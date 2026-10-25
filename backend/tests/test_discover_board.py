"""Discover board (Pinterest pins + products + Inspo posts, two columns in the app), pin Similar, pin ingest,
and the one-time post-visibility backfill."""
import json
import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

TAGS = [{"label": "baggy jeans", "category": "bottom", "color": "blue", "style_tags": ["y2k"]},
        {"label": "baby tee", "category": "top", "color": "white", "style_tags": ["y2k"]}]


def _raw(pid, **kw):
    return {"id": pid, "type": "pin", "grid_title": f"look {pid}", "url": f"https://www.pinterest.com/pin/{pid}/",
            "dominant_color": "#aabbcc",
            "images": {"736x": {"url": f"https://i.pinimg.com/736x/{pid}.jpg", "width": 736, "height": 980}}, **kw}


def _pin(pid, style="y2k", dept="women", tagged=TAGS):
    from app.commerce.discover import normalize_pin
    return {**normalize_pin(_raw(pid), style, dept), "tagged": tagged}


def _product(pid, style="y2k", dept="women"):
    return {"id": pid, "retailer": "hm", "name": pid, "brand": "H&M", "category": "top", "price_usd": 20.0,
            "colors": ["white"], "style_tags": [style], "department": dept, "in_stock": True,
            "sizes": [{"name": "M", "in_stock": True}], "image_url": "https://x/p.jpg", "product_url": "https://x",
            "source": "ingest"}


def test_normalize_pin_keeps_size_link_and_drops_ads_and_videos():
    from app.commerce.discover import normalize_pin
    p = normalize_pin(_raw("1"), "y2k", "women")
    assert (p["id"], p["w"], p["h"], p["style"], p["department"]) == ("pin:1", 736, 980, "y2k", "women")
    assert p["image_url"].startswith("https://i.pinimg.com/") and p["pin_url"].endswith("/pin/1/")
    assert p["title"] == "look 1" and p["tagged"] == []
    assert normalize_pin(_raw("2", description="#ad shop this look"), "y2k", "women") is None
    assert normalize_pin(_raw("3", type="video"), "y2k", "women") is None
    assert normalize_pin({**_raw("4"), "images": {}}, "y2k", "women") is None
    assert normalize_pin({"demo": True}, "y2k", "women") is None  # quota placeholder
    sf = normalize_pin({"id": "9", "type": "pin", "gridTitle": "fit 9", "isVideo": "False", "width": 1000, "height": 1500,
                        "dominantColor": "#112233", "url": "https://www.pinterest.com/pin/9/",
                        "imageUrls": {"736x": "https://i.pinimg.com/736x/9.jpg"}}, "grunge", "men")
    assert (sf["image_url"], sf["w"], sf["h"], sf["title"], sf["dominant_color"]) == \
        ("https://i.pinimg.com/736x/9.jpg", 1000, 1500, "fit 9", "#112233")
    assert normalize_pin({"id": "8", "isVideo": "True", "width": 1, "height": 1,
                          "imageUrls": {"736x": "https://i.pinimg.com/736x/8.jpg"}}, "grunge", "men") is None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    monkeypatch.setattr(store, "root", Path(tmp_path))
    store.put("users", "u_w", {"id": "u_w", "display_name": "W", "shop_for": "women", "style_text": "y2k fits",
                               "friends": []})
    for i in range(6):
        store.put("pins", f"pin:w{i}", _pin(f"w{i}"))
    store.put("pins", "pin:m0", _pin("m0", dept="men"))
    store.put("pins", "pin:g0", _pin("g0", style="grunge"))
    store.put("pins", "pin:bare", _pin("bare", tagged=[]))  # untagged: never on the board
    for i in range(3):
        store.put("products", f"p{i}", _product(f"p{i}"))
    store.put("products", "pm", _product("pm", dept="men"))
    store.put("fitcheck_posts", "fc_pub", {"id": "fc_pub", "user_id": "u_x", "photo_url": "https://x/f.jpg",
                                           "tagged": TAGS, "created_at": "2026-10-25T10:00:00+00:00",
                                           "visibility": "public", "likes": [], "comments": []})
    store.put("fitcheck_posts", "fc_priv", {"id": "fc_priv", "user_id": "u_y", "photo_url": "https://x/g.jpg",
                                            "tagged": TAGS, "created_at": "2026-10-25T10:01:00+00:00",
                                            "visibility": "friends", "likes": [], "comments": []})
    return TestClient(app)


