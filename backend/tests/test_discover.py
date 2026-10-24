"""Discover / Home P0s (council D3, D9, D10, D11): soft size ranking on /feed, seeded feed, /search,
/search/styles, /search/photo. Mock AI throughout (no Claude calls)."""
import io
import os

import pytest

os.environ["MOCK_AI"] = "1"


def _p(pid, retailer, name, cat, price, sizes=("S", "M", "L"), **kw):
    return {"id": pid, "retailer": retailer, "name": name, "brand": retailer.upper(), "category": cat,
            "price_usd": price, "sale_price_usd": None, "colors": [], "style_tags": [], "label": "",
            "sizes": [{"name": s, "in_stock": True} for s in sizes], "in_stock": True,
            "image_url": "https://x/y.jpg", "product_url": "https://x", "source": "ingest", **kw}


# 175 cm / 70 kg -> BMI 22.9 -> M (hm: true to size; zara runs small -> L)
PRODUCTS = [
    _p("hm:1:blue", "hm", "Baggy Jeans", "bottom", 30.0, sizes=("XS", "M"), colors=["light blue"],
       style_tags=["y2k", "streetwear"]),
    _p("hm:2:black", "hm", "Slim Jeans", "bottom", 25.0, sizes=("XS",), colors=["black"], style_tags=["minimalist"]),
    _p("zara:3:white", "zara", "Baby Tee", "top", 15.0, sizes=("L",), colors=["white"], style_tags=["y2k"]),
    _p("zara:4:blue", "zara", "Denim Jacket", "outerwear", 60.0, sizes=("S",), colors=["blue"], style_tags=["y2k"]),
    _p("uniqlo:5:white", "uniqlo", "Oxford Shirt", "top", 40.0, sizes=("S", "M"), colors=["white"],
       style_tags=["minimalist", "classic"]),
    _p("hm:6:black", "hm", "Chunky Sneakers", "shoes", 50.0, sizes=("9", "10"), colors=["black"], style_tags=["streetwear"]),
    _p("hm:7:blue", "hm", "Wide Jeans", "bottom", 32.0, sizes=("M",), colors=["blue"], style_tags=["y2k"]),
]
PROFILE = {"height_cm": 175, "weight_kg": 70, "fit": "regular"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    for p in PRODUCTS:
        store.put("products", p["id"], p)
    store.put("users", "u_sized", {"id": "u_sized", "display_name": "S", "price_ranges": {}, "friends": [],
                                   "body_profile": PROFILE, "preferred_stores": ["uniqlo"]})
    store.put("users", "u_plain", {"id": "u_plain", "display_name": "P", "price_ranges": {}, "friends": []})
    return TestClient(app)


def _ids(cards):
    return [c["id"] for c in cards]


# ---------- D3: soft size ranking ----------

def test_feed_without_profile_is_unchanged_and_unsized(client):
    cards = client.get("/feed", params={"user_id": "u_plain", "limit": 10}).json()
    assert len(cards) == len(PRODUCTS)
    assert all(c["your_size"] is None and c["in_your_size"] is False for c in cards)
    assert {"reason", "score", "pairs_with"} <= set(cards[0])


def test_feed_puts_in_your_size_first_then_preferred_store(client):
    cards = client.get("/feed", params={"user_id": "u_sized", "limit": 10}).json()
    by_id = {c["id"]: c for c in cards}
    assert by_id["hm:1:blue"]["your_size"] == "M" and by_id["hm:1:blue"]["in_your_size"]
    assert by_id["zara:3:white"]["your_size"] == "L" and by_id["zara:3:white"]["in_your_size"]  # zara runs small
    assert by_id["hm:2:black"]["your_size"] == "XS" and not by_id["hm:2:black"]["in_your_size"]  # clamped to stock
    assert by_id["hm:6:black"]["your_size"] is None  # shoes need shoe_us
    flags = [c["in_your_size"] for c in cards]
    assert flags == sorted(flags, reverse=True)  # every in-size card before every other
    in_size = [c for c in cards if c["in_your_size"]]
    assert in_size[0]["retailer"] == "uniqlo"  # preferred store boosted within the group
    assert len(cards) == len(PRODUCTS)  # soft: nothing hidden


def test_size_rank_is_stable_and_reads_flat_measurements():
    from app.ai.discover import size_rank

    cards = [{"id": "a", "retailer": "hm", "category": "top", "sizes": ["M"], "name": "A"},
             {"id": "b", "retailer": "hm", "category": "top", "sizes": ["M"], "name": "B"},
             {"id": "c", "retailer": "hm", "category": "top", "sizes": ["XXL"], "name": "C"}]
    out = size_rank({"measurements": PROFILE}, [cards[2], cards[0], cards[1]])
    assert _ids(out) == ["a", "b", "c"]  # a/b keep their order
    assert size_rank(None, cards) == [{**c, "your_size": None, "in_your_size": False} for c in cards]


def test_usual_size_fallback_without_body_numbers():
    from app.ai.discover import your_size

    user = {"body_profile": {"usual_sizes": {"top": "l"}}}
    assert your_size(user, PRODUCTS[2]) == ("L", True)   # zara Baby Tee has L
    assert your_size(user, PRODUCTS[4]) == (None, False)  # uniqlo shirt has no L


# ---------- D9: seeded feed ----------

def test_seeded_feed_starts_with_the_seed_then_lookalikes(client):
    cards = client.get("/feed", params={"user_id": "u_sized", "seed": "hm:1:blue", "limit": 4}).json()
    assert len(cards) == 4
    assert cards[0]["id"] == "hm:1:blue" and cards[0]["reason"] == "The piece you tapped"
    assert cards[0]["in_your_size"] and cards[0]["your_size"] == "M"
    rest = cards[1:]
    # in size + preferred store first, then the closest look-alike (jeans, blue, y2k, hm, in size)
    assert _ids(rest)[:2] == ["uniqlo:5:white", "hm:7:blue"]
    flags = [c["in_your_size"] for c in rest]
    assert flags == sorted(flags, reverse=True)  # size ranking applies to the look-alikes too
    assert all("reason" in c and "in_your_size" in c for c in rest)
    full = client.get("/feed", params={"user_id": "u_plain", "seed": "hm:1:blue", "limit": 10}).json()
    assert [c["category"] for c in full[1:3]] == ["bottom", "bottom"]  # no profile: same category first


def test_seeded_feed_404_and_limit(client):
    assert client.get("/feed", params={"user_id": "u_plain", "seed": "nope"}).status_code == 404
    cards = client.get("/feed", params={"user_id": "u_plain", "seed": "zara:4:blue", "limit": 2}).json()
    assert _ids(cards)[0] == "zara:4:blue" and len(cards) == 2


def test_similarity_signals():
    from app.ai.discover import similarity

    seed = PRODUCTS[0]
    same_kind, _ = similarity(seed, PRODUCTS[6])  # jeans / blue / y2k / hm / price
    other, _ = similarity(seed, PRODUCTS[5])  # sneakers
    assert same_kind > other


# ---------- D10: text search ----------

def test_search_returns_two_sections_size_ranked(client):
    r = client.get("/search", params={"q": "y2k jeans", "user_id": "u_sized"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"query", "vibe", "similar", "goes_with"} and body["query"] == "y2k jeans"
    assert body["vibe"]["source"] == "rules" and "bottom" in body["vibe"]["categories"]
    sim = body["similar"]
    assert sim and sim[0]["id"] in {"hm:1:blue", "hm:7:blue"}  # y2k jeans in your size first
    assert all({"reason", "score", "your_size", "in_your_size"} <= set(c) for c in sim)
    assert "hm:6:black" not in _ids(sim)  # sneakers aren't jeans
    gw = body["goes_with"]
    assert gw and all(c["category"] != "bottom" for c in gw)  # pieces that complete the jeans
    assert all("in_your_size" in c for c in gw)


def test_search_422_on_empty_and_works_without_user(client):
    assert client.get("/search", params={"q": "  "}).status_code == 422
    body = client.get("/search", params={"q": "white shirt"}).json()
    assert body["similar"][0]["id"] in {"uniqlo:5:white", "zara:3:white"}
    assert body["similar"][0]["your_size"] is None


# ---------- D11: style chips + trending ----------

def test_search_styles_counts_tags_and_falls_back_to_catalog(client):
    body = client.get("/search/styles").json()
    assert body["styles"][0] == {"tag": "y2k", "count": 4}
    assert [s["tag"] for s in body["styles"][:3]] == ["y2k", "minimalist", "streetwear"]
    assert len(body["trending"]) == len(PRODUCTS) and body["trending"][0]["reason"] == "Popular right now"


def test_search_styles_trending_counts_wishlist_and_cart_swipes(client):
    from app.store import store

    store.put("wishlist", "a:zara:4:blue", {"user_id": "a", "product_id": "zara:4:blue"})
    store.put("wishlist", "b:zara:4:blue", {"user_id": "b", "product_id": "zara:4:blue"})
    store.put("swipes", "a:hm:6:black", {"user_id": "a", "product_id": "hm:6:black", "action": "cart"})
    store.put("swipes", "a:hm:1:blue", {"user_id": "a", "product_id": "hm:1:blue", "action": "discard"})
    body = client.get("/search/styles", params={"user_id": "u_sized", "limit": 5}).json()
    assert _ids(body["trending"]) == ["zara:4:blue", "hm:6:black"]
    assert body["trending"][0]["reason"] == "Trending: saved by 2 shoppers"
    assert "in_your_size" in body["trending"][0]


# ---------- photo search ----------

def _jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, "JPEG")
    return buf.getvalue()


def test_search_photo_tags_matches_and_completes(client, tmp_path):
    r = client.post("/search/photo", data={"user_id": "u_sized"},
                    files={"file": ("fit.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"tags", "similar", "goes_with"}
    assert [t["label"] for t in body["tags"]] == ["light-wash baggy jeans", "white baby tee"]  # mock tag_fit
    sim = body["similar"]
    assert "hm:1:blue" in _ids(sim) and "zara:3:white" in _ids(sim)  # shop_fit matches
    assert all({"your_size", "in_your_size", "reason", "matched_tag"} <= set(c) for c in sim)
    assert body["goes_with"] and all(c["id"] not in _ids(sim)[:1] for c in body["goes_with"])
    from app.store import DATA_DIR

    assert list((DATA_DIR / "uploads").glob("*.jpg"))  # saved through _save_upload (metadata stripped)


def test_search_photo_502_when_tagging_is_down(client, monkeypatch):
    from app.ai import service
    from app.ai.llm import BadModelOutput

    def boom(url):
        raise BadModelOutput("down")

    monkeypatch.setattr(service, "tag_fit", boom)
    r = client.post("/search/photo", data={"user_id": "u_sized"}, files={"file": ("f.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 502


def test_search_photo_rejects_non_images(client):
    r = client.post("/search/photo", data={"user_id": "u_sized"}, files={"file": ("f.txt", b"hi", "text/plain")})
    assert r.status_code == 415
