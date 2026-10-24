"""Digitize wardrobe (one photo -> several cropped closet items) and body scan (photo + height -> measurements)."""
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


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("users", "u_s", {"id": "u_s", "display_name": "S", "price_ranges": {}, "friends": []})
    return TestClient(app)


# ---------- boxes and crops ----------

def test_normalize_box_accepts_fractions_thousandths_and_pixels():
    from app.ai.digitize import normalize_box

    assert normalize_box([0.1, 0.2, 0.5, 0.9], 400, 200) == (0.1, 0.2, 0.5, 0.9)
    assert normalize_box([100, 200, 500, 900], 400, 200) == (0.1, 0.2, 0.5, 0.9)      # 0-1000
    assert normalize_box([400, 200, 2000, 1800], 4000, 2000) == (0.1, 0.1, 0.5, 0.9)  # pixels
    assert normalize_box([0.5, 0.9, 0.1, 0.2], 400, 200) == (0.1, 0.2, 0.5, 0.9)      # swapped corners
    assert normalize_box(None, 400, 200) is None and normalize_box(["a", 1, 2, 3], 400, 200) is None
    assert normalize_box([0.1, 0.1, 0.12, 0.9], 400, 200) is None                       # a sliver


def test_crop_returns_that_part_of_the_photo(tmp_path):
    from PIL import Image

    from app.ai.digitize import crop

    p = tmp_path / "pile.jpg"
    p.write_bytes(_jpeg())
    left = Image.open(io.BytesIO(crop(p, [0.0, 0.0, 0.4, 1.0])))
    assert left.getpixel((5, left.height // 2))[0] < 40  # black side
    assert crop(p, "nope") is None and crop(tmp_path / "missing.jpg", [0, 0, 1, 1]) is None


# ---------- /closet/digitize ----------

def test_digitize_makes_one_cropped_item_per_garment(client):
    from app.store import store

    r = client.post("/closet/digitize", data={"user_id": "u_s"},
                    files={"file": ("pile.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    items = r.json()
    assert [i["label"] for i in items] == ["black cargo pants", "white baby tee"]
    assert {i["category"] for i in items} == {"bottom", "top"}
    urls = [i["image_url"] for i in items]
    assert len(set(urls)) == 2 and all("/static/uploads/" in u and u.endswith(".jpg") for u in urls)
    assert len(store.list("closet_items", user_id="u_s")) == 2
    # the crops are real files served under /static
    from PIL import Image
    got = client.get("/static/uploads/" + urls[0].rsplit("/", 1)[1])
    assert got.status_code == 200 and Image.open(io.BytesIO(got.content)).width < 400


def test_digitize_twice_flags_duplicates(client):
    first = client.post("/closet/digitize", data={"user_id": "u_s"},
                        files={"file": ("a.jpg", _jpeg(), "image/jpeg")}).json()
    again = client.post("/closet/digitize", data={"user_id": "u_s"},
                        files={"file": ("b.jpg", _jpeg(), "image/jpeg")}).json()
    assert {i["duplicate_of"] for i in again} == {i["id"] for i in first}


def test_digitize_without_detections_tags_the_whole_photo(client, monkeypatch):
    from app.ai import digitize

    monkeypatch.setattr(digitize, "detect", lambda url: [])
    r = client.post("/closet/digitize", data={"user_id": "u_s"},
                    files={"file": ("one.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200 and len(r.json()) == 1


def test_digitize_without_boxes_keeps_the_whole_photo(client, monkeypatch):
    from app.ai import digitize

    monkeypatch.setattr(digitize, "detect", lambda url: [
        {"label": "grey hoodie", "category": "top", "color": "grey", "pattern": "solid", "formality": "x"}])
    items = client.post("/closet/digitize", data={"user_id": "u_s"},
                        files={"file": ("h.jpg", _jpeg(), "image/jpeg")}).json()
    assert len(items) == 1 and items[0]["formality"] == 3 and items[0]["label"] == "grey hoodie"


def test_digitize_rejects_non_images(client):
    r = client.post("/closet/digitize", data={"user_id": "u_s"}, files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 415


def test_digitize_ai_down_is_a_plain_502(client, monkeypatch):
    from app.ai import digitize

    def down(url):
        raise RuntimeError("provider 529 request_id=abc")

    monkeypatch.setattr(digitize, "detect", down)
    r = client.post("/closet/digitize", data={"user_id": "u_s"}, files={"file": ("p.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 502 and "abc" not in r.text


# ---------- body scan ----------

def test_body_scan_saves_photo_and_profile_mock_uses_formula(client):
    from app.store import store

    r = client.post("/users/u_s/body-scan", data={"height_cm": "178", "weight_kg": "72"},
                    files={"file": ("me.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    prof = body["body_profile"]
    assert prof["source"] == "estimate" and prof["height_cm"] == 178 and prof["weight_kg"] == 72
    assert prof["waist_in"] and prof["inseam_in"] and prof["chest_in"] is None
    user = store.get("users", "u_s")
    assert user["body_photo_url"] == body["body_photo_url"] and user["body_profile"] == prof


def test_body_scan_uses_ai_numbers_inside_human_ranges(monkeypatch):
    from app.ai import body_scan

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", lambda prompt, **k: {
        "full_body_visible": True, "build": "Athletic", "chest_in": 40.2, "waist_in": 31.3,
        "hip_in": 400, "inseam_in": "32", "note": "long legs, pick longer inseams."})
    prof = body_scan.scan("https://x/me.jpg", 180, 75)
    assert prof["source"] == "ai" and prof["build"] == "athletic"
    assert (prof["chest_in"], prof["waist_in"], prof["inseam_in"]) == (40.0, 31.5, 32.0)
    assert prof["hip_in"] is None  # 400 in is not a hip
    assert prof["note"] == "Long legs, pick longer inseams"


def test_body_scan_not_full_body_falls_back_and_says_so(monkeypatch):
    from app.ai import body_scan

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", lambda prompt, **k: {"full_body_visible": False, "waist_in": 30})
    prof = body_scan.scan("https://x/selfie.jpg", 170)
    assert prof["source"] == "estimate" and prof["full_body"] is False and "full-body" in prof["note"]
    assert prof["waist_in"] is None and prof["inseam_in"]  # no weight: no waist formula


def test_body_scan_ai_down_still_returns_a_profile(monkeypatch):
    from app.ai import body_scan

    def down(*a, **k):
        raise RuntimeError("overloaded")

    monkeypatch.setattr(body_scan, "text_mock", lambda: False)
    monkeypatch.setattr(body_scan, "ai_json", down)
    assert body_scan.scan("https://x/me.jpg", 170, 60)["source"] == "estimate"


@pytest.mark.parametrize("height, weight", [("90", "70"), ("170", "10")])
def test_body_scan_rejects_impossible_numbers(client, height, weight):
    r = client.post("/users/u_s/body-scan", data={"height_cm": height, "weight_kg": weight},
                    files={"file": ("me.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 422


def test_size_falls_back_to_the_body_scan(client):
    from app.store import store

    store.put("products", "hm:jeans:blue", {
        "id": "hm:jeans:blue", "retailer": "hm", "brand": "H&M", "name": "Baggy Jeans", "category": "bottom",
        "price_usd": 30.0, "colors": ["blue"], "image_url": "https://img/j.jpg", "product_url": "https://hm.com/j",
        "sizes": ["28/30", "30/32", "32/32", "34/32"], "in_stock": True})
    assert client.post("/size", json={"product_id": "hm:jeans:blue", "user_id": "u_s"}).status_code == 422
    client.post("/users/u_s/body-scan", data={"height_cm": "178", "weight_kg": "72"},
                files={"file": ("me.jpg", _jpeg(), "image/jpeg")})
    r = client.post("/size", json={"product_id": "hm:jeans:blue", "user_id": "u_s"})
    assert r.status_code == 200, r.text
    assert r.json()["size"] in {"28/30", "30/32", "32/32", "34/32"}
    # explicit numbers still win, and old clients (no user_id) work as before
    assert client.post("/size", json={"product_id": "hm:jeans:blue", "height_cm": 160,
                                      "weight_kg": 50}).status_code == 200


def test_editing_the_profile_keeps_the_body_scan(client):
    from app.store import store

    client.post("/users/u_s/body-scan", data={"height_cm": "170"}, files={"file": ("me.jpg", _jpeg(), "image/jpeg")})
    r = client.patch("/users/u_s", json={"display_name": "Sam"})
    assert r.status_code == 200, r.text
    assert store.get("users", "u_s")["body_profile"]["height_cm"] == 170


# ---------- uploads drop EXIF (GPS) and come out upright ----------

def _jpeg_with_gps_and_rotation() -> bytes:
    from PIL import Image

    im = Image.new("RGB", (300, 100), "red")  # stored landscape; EXIF says "rotate 90 to show it"
    exif = Image.Exif()
    exif[0x0112] = 6                                                # Orientation: rotate 90 CW
    exif[0x8825] = {1: "N", 2: (37.0, 46.0, 30.0), 3: "W", 4: (122.0, 25.0, 9.0)}  # GPSInfo
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_uploads_strip_gps_and_apply_rotation(client):
    from PIL import Image

    raw = _jpeg_with_gps_and_rotation()
    assert Image.open(io.BytesIO(raw)).getexif().get(0x8825)  # the test photo really has GPS
    r = client.post("/users/u_s/body-photo", files={"file": ("me.jpg", raw, "image/jpeg")})
    url = r.json()["body_photo_url"]
    saved = Image.open(io.BytesIO(client.get("/static/uploads/" + url.rsplit("/", 1)[1]).content))
    assert not saved.getexif()          # no GPS, no EXIF at all
    assert saved.size == (100, 300)     # rotation applied, so it shows upright everywhere


def test_unreadable_images_are_kept_as_uploaded():
    from app.ai.router import _clean_image

    data, ext = _clean_image(b"not really a heic", "image/heic")
    assert (data, ext) == (b"not really a heic", ".heic")


# ---------- typed measurements: PATCH /users/{id}/body-profile ----------

def test_typed_measurements_are_saved_in_inches_and_marked_manual(client):
    r = client.patch("/users/u_s/body-profile", json={"height_cm": 175, "weight_kg": 70, "waist_cm": 81.3,
                                                      "inseam_cm": 81, "shoe_us": 10, "fit": "oversized",
                                                      "usual_sizes": {"top": "M"}})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["height_cm"], p["waist_in"], p["inseam_in"], p["shoe_us"], p["fit"]) == (175, 32.0, 32.0, 10, "oversized")
    assert p["usual_sizes"] == {"top": "M"} and p["source"] == "manual"
    assert set(p["manual"]) >= {"height_cm", "waist_in", "inseam_in"}
    assert client.get("/users/u_s").json()["body_profile"]["waist_in"] == 32.0  # any device can read it back


def test_patch_only_changes_what_is_sent_and_null_clears(client):
    client.patch("/users/u_s/body-profile", json={"height_cm": 175, "weight_kg": 70})
    p = client.patch("/users/u_s/body-profile", json={"weight_kg": None, "chest_cm": 96}).json()
    assert p["height_cm"] == 175 and p["weight_kg"] is None and p["chest_in"] == 38.0
    assert "weight_kg" not in p["manual"]


@pytest.mark.parametrize("bad", [{"height_cm": 50}, {"waist_cm": 400}, {"fit": "baggy"}, {"usual_sizes": {"hat": "M"}}])
def test_patch_rejects_impossible_values(client, bad):
    assert client.patch("/users/u_s/body-profile", json=bad).status_code == 422


def test_a_scan_keeps_what_the_user_typed(client):
    client.patch("/users/u_s/body-profile", json={"height_cm": 180, "weight_kg": 75, "waist_cm": 76.2,
                                                  "usual_sizes": {"top": "L"}})
    p = client.post("/users/u_s/body-scan", data={"height_cm": "178", "weight_kg": "72"},
                    files={"file": ("me.jpg", _jpeg(), "image/jpeg")}).json()["body_profile"]
    assert p["waist_in"] == 30.0 and p["height_cm"] == 180  # typed values win over the scan
    assert p["usual_sizes"] == {"top": "L"} and p["inseam_in"]  # preferences kept, scan filled the rest


def _tee(store):
    store.put("products", "hm:tee:black", {
        "id": "hm:tee:black", "retailer": "hm", "brand": "H&M", "name": "Tee", "category": "top", "price_usd": 10.0,
        "colors": ["black"], "image_url": "https://img/t.jpg", "product_url": "https://hm.com/t",
        "sizes": ["S", "M", "L"], "in_stock": True})


def test_size_uses_the_saved_fit_and_falls_back_to_the_usual_size(client):
    from app.store import store

    _tee(store)
    client.patch("/users/u_s/body-profile", json={"usual_sizes": {"top": "m"}})
    r = client.post("/size", json={"product_id": "hm:tee:black", "user_id": "u_s"})
    assert r.status_code == 200 and r.json() == {"size": "M", "confidence": "medium", "reason": "your usual size"}
    client.patch("/users/u_s/body-profile", json={"height_cm": 185, "weight_kg": 80, "fit": "oversized"})
    slim = client.post("/size", json={"product_id": "hm:tee:black", "user_id": "u_s", "fit": "slim"}).json()
    saved = client.post("/size", json={"product_id": "hm:tee:black", "user_id": "u_s"}).json()
    assert slim["size"] in {"S", "M", "L"} and saved["size"] in {"S", "M", "L"}
    order = ["S", "M", "L"]
    assert order.index(saved["size"]) >= order.index(slim["size"])  # saved "oversized" sizes up vs explicit slim
