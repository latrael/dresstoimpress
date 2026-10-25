"""Closet v2: multi-photo piece/outfit upload, every garment detected, brand, standalone clean shots,
worn-in fits, dedupe merges, auto-add from Fit Check posts, PATCH / reshoot."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


def _jpeg(w=400, h=200) -> bytes:
    """Left half black, right half white: two 'garments' for the mock detector's two boxes."""
    from PIL import Image

    im = Image.new("RGB", (w, h), "white")
    im.paste((0, 0, 0), (0, 0, w // 2, h))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def _files(n, name="files"):
    return [(name, (f"p{i}.jpg", _jpeg(), "image/jpeg")) for i in range(n)]


PRODUCT = {"id": "hm:tee:black", "retailer": "hm", "name": "Black Baby Tee", "brand": "H&M", "category": "top",
           "price_usd": 9.99, "colors": ["black"], "sizes": [{"name": "M", "in_stock": True}], "in_stock": True,
           "image_url": "https://image.hm.com/tee.jpg", "product_url": "https://hm.com/tee", "style_tags": ["y2k"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("users", "u_c", {"id": "u_c", "display_name": "C", "price_ranges": {}, "friends": []})
    return TestClient(app)


def _tagger(monkeypatch, raw):
    from app.ai import service

    monkeypatch.setattr(service, "tag_image", lambda url, hint=None: dict(raw))


# ---------- upload: kinds and shape ----------

def test_outfit_upload_makes_every_garment_with_its_own_crop(client):
    from app.store import store

    r = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"added", "merged", "skipped", "outfits"} and body["merged"] == [] and body["skipped"] == 0
    added = body["added"]
    assert [i["label"] for i in added] == ["black cargo pants", "white baby tee"]
    crops = [i["crop_image_url"] for i in added]
    assert len(set(crops)) == 2 and all("/static/uploads/" in c for c in crops)
    for i in added:
        assert i["image_url"] == i["display_image_url"]
        assert i["worn_in"] and i["worn_in"][0]["source"] == "closet" and i["worn_in"][0]["at"]
        assert i["worn_in"][0]["photo_url"] != i["crop_image_url"]  # the fit photo, not the piece
    assert len(store.list("closet_items", user_id="u_c")) == 2
    # GET /closet carries the new fields
    got = client.get("/closet/u_c").json()
    assert {g["crop_image_url"] for g in got} == set(crops)


def test_kind_defaults_to_outfit_and_several_photos_add_up(client, monkeypatch):
    from app.ai import digitize

    n = {"calls": 0}

    def detect(url):
        n["calls"] += 1
        return [{"label": f"garment {n['calls']} hoodie", "category": "top", "color": ["red", "blue", "green"][n["calls"] - 1],
                 "pattern": "solid", "formality": 2, "box": [0, 0, 1, 1]}]

    monkeypatch.setattr(digitize, "detect", detect)
    r = client.post("/closet/upload", data={"user_id": "u_c"}, files=_files(3))
    assert r.status_code == 200, r.text
    assert n["calls"] == 3 and len(r.json()["added"]) == 3


def test_kind_piece_tags_one_item_per_photo(client, monkeypatch):
    from app.ai import digitize

    def boom(url):
        raise AssertionError("piece uploads must not run the outfit detector")

    monkeypatch.setattr(digitize, "detect", boom)
    r = client.post("/closet/upload", data={"user_id": "u_c", "kind": "piece"}, files=_files(2))
    assert r.status_code == 200, r.text
    body = r.json()
    # the mock tagger says "black tee" for both photos: one new item, the second photo merges into it
    # (an item added by this same upload is reported once, under added, with both photos in worn_in)
    assert len(body["added"]) == 1 and body["merged"] == []
    assert len(body["added"][0]["worn_in"]) == 2


def test_legacy_single_file_call_still_returns_one_item(client):
    r = client.post("/closet/upload", data={"user_id": "u_c"}, files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    item = r.json()
    # sprint-3 §1.1: the legacy call is digitized too (every garment lands in the closet); it answers with the first
    assert item["id"].startswith("ci_") and item["label"] == "black cargo pants" and item["image_url"]
    assert len(client.get("/closet/u_c").json()) == 2


def test_upload_limits_and_bad_kind(client):
    assert client.post("/closet/upload", data={"user_id": "u_c", "kind": "pile"}, files=_files(1)).status_code == 422
    assert client.post("/closet/upload", data={"user_id": "u_c"}).status_code == 422
    assert client.post("/closet/upload", data={"user_id": "u_c"}, files=_files(9)).status_code == 413


# ---------- brand, catalog match, display image ----------

def test_brand_comes_from_the_tagger_never_guessed(client, monkeypatch):
    _tagger(monkeypatch, {"label": "grey hoodie", "category": "top", "color": "grey", "pattern": "solid",
                          "style_tags": ["streetwear"], "formality": 2, "brand": "Stüssy"})
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "piece"}, files=_files(1)).json()["added"][0]
    assert item["brand"] == "Stüssy" and item["product_id"] is None
    _tagger(monkeypatch, {"label": "navy chinos", "category": "bottom", "color": "navy", "pattern": "solid",
                          "formality": 3, "brand": None})
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "piece"}, files=_files(1)).json()["added"][0]
    assert item["brand"] is None


