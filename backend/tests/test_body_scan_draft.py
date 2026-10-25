"""Draft body scan (`?commit=false`) -> review -> POST /users/{id}/body-scan/confirm (Ryan's follow-up #1)."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


def _jpeg(w=200, h=400) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), "gray").save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.ai import router as ai_router
    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(ai_router, "DATA_DIR", tmp_path)  # uploads land in tmp_path/uploads
    store.put("users", "u_d", {"id": "u_d", "display_name": "D", "price_ranges": {}, "friends": []})
    return TestClient(app)


def _scan(client, commit=None, user="u_d"):
    params = {} if commit is None else {"commit": "true" if commit else "false"}
    return client.post(f"/users/{user}/body-scan", params=params, data={"height_cm": "178", "weight_kg": "72"},
                       files={"file": ("me.jpg", _jpeg(), "image/jpeg")})


def test_draft_scan_saves_the_photo_file_but_not_the_user(client, tmp_path):
    from app.store import store

    r = _scan(client, commit=False)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["committed"] is False
    assert body["body_photo_url"].startswith("http://localhost:8000/static/uploads/")
    assert body["body_profile"]["height_cm"] == 178 and body["body_profile"]["source"] == "estimate"
    # the file exists (the AI read it, confirm needs it) ...
    assert (tmp_path / "uploads" / body["body_photo_url"].rsplit("/", 1)[1]).is_file()
    # ... but nothing changed on the user
    user = store.get("users", "u_d")
    assert user.get("body_photo_url") is None and user.get("body_profile") is None


def test_confirm_persists_edited_values_win_and_are_manual(client):
    from app.store import store

    draft = _scan(client, commit=False).json()
    reviewed = {**draft["body_profile"], "waist_in": 33.0, "fit": "slim"}
    r = client.post("/users/u_d/body-scan/confirm",
                    json={"body_photo_url": draft["body_photo_url"], "profile": reviewed, "edited": ["waist_in", "fit"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["committed"] is True and body["body_photo_url"] == draft["body_photo_url"]
    prof = body["body_profile"]
    assert prof["waist_in"] == 33.0 and prof["fit"] == "slim"
    assert prof["manual"] == ["fit", "waist_in"] and prof["source"] == "manual"
    assert prof["inseam_in"] == draft["body_profile"]["inseam_in"]  # unedited scan values kept
    assert prof["height_cm"] == 178 and prof["weight_kg"] == 72
    user = store.get("users", "u_d")
    assert user["body_photo_url"] == draft["body_photo_url"] and user["body_profile"] == prof
    # a later full scan keeps the typed waist (merge_scan semantics)
    again = _scan(client).json()["body_profile"]
    assert again["waist_in"] == 33.0 and "waist_in" in again["manual"]


def test_confirm_without_edits_accepts_the_scan_and_keeps_earlier_typed_values(client):
    from app.store import store

    client.patch("/users/u_d/body-profile", json={"waist_cm": 86.36})  # 34 in, typed earlier
    draft = _scan(client, commit=False).json()
    assert draft["body_profile"]["waist_in"] == 34.0  # the draft already shows what would be saved
    r = client.post("/users/u_d/body-scan/confirm",
                    json={"body_photo_url": draft["body_photo_url"], "profile": draft["body_profile"]})
    assert r.status_code == 200, r.text
    prof = r.json()["body_profile"]
    assert prof["waist_in"] == 34.0 and prof["manual"] == ["waist_in"]
    assert prof["inseam_in"] == draft["body_profile"]["inseam_in"]
    assert store.get("users", "u_d")["body_photo_url"] == draft["body_photo_url"]


@pytest.mark.parametrize("url", [
    "https://evil.example/static/uploads/x.jpg",            # not a file on this server
    "http://localhost:8000/static/tryon/t1.png",            # ours, but not an upload
    "https://image.hm.com/a.jpg",
    "",
])
def test_confirm_rejects_a_photo_that_is_not_one_of_our_uploads(client, url):
    from app.store import store

    r = client.post("/users/u_d/body-scan/confirm", json={"body_photo_url": url, "profile": {"height_cm": 178}})
    assert r.status_code == 422, r.text
    assert store.get("users", "u_d").get("body_photo_url") is None


def test_confirm_rejects_impossible_numbers_and_unknown_build(client):
    draft = _scan(client, commit=False).json()
    url = draft["body_photo_url"]
    bad = {**draft["body_profile"], "waist_in": 5}
    assert client.post("/users/u_d/body-scan/confirm", json={"body_photo_url": url, "profile": bad}).status_code == 422
    bad = {**draft["body_profile"], "build": "giant"}
    assert client.post("/users/u_d/body-scan/confirm", json={"body_photo_url": url, "profile": bad}).status_code == 422
    bad = {**draft["body_profile"], "height_cm": "tall"}
    assert client.post("/users/u_d/body-scan/confirm", json={"body_photo_url": url, "profile": bad}).status_code == 422


def test_default_commit_saves_right_away_as_before(client):
    from app.store import store

    r = _scan(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["committed"] is True
    user = store.get("users", "u_d")
    assert user["body_photo_url"] == body["body_photo_url"] and user["body_profile"] == body["body_profile"]
    # explicit commit=true is the same
    r2 = _scan(client, commit=True).json()
    assert r2["committed"] is True and store.get("users", "u_d")["body_photo_url"] == r2["body_photo_url"]
