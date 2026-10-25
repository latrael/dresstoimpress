"""Friends: a handle (lowercase username) and a friend code per user, mutual friendship on add.

Hackathon scope: no requests/accepts. `users.friends` (already on the User model) holds the ids, kept
symmetric. `users.handle` and `users.friend_code` are generated on first read so the team accounts just work.
"""
from __future__ import annotations

import hashlib
import re
import time

from fastapi import HTTPException

from ..store import store

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
_HANDLE_RE = re.compile(r"[^a-z0-9_]")


def _code_for(user_id: str) -> str:
    h = hashlib.sha256(user_id.encode()).digest()
    return "NCH-" + "".join(_ALPHABET[b % len(_ALPHABET)] for b in h[:4])


def _handle_for(user: dict) -> str:
    base = _HANDLE_RE.sub("", (user.get("display_name") or user["id"]).lower().replace(" ", "_")) or user["id"]
    base = base[:20]
    handle, n = base, 2
    while any(u.get("handle") == handle and u["id"] != user["id"] for u in store.list("users")):
        handle, n = f"{base}{n}", n + 1
    return handle


def ensure_identity(user: dict) -> dict:
    """Fill in handle + friend_code once; returns the (possibly saved) user doc."""
    changed = False
    if not user.get("handle"):
        user["handle"] = _handle_for(user)
        changed = True
    if not user.get("friend_code"):
        user["friend_code"] = _code_for(user["id"])
        changed = True
    if changed:
        store.put("users", user["id"], user)
    return user


def _get(user_id: str) -> dict:
    user = store.get("users", user_id)
    if not user:
        raise HTTPException(404, "unknown user")
    return ensure_identity(user)


def identity(user_id: str) -> dict:
    u = _get(user_id)
    return {"id": u["id"], "handle": u["handle"], "friend_code": u["friend_code"],
            "friends_count": len(u.get("friends") or [])}


def _public(u: dict) -> dict:
    return {"id": u["id"], "handle": u.get("handle", ""), "display_name": u.get("display_name", ""),
            "body_photo_url": u.get("body_photo_url")}


def list_friends(user_id: str) -> list[dict]:
    u = _get(user_id)
    out = []
    for fid in u.get("friends") or []:
        f = store.get("users", fid)
        if f:
            out.append(_public(ensure_identity(f)))
    return out


def resolve(handle_or_code: str) -> dict:
    """A user by handle (with or without @) or by friend code (case-insensitive, dash optional)."""
    q = (handle_or_code or "").strip()
    if not q:
        raise HTTPException(422, "handle or code required")
    code = q.upper().replace(" ", "")
    if not code.startswith("NCH-") and len(code) == 4:
        code = "NCH-" + code
    handle = q.lstrip("@").lower()
    for u in store.list("users"):
        ensure_identity(u)
        if u["friend_code"] == code or u["handle"] == handle:
            return u
    raise HTTPException(404, "no one with that handle or code")


def add_friend(user_id: str, handle_or_code: str) -> list[dict]:
    me = _get(user_id)
    other = resolve(handle_or_code)
    if other["id"] == me["id"]:
        raise HTTPException(422, "that's you")
    for a, b in ((me, other), (other, me)):
        friends = list(a.get("friends") or [])
        if b["id"] not in friends:
            friends.append(b["id"])
            a["friends"] = friends
            a["friends_at"] = {**(a.get("friends_at") or {}), b["id"]: time.time()}
            store.put("users", a["id"], a)
    return list_friends(user_id)


def remove_friend(user_id: str, friend_id: str) -> list[dict]:
    me = _get(user_id)
    other = store.get("users", friend_id)
    if not other:
        raise HTTPException(404, "unknown user")
    for a, b in ((me, other), (other, me)):
        friends = [x for x in (a.get("friends") or []) if x != b["id"]]
        if friends != (a.get("friends") or []):
            a["friends"] = friends
            store.put("users", a["id"], a)
    return list_friends(user_id)
