"""Google sign-in + session tokens (Nabil). Local branch only until the team agrees; see docs/auth-google.md.

POST /auth/google {id_token, link_user_id?} -> {token, user, created}
POST /auth/logout   (Authorization: Bearer <token>) -> {revoked: true}
GET  /auth/me       (Authorization: Bearer <token>) -> User

The app gets a Google ID token (google_sign_in) and trades it here for our own opaque session token.
Only a SHA-256 of the token is stored (collection `sessions`, doc id = the hash), so a leaked data dir
can't be replayed. The Google account is matched by `sub`, never by email alone.

`auth_guard` is one app-wide dependency (main.py). It never changes today's behaviour when no
Authorization header is sent. With a valid Bearer token, request.state.user_id is the token's user and
any user_id the request also carries (path, query, JSON body or form field) must match, else 403.
AUTH_REQUIRED=1 turns on strict mode: routes that take a user_id then need a valid token (401).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, get_args

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .models import User
from .store import store

router = APIRouter(tags=["auth"])

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"  # {kid: x509 PEM}, what google-auth uses
SESSION_DAYS = 30
CLOCK_SKEW_S = 10


# ---- Google ID token verification ----

_certs: dict[str, str] = {}
_certs_expiry = 0.0
_certs_lock = threading.Lock()


def _fetch_google_certs() -> tuple[dict[str, str], float]:
    """Google's current signing certs and how long to cache them (Cache-Control max-age)."""
    import httpx

    r = httpx.get(GOOGLE_CERTS_URL, timeout=10)
    r.raise_for_status()
    m = re.search(r"max-age=(\d+)", r.headers.get("cache-control", ""))
    return r.json(), float(m.group(1)) if m else 3600.0


def _google_certs(kid: str) -> dict[str, str]:
    """Cached certs; refetched when expired or when the token names a key we haven't seen (rotation)."""
    global _certs, _certs_expiry
    with _certs_lock:
        if time.time() >= _certs_expiry or kid not in _certs:
            _certs, max_age = _fetch_google_certs()
            _certs_expiry = time.time() + max_age
        return _certs


def client_ids() -> list[str]:
    return [c.strip() for c in os.getenv("GOOGLE_CLIENT_IDS", "").split(",") if c.strip()]


def _header(token: str) -> dict:
    seg = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))


def verify_google_id_token(token: str) -> dict:
    """Claims of a valid Google ID token, else HTTPException(401). Checks the RS256 signature against
    Google's keys, exp/iat, aud in GOOGLE_CLIENT_IDS, iss, and email_verified."""
    from google.auth import jwt as gjwt

    auds = client_ids()
    if not auds:
        raise HTTPException(503, "google sign-in not configured (GOOGLE_CLIENT_IDS)")
    try:
        header = _header(token)
        if header.get("alg") != "RS256":
            raise ValueError("unexpected alg")
        certs = _google_certs(str(header.get("kid", "")))
        claims = gjwt.decode(token, certs=certs, audience=auds, clock_skew_in_seconds=CLOCK_SKEW_S)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - bad signature, expired, wrong aud, malformed, certs unreachable
        raise HTTPException(401, "invalid google id token")
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(401, "invalid google id token issuer")
    if not claims.get("sub"):
        raise HTTPException(401, "invalid google id token")
    if claims.get("email_verified") not in (True, "true"):
        raise HTTPException(401, "google email not verified")
    return claims


# ---- sessions ----

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    h = _hash(token)
    store.put("sessions", h, {"token_hash": h, "user_id": user_id, "created_at": now.isoformat(),
                              "expires_at": (now + timedelta(days=SESSION_DAYS)).isoformat()})
    return token


def session_user_id(token: str) -> Optional[str]:
    """The user id for a live session token, else None. Expired sessions are deleted on sight."""
    h = _hash(token)
    s = store.get("sessions", h)
    if not s:
        return None
    if datetime.fromisoformat(s["expires_at"]) <= _now():
        store.delete("sessions", h)
        return None
    return s["user_id"] if store.get("users", s["user_id"]) else None


def bearer_token(request: Request) -> Optional[str]:
    """The Bearer token, None if there's no Authorization header; 401 if the header is malformed."""
    header = request.headers.get("authorization")
    if header is None:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Authorization must be 'Bearer <token>'")
    return token.strip()


# ---- optional enforcement: one app-wide dependency ----

def auth_required() -> bool:
    return os.getenv("AUTH_REQUIRED", "") == "1"


_takes_user_id: dict[int, tuple[bool, bool]] = {}


