"""Council sprint (AI lane): Inspo tag pin boxes, Discover vibe search, body photo delete."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


def _jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (60, 120), "white").save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("users", "u_v", {"id": "u_v", "display_name": "V", "price_ranges": {}, "friends": []})
    return TestClient(app)


# ---------- tag pin boxes ----------

def test_fit_box_normalizes_and_drops_bad_boxes():
    from app.ai.service import fit_box

    assert fit_box([0.1, 0.2, 0.5, 0.9]) == [0.1, 0.2, 0.5, 0.9]
    assert fit_box([100, 200, 500, 900]) == [0.1, 0.2, 0.5, 0.9]         # 0-1000 style
    assert fit_box([0.5, 0.9, 0.1, 0.2]) == [0.1, 0.2, 0.5, 0.9]         # swapped corners
    for bad in (None, "nope", [1, 2, 3], [0.1, 0.1, 0.11, 0.9], [400, 200, 2000, 1800], {}, []):
        assert fit_box(bad) is None, bad


def test_tag_fit_returns_boxes(client):
    tags = client.post("/ai/tag-fit", json={"image_url": "https://x/fit.jpg"}).json()
    assert tags and all(len(t["box"]) == 4 for t in tags)
    x0, y0, x1, y1 = tags[0]["box"]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def test_tag_fit_drops_invalid_box_but_keeps_the_tag(monkeypatch):
    from app.ai import service

    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(service, "ai_json", lambda *a, **k: [
        {"label": "black hoodie", "category": "top", "color": "black", "box": [0.2, 0.1, 0.8, 0.5]},
        {"label": "grey sweatpants", "category": "bottom", "color": "grey", "box": "somewhere"}])
    got = service.tag_fit("https://x/boxes-unique.jpg")
    assert got[0]["box"] == [0.2, 0.1, 0.8, 0.5]
    assert got[1]["label"] == "grey sweatpants" and got[1]["box"] is None


def test_fit_tag_model_keeps_valid_box_and_drops_invalid():
    from app.models import FitTag

    assert FitTag(label="x", box=[0.1, 0.2, 0.3, 0.4]).box == [0.1, 0.2, 0.3, 0.4]
    assert FitTag(label="x").box is None
    assert FitTag(label="x", box=[0.5, 0.2, 0.3, 0.4]).box is None    # x0 > x1
    assert FitTag(label="x", box=[0, 0, 2, 1]).box is None            # outside the photo
    assert FitTag(label="x", box="nope").box is None


def test_fitcheck_post_stores_boxes_and_tag_edit_round_trips(client):
    r = client.post("/fitcheck", json={"user_id": "u_v", "photo_url": "https://x/ootd.jpg", "caption": "fit"})
    assert r.status_code == 200, r.text
    post = r.json()
    assert post["tagged"] and all(t["box"] for t in post["tagged"])
    edited = [{**post["tagged"][0], "label": "baggy jeans"}, {"label": "added by hand"}]
    r = client.patch(f"/fitcheck/{post['id']}/tags", json={"user_id": "u_v", "tagged": edited})
    assert r.status_code == 200, r.text
    tags = r.json()["tagged"]
    assert tags[0]["box"] == post["tagged"][0]["box"] and tags[1]["box"] is None


# ---------- vibe search ----------

def test_vibe_rules_in_mock_mode(client):
    r = client.post("/ai/vibe", json={"q": "Fit for a rooftop PARTY"})
    assert r.status_code == 200
    v = r.json()
    assert set(v) == {"styles", "categories", "colors", "keywords", "source"}
    assert v["source"] == "rules" and "classic" in v["styles"] and "black" in v["colors"]

    v = client.post("/ai/vibe", json={"q": "baggy cargo pants and a black puffer"}).json()
    assert "streetwear" in v["styles"] and {"bottom", "outerwear"} <= set(v["categories"])
    assert "black" in v["colors"] and "cargo" in v["keywords"]


def test_vibe_rejects_empty_and_long_queries(client):
    assert client.post("/ai/vibe", json={"q": "   "}).status_code == 422
    assert client.post("/ai/vibe", json={"q": "x" * 201}).status_code == 422
    assert client.post("/ai/vibe", json={}).status_code == 422


def test_vibe_ai_answer_is_limited_to_our_vocab_and_cached(client, monkeypatch):
    from app.ai import vibe as vibe_mod

    calls = []

    def fake(prompt, **k):
        calls.append(prompt)
        return {"styles": ["Classic", "glam", "streetwear"], "categories": ["top", "jewellery"],
                "colors": ["Black", "silver"], "keywords": ["satin shirt", "wide leg trousers"]}

    monkeypatch.setattr(vibe_mod, "text_mock", lambda: False)
    monkeypatch.setattr(vibe_mod, "ai_json", fake)
    v = vibe_mod.vibe("night out downtown")
    assert v == {"styles": ["classic", "streetwear"], "categories": ["top"], "colors": ["black", "silver"],
                 "keywords": ["satin shirt", "wide leg trousers"], "source": "ai"}
    assert vibe_mod.vibe("  Night OUT downtown ") == v and len(calls) == 1   # cached per normalized q
    assert '"night out downtown"' in calls[0]


def test_vibe_falls_back_to_rules_when_ai_fails_or_says_nothing(monkeypatch):
    from app.ai import vibe as vibe_mod

    monkeypatch.setattr(vibe_mod, "text_mock", lambda: False)

    def boom(*a, **k):
        raise RuntimeError("no credits")

    monkeypatch.setattr(vibe_mod, "ai_json", boom)
    assert vibe_mod.vibe("gym fit unique-1")["source"] == "rules"
    monkeypatch.setattr(vibe_mod, "ai_json", lambda *a, **k: {"styles": ["glam"]})
    v = vibe_mod.vibe("gym fit unique-2")
    assert v["source"] == "rules" and v["styles"] == ["athleisure"]


# ---------- body photo delete ----------

def test_delete_body_photo_removes_file_keeps_measurements(client):
    from app.ai.router import DATA_DIR
    from app.store import store

    r = client.post("/users/u_v/body-scan", data={"height_cm": "178"},
                    files={"file": ("me.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    url = r.json()["body_photo_url"]
    path = DATA_DIR / "uploads" / url.rsplit("/", 1)[1]
    assert path.is_file()

    assert client.delete("/users/u_v/body-photo").json() == {"deleted": True}
    assert not path.exists()
    user = store.get("users", "u_v")
    assert user["body_photo_url"] is None and user["body_profile"]["height_cm"] == 178
    assert client.delete("/users/u_v/body-photo").json() == {"deleted": False}   # repeat-safe
    assert client.delete("/users/nobody/body-photo").json() == {"deleted": False}


def test_delete_body_photo_never_deletes_files_outside_uploads(client, tmp_path):
    from app.ai.router import DATA_DIR
    from app.store import store

    other = DATA_DIR / "tryon"
    other.mkdir(parents=True, exist_ok=True)
    f = other / "keep.jpg"
    f.write_bytes(_jpeg())
    store.put("users", "u_v", {"id": "u_v", "display_name": "V", "body_photo_url":
                               "http://localhost:8000/static/tryon/keep.jpg"})
    assert client.delete("/users/u_v/body-photo").json() == {"deleted": True}
    assert f.exists() and store.get("users", "u_v")["body_photo_url"] is None