def test_catalog_match_sets_product_but_never_the_display_image(client, monkeypatch):
    from app.store import store

    store.put("products", PRODUCT["id"], PRODUCT)
    _tagger(monkeypatch, {"label": "black baby tee", "category": "top", "color": "black", "pattern": "solid",
                          "formality": 2, "brand": None})
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "piece"}, files=_files(1)).json()["added"][0]
    assert item["product_id"] == PRODUCT["id"] and item["brand"] is None  # catalog match never sets the brand
    assert item["catalog_image_url"] == PRODUCT["image_url"]  # kept for "shop similar", never shown
    assert item["display_image_url"] == item["crop_image_url"] == item["image_url"]  # sprint-3 §1.2
    assert 0.7 <= item["match_confidence"] <= 1.0
    assert "/static/uploads/" in item["crop_image_url"]  # the photo is kept


def test_weak_match_is_not_a_match(client, monkeypatch):
    from app.store import store

    store.put("products", PRODUCT["id"], PRODUCT)
    _tagger(monkeypatch, {"label": "white tee", "category": "top", "color": "white", "pattern": "solid", "formality": 2})
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "piece"}, files=_files(1)).json()["added"][0]
    assert item["product_id"] is None and item["display_image_url"] == item["crop_image_url"]


def test_no_match_generates_a_clean_shot_when_image_ai_is_on(client, monkeypatch):
    from app.ai import closet

    calls = []

    def fake_gemini(prompt, urls):
        calls.append((prompt, urls))
        return b"\x89PNG fake"

    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    monkeypatch.setattr(closet, "gemini_image", fake_gemini)
    body = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()
    assert len(calls) == 2  # one clean shot per garment
    assert "only this garment" in calls[0][0] and "white background" in calls[0][0] and "no person" in calls[0][0]
    for item, (_, urls) in zip(body["added"], calls):
        assert urls == [item["crop_image_url"]]  # generated from the crop
        assert item["display_image_url"].endswith("-clean.png") and item["display_image_url"] != item["crop_image_url"]
        assert client.get(item["display_image_url"].split("8000", 1)[1]).content == b"\x89PNG fake"


def test_no_match_and_no_image_ai_falls_back_to_the_crop(client, monkeypatch):
    from app.ai import closet

    def boom(prompt, urls):
        raise AssertionError("gemini must not be called when image AI is off")

    monkeypatch.setattr(closet, "gemini_image", boom)
    body = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()
    assert all(i["display_image_url"] == i["crop_image_url"] for i in body["added"])


def test_clean_shot_failure_is_not_an_error(client, monkeypatch):
    from app.ai import closet
    from app.ai.llm import BadModelOutput

    def down(prompt, urls):
        raise BadModelOutput("quota")

    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    monkeypatch.setattr(closet, "gemini_image", down)
    r = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1))
    assert r.status_code == 200 and all(i["display_image_url"] == i["crop_image_url"] for i in r.json()["added"])


# ---------- dedupe merges ----------