def _route_user_id(route: Any) -> tuple[bool, bool]:
    """(takes a user_id anywhere, takes it in the body) for a FastAPI route; cached per route."""
    key = id(route)
    if key not in _takes_user_id:
        path, query, body = [], [], []
        todo = [route.dependant]
        while todo:  # the route's own params plus those of its sub-dependencies
            d = todo.pop()
            path += d.path_params
            query += d.query_params
            body += d.body_params
            todo += d.dependencies

        def named(fields):
            return any("user_id" in (f.name, getattr(f, "alias", None)) for f in fields)

        def model_has_user_id(f):
            ann = f.field_info.annotation
            return any("user_id" in (getattr(t, "model_fields", None) or {}) for t in (ann, *get_args(ann)))

        in_body = named(body) or any(model_has_user_id(f) for f in body)
        _takes_user_id[key] = (in_body or named(path) or named(query), in_body)
    return _takes_user_id[key]


async def _claimed_user_ids(request: Request, body: bool) -> set[str]:
    ids = {request.path_params.get("user_id")} | set(request.query_params.getlist("user_id"))
    if body:  # FastAPI has already read and cached the body for routes with body params
        ctype = request.headers.get("content-type", "")
        try:
            if ctype.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
                ids.add((await request.form()).get("user_id"))
            elif raw := await request.body():
                data = json.loads(raw)
                if isinstance(data, dict):
                    ids.add(data.get("user_id"))
        except Exception:  # noqa: BLE001 - malformed bodies are FastAPI's 422 to report
            pass
    return {i for i in ids if isinstance(i, str) and i}


def make_auth_guard(is_open: Callable[[str], bool]):
    """main.py passes its _is_open so the open paths (/health, /static, /img, /fit...) stay in one place."""

    async def auth_guard(request: Request) -> None:
        path = request.url.path
        request.state.user_id = None
        if is_open(path) or path == "/auth/google":
            return
        route = request.scope.get("route")
        takes, in_body = _route_user_id(route) if route is not None else (False, False)
        token = bearer_token(request)
        if token is None:
            if auth_required() and takes:
                raise HTTPException(401, "sign in required (Authorization: Bearer <token>)")
            return  # today's behaviour: trust the user_id the app sends
        uid = session_user_id(token)
        if uid is None:
            raise HTTPException(401, "invalid or expired session")
        request.state.user_id = uid
        if takes and any(c != uid for c in await _claimed_user_ids(request, in_body)):
            raise HTTPException(403, "user_id does not match the signed-in user")

    return auth_guard


# ---- routes ----

class GoogleLogin(BaseModel):
    id_token: str = Field(..., min_length=10, max_length=8192)
    link_user_id: Optional[str] = Field(None, min_length=1, max_length=64)


def _google_identity(user: dict) -> Optional[dict]:
    return next((a for a in user.get("auth") or [] if a.get("provider") == "google"), None)


def _find_by_google_sub(sub: str) -> Optional[dict]:
    return next((u for u in store.list("users") if (_google_identity(u) or {}).get("sub") == sub), None)


@router.post("/auth/google")
def auth_google(req: GoogleLogin):
    """Verify a Google ID token, find or create the user (by Google `sub`), return a 30-day session token.
    link_user_id attaches this Google account to an existing user that has none yet (first sign-in of a
    team / onboarded account)."""
    from .commerce.users import _new_id, _save

    claims = verify_google_id_token(req.id_token)
    identity = {"provider": "google", "sub": claims["sub"], "email": claims.get("email", "")}
    user = _find_by_google_sub(claims["sub"])
    created = False
    if user:
        if req.link_user_id and req.link_user_id != user["id"]:
            raise HTTPException(409, "this google account is already linked to another user")
    elif req.link_user_id:
        user = store.get("users", req.link_user_id)
        if not user:
            raise HTTPException(404, "unknown user")
        if _google_identity(user):
            raise HTTPException(409, "this user is already linked to a google account")
        user = _save({**user, "auth": [*(user.get("auth") or []), identity]})
    else:
        name = (claims.get("name") or claims.get("given_name") or claims.get("email", "").split("@")[0]
                or "You")[:60]
        uid = _new_id(name)
        while store.get("users", uid):
            uid = _new_id(name)
        user = _save({"id": uid, "display_name": name, "auth": [identity]})
        created = True
    return {"token": create_session(user["id"]), "user": User(**user).model_dump(), "created": created}


def _require_token(request: Request) -> tuple[str, str]:
    token = bearer_token(request)
    uid = session_user_id(token) if token else None
    if uid is None:
        raise HTTPException(401, "invalid or expired session")
    return token, uid


@router.post("/auth/logout")
def auth_logout(request: Request):
    token, _ = _require_token(request)
    store.delete("sessions", _hash(token))
    return {"revoked": True}


@router.get("/auth/me", response_model=User)
def auth_me(request: Request):
    _, uid = _require_token(request)
    return store.get("users", uid)
