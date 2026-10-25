"""Multi-photo body scan: POST /users/{id}/body-scan with 1-6 `files` -> averaged estimate + confidence."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


def _jpeg(w=200, h=400, fill="gray") -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), fill).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.ai import router as ai_router
    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(ai_router, "DATA_DIR", tmp_path)
    store.put("users", "u_m", {"id": "u_m", "display_name": "M", "price_ranges": {}, "friends": []})
    return TestClient(app)


def _files(n):
    return [("files", (f"p{i}.jpg", _jpeg(200 + 10 * i, 400), "image/jpeg")) for i in range(n)]


def _post(client, files, params=None):
    return client.post("/users/u_m/body-scan", params=params or {}, data={"height_cm": "178", "weight_kg": "72"},
                       files=files)


def _answers(monkeypatch, answers):
    """Scripted AI replies, one per photo scanned, in order."""
    from app.ai import body_scan

    seen = []
    it = iter(answers)

    def fake(prompt, **k):
        seen.append(k["image_url"])
        return next(it)

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", fake)
    return seen


def _full(chest, waist, hip, inseam, build="slim", presenting="men"):
    return {"full_body_visible": True, "build": build, "chest_in": chest, "waist_in": waist, "hip_in": hip,
            "inseam_in": inseam, "presenting": presenting, "note": "ok"}


def test_single_file_field_still_works_and_is_low_confidence(client):
    r = _post(client, {"file": ("me.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    prof = r.json()["body_profile"]
    assert prof["source"] == "estimate" and prof["scan_photos"] == 0 and prof["confidence"] == "low"
    assert r.json()["skipped"] == 1 and r.json()["committed"] is True


def test_three_full_body_photos_are_averaged_high_confidence(client, monkeypatch):
    from app.store import store

    seen = _answers(monkeypatch, [_full(38, 30, 38, 32), _full(40, 32, 40, 33, build="athletic"),
                                  _full(39, 31, 39, 32, build="athletic", presenting="unknown")])
    r = _post(client, _files(3))
    assert r.status_code == 200, r.text
    body = r.json()
    prof = body["body_profile"]
    assert len(seen) == 3 and body["skipped"] == 0
    assert (prof["chest_in"], prof["waist_in"], prof["hip_in"], prof["inseam_in"]) == (39.0, 31.0, 39.0, 32.5)
    assert prof["build"] == "athletic" and prof["presenting"] == "men"  # majority votes
    assert prof["scan_photos"] == 3 and prof["confidence"] == "high" and prof["source"] == "ai"
    assert body["body_photo_url"] == seen[0]  # the first full-body photo is the try-on photo
    user = store.get("users", "u_m")
    assert user["body_photo_url"] == seen[0] and user["body_profile"]["confidence"] == "high"


def test_non_full_body_photos_are_skipped_and_confidence_follows_the_count(client, monkeypatch):
    seen = _answers(monkeypatch, [{"full_body_visible": False}, _full(38, 30, 38, 32), _full(38, 31, 38, 32)])
    body = _post(client, _files(3)).json()
    prof = body["body_profile"]
    assert body["skipped"] == 1 and prof["scan_photos"] == 2 and prof["confidence"] == "medium"
    assert prof["waist_in"] == 30.5
    assert body["body_photo_url"] == seen[1]  # not the selfie


def test_one_full_body_photo_is_low_confidence_and_draft_path_has_the_same_fields(client, monkeypatch):
    from app.store import store

    _answers(monkeypatch, [_full(38, 30, 38, 32), {"full_body_visible": False}])
    body = _post(client, _files(2), params={"commit": "false"}).json()
    assert body["committed"] is False and body["skipped"] == 1
    assert body["body_profile"]["scan_photos"] == 1 and body["body_profile"]["confidence"] == "low"
    assert store.get("users", "u_m").get("body_profile") is None  # draft: nothing saved
    r = client.post("/users/u_m/body-scan/confirm", json={"body_photo_url": body["body_photo_url"],
                                                          "profile": body["body_profile"], "edited": []})
    assert r.status_code == 200, r.text
    assert r.json()["body_profile"]["confidence"] == "low" and r.json()["body_profile"]["scan_photos"] == 1


def test_rejects_no_photos_and_too_many(client):
    assert _post(client, []).status_code == 422
    assert _post(client, _files(7)).status_code == 422


def test_scan_many_unit_rounds_to_half_inch(monkeypatch):
    from app.ai import body_scan

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    answers = iter([_full(38, 30, 38, 32), _full(39, 31, 38, 32)])
    monkeypatch.setattr(body_scan, "ai_json", lambda prompt, **k: next(answers))
    profile, url, skipped = body_scan.scan_many(["a", "b"], 178, 72)
    assert (profile["chest_in"], profile["waist_in"]) == (38.5, 30.5) and url == "a" and skipped == 0
    assert body_scan.confidence(0) == "low" and body_scan.confidence(2) == "medium" and body_scan.confidence(5) == "high"