def test_same_outfit_twice_merges_and_appends_worn_in(client):
    from app.store import store

    first = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()
    again = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()
    assert again["added"] == [] and {m["id"] for m in again["merged"]} == {a["id"] for a in first["added"]}
    assert len(store.list("closet_items", user_id="u_c")) == 2  # no twins
    for m in again["merged"]:
        photos = [w["photo_url"] for w in m["worn_in"]]
        assert len(photos) == 2 and len(set(photos)) == 2 and all(w["source"] == "closet" for w in m["worn_in"])


def test_merge_keeps_the_existing_items_display_image(client, monkeypatch):
    from app.ai import closet

    first = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()["added"]
    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    monkeypatch.setattr(closet, "gemini_image", lambda p, u: b"new")
    merged = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()["merged"]
    assert {m["display_image_url"] for m in merged} == {f["display_image_url"] for f in first}


# ---------- Fit Check hook ----------

def test_posting_a_fit_check_adds_its_pieces_to_the_closet(client, monkeypatch):
    from app.ai import closet, service
    from app.store import store

    ran = []
    monkeypatch.setattr(service, "_spawn", lambda fn: ran.append(fn))  # call the hook synchronously below
    r = client.post("/fitcheck", data={"user_id": "u_c", "caption": "fit"}, files={"file": ("f.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    post = r.json()
    assert len(post["tagged"]) == 2 and store.list("closet_items", user_id="u_c") == []  # not yet: background
    assert len(ran) == 1
    ran[0]()
    items = store.list("closet_items", user_id="u_c")
    assert {i["label"] for i in items} == {t["label"] for t in post["tagged"]}
    for i in items:
        assert i["worn_in"] == [{"photo_url": post["photo_url"], "at": i["worn_in"][0]["at"], "source": "fitcheck",
                                 "box": i["worn_in"][0]["box"]}] and i["worn_in"][0]["box"] is not None
        assert "/static/uploads/" in i["crop_image_url"] and i["crop_image_url"] != post["photo_url"]  # cropped by box
    # posting the same fit again merges (worn twice), never duplicates
    out = closet.add_from_fit("u_c", "http://localhost:8000/static/uploads/again.jpg", None, post["tagged"])
    assert out["added"] == [] and len(out["merged"]) == 2
    assert all(len(m["worn_in"]) == 2 for m in out["merged"]) and len(store.list("closet_items", user_id="u_c")) == 2


def test_fit_check_hook_never_fails_the_post(client, monkeypatch):
    from app.commerce import fitcheck

    def boom(*a, **k):
        raise RuntimeError("closet exploded")

    monkeypatch.setattr("app.ai.closet.add_from_fit_later", boom)
    r = client.post("/fitcheck", json={"user_id": "u_c", "photo_url": "https://x/fit.jpg"})
    assert r.status_code == 200, r.text


def test_add_from_fit_runs_in_the_background(client, monkeypatch):
    from app.ai import closet, service

    spawned = []
    monkeypatch.setattr(service, "_spawn", lambda fn: spawned.append(fn))
    closet.add_from_fit_later("u_c", "https://x/fit.jpg", [{"label": "red cap", "category": "accessory", "color": "red"}])
    assert len(spawned) == 1
    spawned[0]()
    from app.store import store

    assert [i["label"] for i in store.list("closet_items", user_id="u_c")] == ["red cap"]


# ---------- PATCH / reshoot ----------

def test_patch_edits_fields_and_product_link(client):
    from app.store import store

    store.put("products", PRODUCT["id"], PRODUCT)
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()["added"][1]
    assert item["product_id"] is None
    r = client.patch(f"/closet/u_c/{item['id']}", json={"label": "stussy tee", "brand": "Stüssy", "color": "off white"})
    assert r.status_code == 200, r.text
    got = r.json()
    assert (got["label"], got["brand"], got["color"]) == ("stussy tee", "Stüssy", "off white")
    assert got["display_image_url"] == item["display_image_url"]  # a label edit doesn't touch the picture
    # link to a catalog product: the picture does not change (sprint-3 §1.2)
    got = client.patch(f"/closet/u_c/{item['id']}", json={"product_id": PRODUCT["id"]}).json()
    assert got["product_id"] == PRODUCT["id"] and got["display_image_url"] == item["crop_image_url"] == got["image_url"]
    assert got["match_confidence"] == 1.0 and got["catalog_image_url"] == PRODUCT["image_url"]
    # clear it: still the clean shot / crop
    got = client.patch(f"/closet/u_c/{item['id']}", json={"product_id": None}).json()
    assert got["product_id"] is None and got["catalog_image_url"] is None and got["match_confidence"] is None
    assert got["display_image_url"] == item["crop_image_url"] == got["image_url"]
    assert store.get("closet_items", item["id"])["display_image_url"] == item["crop_image_url"]


def test_patch_validation_and_ownership(client):
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()["added"][0]
    assert client.patch(f"/closet/u_c/{item['id']}", json={"category": "hat"}).status_code == 422
    assert client.patch(f"/closet/u_c/{item['id']}", json={"product_id": "nope:1"}).status_code == 422
    assert client.patch(f"/closet/u_c/{item['id']}", json={"category": "accessory"}).json()["category"] == "accessory"
    assert client.patch(f"/closet/u_other/{item['id']}", json={"label": "x"}).status_code == 403
    assert client.patch("/closet/u_c/ci_missing", json={"label": "x"}).status_code == 404
    assert client.post(f"/closet/u_other/{item['id']}/reshoot").status_code == 403
    assert client.post("/closet/u_c/ci_missing/reshoot").status_code == 404


def test_reshoot_regenerates_the_clean_shot(client, monkeypatch):
    from app.ai import closet

    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "outfit"}, files=_files(1)).json()["added"][0]
    assert item["display_image_url"] == item["crop_image_url"]  # image AI off at upload time
    shots = []
    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    monkeypatch.setattr(closet, "gemini_image", lambda p, urls: shots.append(urls) or b"shot")
    got = client.post(f"/closet/u_c/{item['id']}/reshoot").json()
    assert shots == [[item["crop_image_url"]]]
    assert got["display_image_url"].endswith("-clean.png") and got["image_url"] == got["display_image_url"]
    assert got["crop_image_url"] == item["crop_image_url"]


def test_reshoot_of_a_matched_item_never_uses_the_catalog_photo(client, monkeypatch):
    from app.ai import closet
    from app.store import store

    store.put("products", PRODUCT["id"], PRODUCT)
    _tagger(monkeypatch, {"label": "black baby tee", "category": "top", "color": "black", "pattern": "solid", "formality": 2})
    item = client.post("/closet/upload", data={"user_id": "u_c", "kind": "piece"}, files=_files(1)).json()["added"][0]
    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    monkeypatch.setattr(closet, "gemini_image", lambda p, u: b"shot")
    got = client.post(f"/closet/u_c/{item['id']}/reshoot").json()
    assert got["display_image_url"].endswith("-clean.png") and got["display_image_url"] != PRODUCT["image_url"]


# ---------- prompts / pair ----------

def test_prompts_ask_for_every_garment_and_brand():
    from app.ai import prompts

    assert '"brand"' in prompts.TAGGER and prompts.TAGGER_VERSION == "v3"
    assert '"brand"' in prompts.DIGITIZE and "accessory" in prompts.DIGITIZE and prompts.DIGITIZE_VERSION == "v3"
    for word in ("mirror selfie", "shoes", "watch", "bag", "cap", "Never collapse"):
        assert word in prompts.DIGITIZE
    assert prompts.PAIR_VERSION == "v5" and "brand" in prompts.PAIR


def test_pair_closet_json_includes_brand(client, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(service, "text_mock", lambda: False)
    # a bottom: a top can't "pair with" another top any more (same-category pairs are dropped by the validator)
    store.put("closet_items", "ci_b", {"id": "ci_b", "user_id": "u_c", "image_url": "https://x/t.jpg", "category": "bottom",
                                       "color": "black", "pattern": "solid", "style_tags": [], "formality": 2,
                                       "label": "black cargos", "brand": "Stüssy"})
    store.put("products", PRODUCT["id"], PRODUCT)
    seen = {}

    def fake_ai(prompt, **kw):
        seen["prompt"] = prompt
        return [{"product_id": PRODUCT["id"], "score": 0.9, "reason": "goes with your Stüssy cargos", "pairs_with": ["ci_b"]}]

    monkeypatch.setattr(service, "ai_json", fake_ai)
    out = service.pair("u_c", [PRODUCT["id"]], k=1)
    assert '"brand": "St\\u00fcssy"' in seen["prompt"] or "Stüssy" in seen["prompt"]
    assert out and "St" in out[0].reason
