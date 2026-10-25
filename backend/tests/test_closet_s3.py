"""Sprint-3 §1 (Adam): every garment from every closet photo (1.1), no catalog photos on owned pieces + a
strict catalog match (1.2), outfits + pieces (1.3), and the clean shot from the best source photo."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


_SHOT = iter(range(10**6))


def _jpeg(w=400, h=200) -> bytes:
    """Left half dark, right half light: two 'garments' for the mock detector's two boxes. Every call is a
    different photo (block texture), so closet de-duplication of the same photo doesn't merge them."""
    import random

    from PIL import Image

    rnd = random.Random(next(_SHOT))
    small = Image.new("RGB", (16, 8))
    small.putdata([(rnd.randint(0, 70) if x < 8 else rnd.randint(185, 255),) * 3
                   for y in range(8) for x in range(16)])
    im = small.resize((w, h), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def _files(n, name="files"):
    return [(name, (f"p{i}.jpg", _jpeg(), "image/jpeg")) for i in range(n)]


def _garment(label, category, color, box, pattern="solid"):
    return {"label": label, "category": category, "color": color, "pattern": pattern, "formality": 2,
            "style_tags": [], "brand": None, "box": box}


FOUR = [_garment("black cargo pants", "bottom", "black", [0, 0.5, 0.5, 1]),
        _garment("white baby tee", "top", "white", [0, 0, 0.5, 0.5]),
        _garment("brown leather jacket", "outerwear", "brown", [0.5, 0, 1, 0.5]),
        _garment("white sneakers", "shoes", "white", [0.5, 0.5, 1, 1])]

PRODUCT = {"id": "hm:tee:black", "retailer": "hm", "name": "Black Baby Tee", "brand": "H&M", "category": "top",
           "price_usd": 9.99, "colors": ["black"], "sizes": [{"name": "M", "in_stock": True}], "in_stock": True,
           "image_url": "https://image.hm.com/tee.jpg", "product_url": "https://hm.com/tee", "style_tags": ["y2k"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("users", "u_s3", {"id": "u_s3", "display_name": "S3", "price_ranges": {}, "friends": []})
    return TestClient(app)


def _detect(monkeypatch, found):
    from app.ai import digitize

    monkeypatch.setattr(digitize, "detect", lambda url: [dict(d) for d in found])


# ---------- 1.1 every garment ----------

def test_single_file_upload_without_kind_digitizes_every_garment(client, monkeypatch):
    from app.store import store

    _detect(monkeypatch, FOUR)
    r = client.post("/closet/upload", data={"user_id": "u_s3"}, files={"file": ("a.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "black cargo pants"  # legacy shape: one item (the first)
    items = store.list("closet_items", user_id="u_s3")
    assert len(items) == 4 and {i["label"] for i in items} == {g["label"] for g in FOUR}


def test_kind_outfit_returns_all_four(client, monkeypatch):
    _detect(monkeypatch, FOUR)
    body = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()
    assert len(body["added"]) == 4 and body["merged"] == [] and body["skipped"] == 0
    assert len(body["outfits"]) == 1 and body["outfits"][0]["piece_ids"] == [a["id"] for a in body["added"]]


# ---------- 1.2 no catalog photos, strict match ----------

def test_owned_pieces_never_show_a_catalog_photo(client, monkeypatch):
    from app.ai import closet
    from app.store import store

    store.put("products", PRODUCT["id"], PRODUCT)
    _detect(monkeypatch, [_garment("black baby tee", "top", "black", [0, 0, 1, 1])])
    item = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()["added"][0]
    assert item["product_id"] == PRODUCT["id"] and item["brand"] is None  # catalog match never sets the brand
    assert item["display_image_url"] == item["crop_image_url"] == item["image_url"] != PRODUCT["image_url"]
    # with image AI on: a clean shot generated from the user's crop, still never the catalog photo
    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    monkeypatch.setattr(closet, "gemini_image", lambda p, urls: b"shot")
    got = client.post(f"/closet/u_s3/{item['id']}/reshoot").json()
    assert got["display_image_url"].endswith("-clean.png") and got["display_image_url"] != PRODUCT["image_url"]
    assert got["clean_source_photo_url"] == item["worn_in"][0]["photo_url"] and got["clean_source_box"] == [0, 0, 1, 1]
    # linking a product by hand does not change the picture either
    got = client.patch(f"/closet/u_s3/{item['id']}", json={"product_id": PRODUCT["id"]}).json()
    assert got["display_image_url"] != PRODUCT["image_url"]


@pytest.mark.parametrize("label,color,pattern,expected", [
    ("black baby tee", "black", "solid", True),           # nouns + colour + pattern agree
    ("black tee", "black", "solid", True),                # fewer words, all agree
    ("black baby tee", "white", "solid", False),          # colour disagrees
    ("black baby tee", "black", "striped", False),        # pattern disagrees
    ("black corduroy shirt", "black", "solid", False),    # a noun the product doesn't have
    ("black oversized tee", "black", "solid", False),     # extra descriptor missing from the product
    ("navy baby tee", "navy", "solid", False),            # neutral-ish colour is not the same colour
])
def test_strict_match_bar(label, color, pattern, expected):
    from app.ai import closet

    item = {"label": label, "category": "top", "color": color, "pattern": pattern}
    assert closet.strict_match(item, PRODUCT) is expected


def test_pattern_in_product_name_blocks_a_solid_piece():
    from app.ai import closet

    striped = {**PRODUCT, "id": "hm:tee:striped", "name": "Black Striped Baby Tee"}
    assert closet.strict_match({"label": "black baby tee", "category": "top", "color": "black", "pattern": "solid"}, striped) is False
    assert closet.strict_match({"label": "black baby tee", "category": "top", "color": "black", "pattern": "striped"}, striped) is True


def test_no_match_means_no_product_id(client, monkeypatch):
    from app.store import store

    store.put("products", PRODUCT["id"], PRODUCT)
    _detect(monkeypatch, [_garment("brown corduroy shirt", "top", "brown", [0, 0, 1, 1])])
    item = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()["added"][0]
    assert item["product_id"] is None and item["catalog_image_url"] is None and item["brand"] is None


# ---------- 1.3 outfits + pieces ----------

def test_outfit_upload_creates_an_outfit_and_links_pieces(client, monkeypatch):
    from app.store import store

    _detect(monkeypatch, FOUR)
    body = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()
    outfit = body["outfits"][0]
    assert outfit["id"].startswith("of_") and outfit["user_id"] == "u_s3" and outfit["source"] == "closet"
    assert outfit["photo_url"] == body["added"][0]["worn_in"][0]["photo_url"] and outfit["created_at"]
    assert all(a["outfit_id"] == outfit["id"] for a in body["added"])
    assert store.get("outfits", outfit["id"])["piece_ids"] == [a["id"] for a in body["added"]]
    r = client.get("/closet/u_s3/outfits")
    assert r.status_code == 200, r.text
    got = r.json()
    assert len(got) == 1 and got[0]["id"] == outfit["id"]
    assert [p["id"] for p in got[0]["pieces"]] == outfit["piece_ids"] and got[0]["pieces"][0]["label"] == "black cargo pants"


def test_outfits_list_newest_first_and_merged_pieces_keep_their_first_outfit(client, monkeypatch):
    from app.ai import closet

    _detect(monkeypatch, FOUR)
    first = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()
    monkeypatch.setattr(closet, "_now", lambda: "2099-01-01T00:00:00+00:00")
    # a different photo of the same four pieces (the identical photo is one outfit: test_closet_social_s4)
    second = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"},
                         files=[("files", ("q.jpg", _jpeg(401, 200), "image/jpeg"))]).json()
    assert second["added"] == [] and len(second["merged"]) == 4 and len(second["outfits"]) == 1
    got = client.get("/closet/u_s3/outfits").json()
    assert [o["id"] for o in got] == [second["outfits"][0]["id"], first["outfits"][0]["id"]]
    assert got[0]["piece_ids"] == got[1]["piece_ids"]  # the same four pieces, worn in both
    assert all(p["outfit_id"] == first["outfits"][0]["id"] for p in got[0]["pieces"])


def test_delete_outfit_keeps_the_pieces(client, monkeypatch):
    from app.store import store

    _detect(monkeypatch, FOUR)
    body = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()
    oid = body["outfits"][0]["id"]
    assert client.delete(f"/closet/u_other/outfits/{oid}").status_code == 404
    assert client.delete(f"/closet/u_s3/outfits/{oid}").json() == {"deleted": oid}
    assert client.get("/closet/u_s3/outfits").json() == []
    items = store.list("closet_items", user_id="u_s3")
    assert len(items) == 4 and all(i["outfit_id"] is None for i in items)
    assert client.delete(f"/closet/u_s3/outfits/{oid}").status_code == 404


def test_piece_upload_makes_no_outfit(client, monkeypatch):
    from app.ai import service

    monkeypatch.setattr(service, "tag_image", lambda url, hint=None: _garment("red cap", "accessory", "red", None))
    body = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "piece"}, files=_files(1)).json()
    assert body["outfits"] == [] and body["added"][0]["outfit_id"] is None
    assert client.get("/closet/u_s3/outfits").json() == []


def test_fit_check_auto_add_creates_a_fitcheck_outfit(client, monkeypatch):
    from app.ai import service

    ran = []
    monkeypatch.setattr(service, "_spawn", lambda fn: ran.append(fn))
    post = client.post("/fitcheck", data={"user_id": "u_s3", "caption": "fit"},
                       files={"file": ("f.jpg", _jpeg(), "image/jpeg")}).json()
    ran[0]()
    got = client.get("/closet/u_s3/outfits").json()
    assert len(got) == 1 and got[0]["source"] == "fitcheck" and got[0]["photo_url"] == post["photo_url"]
    assert {p["label"] for p in got[0]["pieces"]} == {t["label"] for t in post["tagged"]}
    assert all(p["outfit_id"] == got[0]["id"] for p in got[0]["pieces"])


# ---------- clean shot from the best source photo ----------

def _photo(tmp_path, name, w=400, h=400, blur=False):
    """A photo in DATA_DIR/uploads (so local_static_path resolves it); its public URL."""
    from PIL import Image, ImageFilter

    from app.store import DATA_DIR

    im = Image.new("RGB", (w, h), "white")
    for x in range(0, w, 8):  # fine stripes: sharp unless blurred
        im.paste((0, 0, 0), (x, 0, x + 4, h))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(6))
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    im.save(DATA_DIR / "uploads" / name, "JPEG")
    return f"http://localhost:8000/static/uploads/{name}"


def test_best_source_prefers_whole_then_large_then_sharp(client, tmp_path):
    from app.ai import closet

    small = _photo(tmp_path, "small.jpg")
    big = _photo(tmp_path, "big.jpg")
    cut = _photo(tmp_path, "cut.jpg")
    blurry = _photo(tmp_path, "blurry.jpg", blur=True)
    item = {"worn_in": [
        {"photo_url": small, "box": [0.4, 0.4, 0.6, 0.6]},
        {"photo_url": cut, "box": [0.0, 0.1, 0.9, 0.9]},    # biggest, but touches the left edge: cut off
        {"photo_url": big, "box": [0.1, 0.1, 0.7, 0.7]},
        {"photo_url": "http://localhost:8000/static/uploads/nobox.jpg", "box": None},
    ]}
    assert closet.best_source(item) == (big, [0.1, 0.1, 0.7, 0.7])
    # same box: the sharper photo wins
    item = {"worn_in": [{"photo_url": blurry, "box": [0.1, 0.1, 0.7, 0.7]}, {"photo_url": big, "box": [0.1, 0.1, 0.7, 0.7]}]}
    assert closet.best_source(item) == (big, [0.1, 0.1, 0.7, 0.7])
    assert closet.sharpness(None) == 0.0
    assert closet.best_source({"worn_in": [{"photo_url": "x", "box": None}]}) is None


def test_merge_keeps_the_new_photos_box_and_regenerates_when_it_shows_the_piece_better(client, monkeypatch):
    from app.ai import closet, service
    from app.store import store

    _detect(monkeypatch, [_garment("black cargo pants", "bottom", "black", [0.3, 0.3, 0.6, 0.6])])
    monkeypatch.setattr(closet, "mock_mode", lambda key: False)
    shots = []
    monkeypatch.setattr(closet, "gemini_image", lambda p, urls: shots.append((p, urls)) or b"shot")
    spawned = []
    monkeypatch.setattr(service, "_spawn", lambda fn: spawned.append(fn))
    first = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()["added"][0]
    assert len(shots) == 1 and shots[0][1] == [first["crop_image_url"]]
    assert "as worn in the photo" in shots[0][0] and "same colour, fabric, print, logo and fit" in shots[0][0]
    assert first["clean_source_box"] == [0.3, 0.3, 0.6, 0.6]
    # the same garment, bigger in a second photo
    _detect(monkeypatch, [_garment("black cargo pants", "bottom", "black", [0.1, 0.1, 0.9, 0.9])])
    merged = client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1)).json()["merged"][0]
    assert [w["box"] for w in merged["worn_in"]] == [[0.3, 0.3, 0.6, 0.6], [0.1, 0.1, 0.9, 0.9]]
    assert len(spawned) == 1  # a background regeneration was queued
    spawned[0]()
    saved = store.get("closet_items", first["id"])
    assert saved["clean_source_photo_url"] == merged["worn_in"][1]["photo_url"] and saved["clean_source_box"] == [0.1, 0.1, 0.9, 0.9]
    assert len(shots) == 2 and shots[1][1] != [first["crop_image_url"]]  # cropped from the new, better photo
    assert saved["display_image_url"] != first["display_image_url"] and saved["display_image_url"].endswith("-clean.png")
    # a worse photo (smaller box) queues nothing
    _detect(monkeypatch, [_garment("black cargo pants", "bottom", "black", [0.4, 0.4, 0.5, 0.5])])
    client.post("/closet/upload", data={"user_id": "u_s3", "kind": "outfit"}, files=_files(1))
    assert len(spawned) == 1
