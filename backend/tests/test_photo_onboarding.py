"""Photo onboarding: POST /onboarding/photos -> closet digitized (dedupe), body scanned, style inferred, feed warmed."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


def _jpeg(w=400, h=200, fill="white") -> bytes:
    from PIL import Image

    im = Image.new("RGB", (w, h), fill)
    im.paste((0, 0, 0), (0, 0, w // 2, h))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


HOODIE = {"label": "grey hoodie", "category": "top", "color": "grey", "pattern": "solid",
          "style_tags": ["streetwear", "athleisure"], "formality": 2, "box": [0, 0, 0.5, 1]}
JEANS = {"label": "light wash jeans", "category": "bottom", "color": "light blue", "pattern": "solid",
         "style_tags": ["streetwear", "vintage"], "formality": 2, "box": [0.5, 0, 1, 1]}
SNEAKERS = {"label": "white sneakers", "category": "shoes", "color": "white", "pattern": "solid",
            "style_tags": ["streetwear", "minimalist"], "formality": 2, "box": [0, 0, 1, 1]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.ai import service
    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "_spawn", lambda fn: None)  # no background threads in tests
    store.put("users", "u_p", {"id": "u_p", "display_name": "P", "price_ranges": {}, "friends": [],
                               "shop_for": "men", "preferred_stores": ["hm"]})
    return TestClient(app)


def _files(n, **kw):
    return [("files", (f"p{i}.jpg", _jpeg(**kw), "image/jpeg")) for i in range(n)]


def _post(client, n=2, data=None, files=None):
    return client.post("/onboarding/photos", data={"user_id": "u_p", "height_cm": "178", **(data or {})},
                       files=files if files is not None else _files(n))


# ---------- closet ----------

def test_adds_closet_items_and_skips_duplicates_across_the_batch(client):
    from app.store import store

    # the mock detector finds the same two garments in every photo: 3 photos -> 2 items kept, 4 skipped
    r = _post(client, n=3)
    assert r.status_code == 200, r.text
    body = r.json()
    assert sorted(i["label"] for i in body["closet_added"]) == ["black cargo pants", "white baby tee"]
    assert body["closet_skipped_duplicates"] == 4
    assert all(i["duplicate_of"] is None for i in body["closet_added"])
    assert len(store.list("closet_items", user_id="u_p")) == 2


def test_keeps_existing_closet_and_dedupes_against_it(client):
    from app.store import store

    client.post("/closet/digitize", data={"user_id": "u_p"}, files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    before = {i["id"] for i in store.list("closet_items", user_id="u_p")}
    body = _post(client, n=1).json()
    assert body["closet_added"] == [] and body["closet_skipped_duplicates"] == 2
    assert {i["id"] for i in store.list("closet_items", user_id="u_p")} == before


def test_non_clothing_photo_is_skipped_not_fatal(client, monkeypatch):
    from app.ai import digitize

    calls = iter([[], [HOODIE, JEANS]])
    monkeypatch.setattr(digitize, "detect", lambda url: next(calls))
    body = _post(client, n=2).json()
    assert [i["label"] for i in body["closet_added"]] == ["grey hoodie", "light wash jeans"]


def test_tagging_down_for_every_photo_is_a_plain_502(client, monkeypatch):
    from app.ai import digitize

    def down(url):
        raise RuntimeError("provider 529 request_id=xyz")

    monkeypatch.setattr(digitize, "detect", down)
    r = _post(client, n=2)
    assert r.status_code == 502 and "xyz" not in r.text


def test_tagging_down_for_one_photo_still_succeeds(client, monkeypatch):
    from app.ai import digitize

    calls = iter([RuntimeError("boom"), [SNEAKERS]])

    def flaky(url):
        c = next(calls)
        if isinstance(c, Exception):
            raise c
        return c

    monkeypatch.setattr(digitize, "detect", flaky)
    body = _post(client, n=2).json()
    assert [i["label"] for i in body["closet_added"]] == ["white sneakers"]


# ---------- body ----------

def test_body_profile_saved_mock_uses_formula_and_no_body_photo(client):
    from app.store import store

    body = _post(client, n=2, data={"weight_kg": "72"}).json()
    prof = body["body_profile"]
    assert prof["source"] == "estimate" and prof["height_cm"] == 178 and prof["weight_kg"] == 72
    assert prof["waist_in"] and prof["inseam_in"] and prof["full_body"] is False and "full-body" in prof["note"]
    assert body["body_photo_url"] is None  # no full-body photo found: no try-on photo set
    user = store.get("users", "u_p")
    assert user["body_profile"] == prof and user.get("body_photo_url") is None


def test_body_scan_averages_full_body_photos_cheapest_first(client, monkeypatch):
    from app.ai import body_scan
    from app.store import store

    seen = []

    def fake_ai(prompt, **k):
        seen.append(k["image_url"])
        # the second and third photos scanned are full-body; their numbers are averaged
        if len(seen) == 2:
            return {"full_body_visible": True, "build": "slim", "chest_in": 38, "waist_in": 31, "hip_in": 38,
                    "inseam_in": 32, "note": "long legs"}
        if len(seen) == 3:
            return {"full_body_visible": True, "build": "slim", "chest_in": 39, "waist_in": 32, "hip_in": 38,
                    "inseam_in": 32, "note": "long legs"}
        return {"full_body_visible": False}

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", fake_ai)
    # three photos of different file sizes: small, big, medium -> scanned small, medium, big
    files = [("files", ("small.jpg", _jpeg(200, 100), "image/jpeg")),
             ("files", ("big.jpg", _jpeg(1600, 800, "red"), "image/jpeg")),
             ("files", ("medium.jpg", _jpeg(800, 400, "blue"), "image/jpeg"))]
    body = _post(client, files=files).json()
    assert len(seen) == 3  # every photo is scanned; more full-body photos = better estimate
    assert body["body_photo_url"] == seen[1]  # the first full-body photo becomes the try-on photo
    assert body["body_profile"]["source"] == "ai" and body["body_profile"]["build"] == "slim"
    assert body["body_profile"]["full_body"] is True and body["body_profile"]["chest_in"] == 38.5
    assert body["body_profile"]["waist_in"] == 31.5
    assert body["body_profile"]["scan_photos"] == 2 and body["body_profile"]["confidence"] == "medium"
    assert store.get("users", "u_p")["body_photo_url"] == seen[1]
    from app.static_urls import local_static_path
    from app.store import DATA_DIR
    sizes = [local_static_path(u, DATA_DIR).stat().st_size for u in seen]
    assert sizes == sorted(sizes)  # cheapest first


def test_body_scan_without_a_full_body_photo_falls_back_to_the_formula(client, monkeypatch):
    from app.ai import body_scan

    seen = []

    def never(prompt, **k):
        seen.append(k["image_url"])
        return {"full_body_visible": False}

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", never)
    body = _post(client, n=5).json()
    assert len(seen) == 5 and body["body_photo_url"] is None and body["body_profile"]["source"] == "estimate"
    assert body["body_profile"]["scan_photos"] == 0 and body["body_profile"]["confidence"] == "low"


def test_a_scan_keeps_what_the_user_typed(client):
    client.patch("/users/u_p/body-profile", json={"height_cm": 180, "waist_cm": 76.2})
    prof = _post(client, n=1, data={"weight_kg": "72"}).json()["body_profile"]
    assert prof["height_cm"] == 180 and prof["waist_in"] == 30.0 and prof["inseam_in"]


# ---------- style ----------

def test_style_inferred_from_garments_and_saved_onboarded(client, monkeypatch):
    from app.ai import digitize
    from app.store import store

    calls = iter([[HOODIE, JEANS], [SNEAKERS]])
    monkeypatch.setattr(digitize, "detect", lambda url: next(calls))
    body = _post(client, n=2).json()
    style = body["style"]
    assert style["style_tags"] == ["streetwear", "athleisure", "minimalist"] or style["style_tags"][0] == "streetwear"
    assert len(style["style_tags"]) == 3 and style["formality"] == "casual"
    assert style["colors"][0] in {"grey", "gray", "light blue", "white"} and len(style["colors"]) == 3
    assert style["style_text"].startswith("streetwear and ")
    assert "grey hoodie" in style["style_text"] and "mostly casual" in style["style_text"]
    user = store.get("users", "u_p")
    assert user["style_text"] == style["style_text"] and user["style_tags"] == style["style_tags"]
    assert user["onboarded"] is True
    assert user["shop_for"] == "men" and user["preferred_stores"] == ["hm"]  # untouched
    assert body["user"]["onboarded"] is True and body["user"]["style_tags"] == style["style_tags"]


def test_style_hint_is_prepended_and_its_budget_parsed(client):
    from app.store import store

    body = _post(client, n=1, data={"style_hint": "Y2K, tops under $40"}).json()
    assert body["style"]["style_text"].startswith("Y2K, tops under $40; ")
    assert body["style"]["style_tags"][0] == "y2k"
    user = store.get("users", "u_p")
    assert user["price_ranges"]["top"] == [0, 40] and user["onboarded"] is True


def test_ai_style_sentence_used_when_on_and_rules_when_bad(monkeypatch):
    from app.ai import photo_onboarding as po

    items = [HOODIE, JEANS]
    monkeypatch.setattr(po, "text_mock", lambda: False)
    monkeypatch.setattr(po, "ai_json", lambda prompt, **k: {"style_text": "Relaxed streetwear; hoodies and faded denim; casual."})
    assert po.infer_style(items)["style_text"] == "Relaxed streetwear; hoodies and faded denim; casual"
    monkeypatch.setattr(po, "ai_json", lambda prompt, **k: {"style_text": "x" * 500})
    assert po.infer_style(items)["style_text"] == po.style_summary(items)["style_text"]

    def down(*a, **k):
        raise RuntimeError("overloaded")

    monkeypatch.setattr(po, "ai_json", down)
    assert po.infer_style(items, "grunge")["style_text"].startswith("grunge; streetwear")


def test_style_summary_with_nothing_is_empty_not_an_error():
    from app.ai.photo_onboarding import style_summary

    assert style_summary([]) == {"style_tags": [], "colors": [], "formality": "unknown", "style_text": ""}


# ---------- feed warm-up ----------

def test_feed_warm_up_is_spawned_not_awaited(client, monkeypatch):
    from app.ai import service

    spawned = []
    monkeypatch.setattr(service, "_spawn", lambda fn: spawned.append(fn))
    assert _post(client, n=1).status_code == 200
    assert len(spawned) == 1
    spawned[0]()  # runs pair() in mock mode without raising


# ---------- validation ----------

@pytest.mark.parametrize("data", [{"height_cm": "90"}, {"height_cm": "250"}, {"weight_kg": "10"}, {"weight_kg": "300"}])
def test_rejects_impossible_numbers(client, data):
    assert _post(client, n=1, data=data).status_code == 422


def test_rejects_no_files_and_too_many(client):
    assert _post(client, files=[]).status_code == 422
    assert _post(client, n=9).status_code == 422


def test_rejects_non_image(client):
    r = _post(client, files=_files(1) + [("files", ("x.txt", b"hi", "text/plain"))])
    assert r.status_code == 415


def test_creates_the_user_when_unknown(client):
    from app.store import store

    r = client.post("/onboarding/photos", data={"user_id": "u_new", "height_cm": "170"}, files=_files(1))
    assert r.status_code == 200, r.text
    user = store.get("users", "u_new")
    assert user and user["onboarded"] is True and user["body_profile"]["height_cm"] == 170


# ---------- presenting -> shop_for ----------

def _full_body(presenting):
    def fake(prompt, **k):
        return {"full_body_visible": True, "build": "average", "chest_in": 38, "waist_in": 31, "hip_in": 38,
                "inseam_in": 32, "presenting": presenting, "note": ""}
    return fake


def test_presenting_sets_shop_for_only_when_the_user_never_chose(client, monkeypatch):
    from app.ai import body_scan
    from app.store import store

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", _full_body("Women"))
    # u_p chose "men" during onboarding: a photo never overrides that
    body = _post(client, n=1).json()
    assert body["shop_for"] == "men" and store.get("users", "u_p")["shop_for"] == "men"
    assert body["body_profile"]["presenting"] == "women"
    # a new user (default "both") gets the department the photo points to
    r = client.post("/onboarding/photos", data={"user_id": "u_w", "height_cm": "165"}, files=_files(1))
    assert r.json()["shop_for"] == "women" and store.get("users", "u_w")["shop_for"] == "women"
    assert r.json()["user"]["shop_for"] == "women"


def test_unknown_presenting_leaves_shop_for_alone(client, monkeypatch):
    from app.ai import body_scan
    from app.store import store

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", _full_body("not sure"))
    r = client.post("/onboarding/photos", data={"user_id": "u_q", "height_cm": "170"}, files=_files(1))
    assert r.json()["shop_for"] == "both" and r.json()["body_profile"]["presenting"] == "unknown"
    assert store.get("users", "u_q")["shop_for"] == "both"
    # mock / not full-body: presenting is "unknown", never a guess
    assert _post(client, n=1).json()["body_profile"]["presenting"] == "unknown"
