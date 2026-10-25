"""Google sign-in + optional Bearer enforcement (app/auth.py). No network: tokens are signed with a local
RSA key and the Google cert fetch is replaced by that key's public half."""
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

CID = "ios-client.apps.googleusercontent.com"


def _keypair():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub.decode()


GOOGLE_PRIV, GOOGLE_PUB = _keypair()
OTHER_PRIV, _ = _keypair()


def make_token(priv=GOOGLE_PRIV, kid="k1", **over):
    from google.auth import crypt, jwt

    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CID, "sub": "g-123", "email": "ada@example.com",
              "email_verified": True, "name": "Ada Lovelace", "iat": now, "exp": now + 3600, **over}
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(crypt.RSASigner.from_string(priv, key_id=kid), claims).decode()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import auth
    from app.main import app
    from app.store import store

    old = getattr(store, "root", None)
    store.root = Path(tmp_path)
    monkeypatch.setenv("GOOGLE_CLIENT_IDS", f"web-client.apps.googleusercontent.com, {CID}")
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    monkeypatch.setattr(auth, "_google_certs", lambda kid: {"k1": GOOGLE_PUB})
    for uid in ("u_adam", "u_nabil"):
        store.put("users", uid, {"id": uid, "display_name": uid})
    yield TestClient(app)
    store.root = old


def login(client, **kw):
    link = kw.pop("link_user_id", None)
    body = {"id_token": make_token(**kw)}
    if link:
        body["link_user_id"] = link
    return client.post("/auth/google", json=body)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---- /auth/google: token verification ----

def test_valid_token_creates_user_and_session(client):
    from app.auth import _hash
    from app.store import store

    r = login(client)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] is True
    u = out["user"]
    assert u["id"].startswith("u_ada-lovelace-") and len(u["id"]) == len("u_ada-lovelace-") + 4
    assert u["display_name"] == "Ada Lovelace"
    assert u["auth"] == [{"provider": "google", "sub": "g-123", "email": "ada@example.com"}]
    s = store.get("sessions", _hash(out["token"]))  # stored by hash, never the raw token
    assert s["user_id"] == u["id"] and out["token"] not in str(store._load("sessions"))
    days = (datetime.fromisoformat(s["expires_at"]) - datetime.fromisoformat(s["created_at"])).days
    assert days == 30
    assert client.get("/auth/me", headers=bearer(out["token"])).json() == u


def test_same_google_account_finds_same_user(client):
    first = login(client).json()
    again = login(client, email="changed@example.com", name="Someone Else").json()
    assert again["created"] is False and again["user"]["id"] == first["user"]["id"]
    assert again["token"] != first["token"]


def test_same_email_different_sub_is_a_different_user(client):
    a = login(client).json()
    b = login(client, sub="g-999").json()  # email alone never matches an account
    assert b["created"] is True and b["user"]["id"] != a["user"]["id"]


@pytest.mark.parametrize("over,detail", [
    ({"priv": OTHER_PRIV}, "invalid google id token"),                     # bad signature
    ({"exp": int(time.time()) - 600, "iat": int(time.time()) - 4000}, "invalid google id token"),  # expired
    ({"aud": "someone-else.apps.googleusercontent.com"}, "invalid google id token"),
    ({"iss": "https://evil.example.com"}, "invalid google id token issuer"),
    ({"email_verified": False}, "google email not verified"),
    ({"email_verified": None}, "google email not verified"),
])
def test_rejected_tokens(client, over, detail):
    r = login(client, **over)
    assert r.status_code == 401 and r.json()["detail"] == detail


def test_accepts_bare_issuer_and_any_configured_client(client):
    r = login(client, iss="accounts.google.com", aud="web-client.apps.googleusercontent.com")
    assert r.status_code == 200


def test_garbage_and_unknown_key(client):
    assert client.post("/auth/google", json={"id_token": "not.a.jwt-at-all"}).status_code == 401
    assert login(client, kid="rotated-away").status_code == 401