def test_board_weaves_pins_products_posts_for_the_viewer(client):
    r = client.get("/discover/board", params={"user_id": "u_w", "limit": 60})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["styles"] == ["y2k"]  # from the style words the user typed
    kinds = [i["kind"] for i in body["items"]]
    assert kinds[:4] == ["pin", "pin", "product", "pin"]  # the pattern leads with pins
    pins = [i["pin"]["id"] for i in body["items"] if i["kind"] == "pin"]
    assert sorted(pins) == [f"pin:w{i}" for i in range(6)]  # women's y2k, tagged only: no men's, grunge or bare pin
    assert {i["product"]["id"] for i in body["items"] if i["kind"] == "product"} == {"p0", "p1", "p2"}
    posts = [i["post"]["id"] for i in body["items"] if i["kind"] == "post"]
    assert posts == ["fc_pub"]  # a friends-only post of a non-friend stays hidden
    assert body["next_offset"] is None


def test_board_style_chip_paging_and_errors(client):
    g = client.get("/discover/board", params={"user_id": "u_w", "style": "grunge"}).json()
    assert [i["pin"]["id"] for i in g["items"] if i["kind"] == "pin"] == ["pin:g0"]
    first = client.get("/discover/board", params={"user_id": "u_w", "limit": 4}).json()
    second = client.get("/discover/board", params={"user_id": "u_w", "limit": 4, "offset": 4}).json()
    ids = lambda b: [i[i["kind"]]["id"] for i in b["items"]]  # noqa: E731
    assert first["next_offset"] == 4 and not set(ids(first)) & set(ids(second))  # stable paging, no repeats
    assert client.get("/discover/board", params={"user_id": "u_w", "style": "goth"}).status_code == 422


def test_pin_similar_uses_the_pins_tags(client, monkeypatch):
    from app.ai import similar_look
    seen = {}

    def fake(viewer, tagged, keep=None):
        seen.update(viewer=viewer, tagged=tagged)
        return [{"tag": t, "closet": [], "products": []} for t in tagged]
    monkeypatch.setattr(similar_look, "similar_look", fake)
    r = client.get("/discover/pins/pin:w0/similar", params={"user_id": "u_w"})
    assert r.status_code == 200 and len(r.json()) == 2
    assert seen == {"viewer": "u_w", "tagged": TAGS}
    assert client.get("/discover/pins/pin:nope/similar", params={"user_id": "u_w"}).status_code == 404


def test_ingest_pins_dedupes_tags_keeps_outfits_and_loads(tmp_path, monkeypatch):
    import gzip
    from app.ai import service
    from app.store import store
    from scripts import ingest_pins
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    monkeypatch.setattr(store, "root", Path(tmp_path))
    raw = tmp_path / "raw"
    raw.mkdir()
    with gzip.open(raw / "pinterest_y2k_women_20261025.json.gz", "wt") as f:
        json.dump([_raw("a"), _raw("a"), _raw("b"), _raw("c", description="#ad")], f)
    monkeypatch.setattr(ingest_pins, "RAW", raw)
    (tmp_path / "seed").mkdir()  # not tmp_path/pins.json: that's the store's own "pins" collection file
    monkeypatch.setattr(ingest_pins, "SNAPSHOT", tmp_path / "seed" / "pins.json")
    monkeypatch.setattr(service, "tag_fit", lambda url: TAGS if url.endswith("/a.jpg") else TAGS[:1])
    assert ingest_pins.main(["--yes", "--workers", "1"]) == 0
    pins = json.loads((tmp_path / "seed" / "pins.json").read_text())
    assert [p["id"] for p in pins] == ["pin:a"]  # b has 1 piece (not an outfit), c is an ad, a de-duped
    assert ingest_pins.main(["--load"]) == 0 and store.get("pins", "pin:a")["tagged"] == TAGS


def test_backfill_post_visibility(tmp_path, monkeypatch):
    from app.store import store
    from scripts import backfill_post_visibility as bf
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    monkeypatch.setattr(store, "root", Path(tmp_path))
    store.put("fitcheck_posts", "old", {"id": "old", "user_id": "u", "visibility": "friends",
                                        "created_at": "2026-10-25T09:00:00+00:00"})
    store.put("fitcheck_posts", "chosen", {"id": "chosen", "user_id": "u", "visibility": "friends",
                                           "created_at": "2026-10-25T12:30:00+00:00"})
    bf.main([])  # dry run
    assert store.get("fitcheck_posts", "old")["visibility"] == "friends"
    bf.main(["--yes"])
    assert store.get("fitcheck_posts", "old")["visibility"] == "public"
    assert store.get("fitcheck_posts", "chosen")["visibility"] == "friends"  # picked after #103: kept