def test_not_configured(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_IDS", "")
    assert login(client).status_code == 503


def test_certs_cached_and_refetched_for_new_kid(monkeypatch):
    from app import auth

    calls = []
    monkeypatch.setattr(auth, "_certs", {})
    monkeypatch.setattr(auth, "_certs_expiry", 0.0)
    monkeypatch.setattr(auth, "_fetch_google_certs", lambda: (calls.append(1) or {"k1": "pem"}, 3600.0))
    auth._google_certs("k1")
    auth._google_certs("k1")
    assert len(calls) == 1
    auth._google_certs("k2")  # unseen key id: Google rotated keys, fetch again
    assert len(calls) == 2


# ---- linking ----

def test_link_existing_user(client):
    r = login(client, link_user_id="u_adam").json()
    assert r["created"] is False and r["user"]["id"] == "u_adam"
    assert r["user"]["auth"][0]["sub"] == "g-123"
    # next sign-in finds u_adam without link_user_id
    assert login(client).json()["user"]["id"] == "u_adam"
    # linking the same account to the same user again is fine
    assert login(client, link_user_id="u_adam").status_code == 200


def test_link_conflicts(client):
    login(client, link_user_id="u_adam")
    # u_adam already has a google account
    assert login(client, sub="g-other", link_user_id="u_adam").status_code == 409
    # this google account already belongs to u_adam
    assert login(client, link_user_id="u_nabil").status_code == 409
    assert login(client, sub="g-new", link_user_id="u_nobody").status_code == 404


def test_patch_keeps_identity(client):
    login(client, link_user_id="u_adam")
    u = client.patch("/users/u_adam", json={"display_name": "Adam"}).json()
    assert u["auth"][0]["sub"] == "g-123"


# ---- sessions ----

def test_logout_revokes(client):
    tok = login(client).json()["token"]
    assert client.post("/auth/logout", headers=bearer(tok)).json() == {"revoked": True}
    assert client.get("/auth/me", headers=bearer(tok)).status_code == 401
    assert client.post("/auth/logout", headers=bearer(tok)).status_code == 401


def test_expired_session(client):
    from app.auth import _hash
    from app.store import store

    tok = login(client).json()["token"]
    s = store.get("sessions", _hash(tok))
    store.put("sessions", _hash(tok), {**s, "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
    assert client.get("/auth/me", headers=bearer(tok)).status_code == 401
    assert store.get("sessions", _hash(tok)) is None  # cleaned up


def test_me_needs_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=bearer("nope")).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


# ---- optional enforcement ----

def test_no_header_is_unchanged(client):
    assert client.get("/users/u_nabil").status_code == 200
    assert client.patch("/users/u_adam", json={"display_name": "A"}).status_code == 200


def test_bearer_pins_the_user(client):
    tok = login(client, link_user_id="u_adam").json()["token"]
    h = bearer(tok)
    assert client.get("/users/u_adam", headers=h).status_code == 200                  # path, same user
    assert client.get("/users/u_nabil", headers=h).status_code == 403                 # path, other user
    assert client.get("/feed", params={"user_id": "u_nabil"}, headers=h).status_code == 403   # query
    r = client.post("/onboarding", json={"user_id": "u_nabil", "text": "y2k"}, headers=h)      # JSON body
    assert r.status_code == 403 and r.json()["detail"] == "user_id does not match the signed-in user"
    assert client.post("/onboarding", json={"user_id": "u_adam", "text": "y2k"}, headers=h).status_code == 200
    r = client.post("/closet/upload", data={"user_id": "u_nabil", "kind": "piece"},         # form field
                    files={"files": ("a.jpg", b"\xff\xd8", "image/jpeg")}, headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "user_id does not match the signed-in user"
    assert client.get("/products", headers=h).status_code == 200                      # no user_id at all


def test_bad_bearer_is_401_even_when_not_strict(client):
    assert client.get("/users/u_adam", headers=bearer("stale")).status_code == 401
    assert client.get("/products", headers={"Authorization": "Bearer"}).status_code == 401


def test_strict_mode(client, monkeypatch):
    tok = login(client, link_user_id="u_adam").json()["token"]
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    assert client.get("/users/u_adam").status_code == 401
    assert client.get("/feed", params={"user_id": "u_adam"}).status_code == 401
    assert client.post("/onboarding", json={"text": "y2k"}).status_code == 401  # takes an (optional) user_id
    assert client.get("/users/u_adam", headers=bearer(tok)).status_code == 200
    assert client.get("/products").status_code == 200   # no user_id: stays open
    assert client.get("/health").status_code == 200
    assert login(client).status_code == 200              # /auth/google stays open


def test_open_paths_ignore_bearer(client):
    assert client.get("/health", headers=bearer("stale")).status_code == 200
    assert client.post("/auth/google", json={"id_token": make_token()}, headers=bearer("stale")).status_code == 200
