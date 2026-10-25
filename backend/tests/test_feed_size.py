"""/feed soft size ranking (in your size first, never hidden), preferred-store 2:1 mix, seeded Home (?seed=,
seed_shown), and the same size fields/order on Discover (/search, /search/photo, trending)."""
import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

ALL = {"S": True, "M": True, "L": True}
NO_M = {"S": True, "M": False, "L": True}


def _mk(pid, retailer="hm", category="top", name=None, sizes=ALL, colors=(), tags=(), price=20.0):
    return {"id": pid, "retailer": retailer, "name": name or pid, "brand": retailer, "category": category,
            "price_usd": price, "colors": list(colors), "style_tags": list(tags),
            "sizes": [{"name": s, "in_stock": ok} for s, ok in sizes.items()], "in_stock": True,
            "image_url": "https://x/y.jpg", "product_url": "https://x", "source": "seed"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        monkeypatch.setattr(store, "root", Path(tmp_path))  # empty store per test: only the products below
    return TestClient(app)


def _rank(monkeypatch, order):
    """pair() stub: ranks exactly `order` (ids not among the candidates are dropped, like the real one)."""
    from app.commerce import router
    from app.models import PairResult
    monkeypatch.setattr(router, "pair", lambda uid, cands, k: [
        PairResult(product_id=pid, score=0.9, reason=f"why {pid}") for pid in order if pid in cands])


def _put(user=None, products=()):
    from app.store import store
    store.put("users", "u", {"id": "u", "display_name": "u", **(user or {})})
    for p in products:
        store.put("products", p["id"], p)


def _ids(cards):
    return [c["id"] for c in cards]


def test_in_your_size_first_keeping_ai_order(client, monkeypatch):
    _put({"body_profile": {"usual_sizes": {"top": "M"}}},
         [_mk("a", sizes=NO_M), _mk("b"), _mk("c"), _mk("d", sizes=NO_M)])
    _rank(monkeypatch, ["a", "c", "d", "b"])
    cards = client.get("/feed", params={"user_id": "u"}).json()
    assert _ids(cards) == ["c", "b", "a", "d"]  # M in stock first, AI order inside each group, nothing hidden
    by = {c["id"]: c for c in cards}
    assert by["c"]["your_size"] == "M" and by["c"]["in_your_size"] is True and by["c"]["reason"] == "why c"
    assert by["a"]["your_size"] is None and by["a"]["in_your_size"] is False  # usual size sold out


def test_body_numbers_suggest_nearest_size_when_theirs_is_sold_out(client, monkeypatch):
    _put({"body_profile": {"height_cm": 178, "weight_kg": 72}}, [_mk("a", sizes=NO_M), _mk("b")])
    _rank(monkeypatch, ["a", "b"])
    cards = client.get("/feed", params={"user_id": "u"}).json()
    assert [(c["id"], c["your_size"], c["in_your_size"]) for c in cards] == [("b", "M", True), ("a", "L", False)]
    # same pick as POST /size
    assert client.post("/size", json={"product_id": "a", "user_id": "u"}).json()["size"] == "L"


def test_no_size_info_gives_null_fields_and_plain_order(client, monkeypatch):
    _put({}, [_mk("a", sizes=NO_M), _mk("b"), _mk("s", category="shoes", sizes={"9": True})])
    _rank(monkeypatch, ["a", "s", "b"])
    cards = client.get("/feed", params={"user_id": "u"}).json()
    assert _ids(cards) == ["a", "s", "b"]  # unchanged: AI order, categories alternated
    assert all(c["your_size"] is None and c["in_your_size"] is None for c in cards)


def test_preferred_stores_boost_within_size_group(client, monkeypatch):
    _put({"preferred_stores": ["uniqlo"], "body_profile": {"usual_sizes": {"top": "M"}}},
         [_mk("h1"), _mk("h2"), _mk("u1", "uniqlo"), _mk("u2", "uniqlo", sizes=NO_M)])
    _rank(monkeypatch, ["h1", "u2", "h2", "u1"])
    cards = client.get("/feed", params={"user_id": "u"}).json()
    # in your size: uniqlo first, then H&M; not in your size: still shown, last
    assert _ids(cards) == ["u1", "h1", "h2", "u2"]


def test_seeded_feed(client, monkeypatch):
    seed = _mk("jeans", category="bottom", name="Baggy jeans", colors=["blue"], tags=["y2k"])
    bottoms = [_mk("variant", category="bottom", name="Baggy jeans", colors=["black"], tags=["y2k"]),
               _mk("twin", category="bottom", name="Baggy wide jeans", colors=["blue"], tags=["y2k"]),
               _mk("far", category="bottom", name="Tailored trousers", colors=["grey"], tags=["business"]),
               *[_mk(f"b{i}", category="bottom", name=f"Jeans {i}", colors=["blue"]) for i in range(5)]]
    tops = [_mk("tee", name="White tee", colors=["white"]), _mk("tank", name="Black tank", colors=["black"])]
    _put({"body_profile": {"usual_sizes": {"bottom": "M", "top": "M"}}}, [seed, *bottoms, *tops])
    _rank(monkeypatch, ["tee"])
    client.post("/swipe", json={"user_id": "u", "product_id": "jeans", "action": "discard"})
    cards = client.get("/feed", params={"user_id": "u", "seed": "jeans"}).json()
    ids, cats = _ids(cards), [c["category"] for c in cards]
    assert ids[0] == "jeans" and cards[0]["your_size"] == "M"  # seed first even though it was swiped
    assert ids[1] == "twin" and ids.index("far") > ids.index("b0")  # most similar first
    assert "variant" not in ids  # the seed's other colour of the same style
    assert cats[1:6] == ["bottom"] * 5 and cats[6] == "top"  # a top that goes with it after 5 similar
    assert set(ids[6:]) >= {"tee", "tank"} and next(c for c in cards if c["id"] == "tee")["reason"] == "why tee"


def test_seeded_feed_size_first_and_404(client, monkeypatch):
    _put({"body_profile": {"usual_sizes": {"bottom": "M"}}},
         [_mk("jeans", category="bottom", name="Baggy jeans", colors=["blue"]),
          _mk("twin", category="bottom", name="Baggy blue jeans", colors=["blue"], sizes=NO_M),
          _mk("other", category="bottom", name="Chinos")])
    _rank(monkeypatch, [])
    cards = client.get("/feed", params={"user_id": "u", "seed": "jeans"}).json()
    assert _ids(cards) == ["jeans", "other", "twin"]  # in your size beats more similar
    assert client.get("/feed", params={"user_id": "u", "seed": "nope"}).status_code == 404


def test_preferred_stores_two_to_one(client, monkeypatch):
    _put({"preferred_stores": ["Uniqlo"], "body_profile": {"usual_sizes": {"top": "M"}}},
         [*[_mk(f"u{i}", "uniqlo") for i in range(1, 5)], *[_mk(f"h{i}", "hm") for i in range(1, 4)],
          _mk("u5", "uniqlo", sizes=NO_M), _mk("h4", "hm", sizes=NO_M)])
    _rank(monkeypatch, ["h2", "u3", "h1", "u1", "h3", "u2", "u4", "h4", "u5"])
    cards = client.get("/feed", params={"user_id": "u"}).json()
    # in your size: 2 uniqlo per H&M, each store in its own (AI) order; uniqlo runs out, H&M follows.
    # Not in your size: still shown, last, mixed the same way
    assert _ids(cards) == ["u3", "u1", "h2", "u2", "u4", "h1", "h3", "u5", "h4"]


def test_two_to_one_leftovers():
    from app.commerce.router import _two_to_one
    assert _two_to_one([1, 2, 3, 4, 5], ["a"]) == [1, 2, "a", 3, 4, 5]
    assert _two_to_one([1], ["a", "b", "c"]) == [1, "a", "b", "c"]
    assert _two_to_one([], ["a", "b"]) == ["a", "b"] and _two_to_one([1, 2], []) == [1, 2]


def test_seed_shown_drops_the_seed_card(client, monkeypatch):
    _put({"body_profile": {"usual_sizes": {"bottom": "M"}}},
         [_mk("jeans", category="bottom", name="Baggy jeans", colors=["blue"]),
          _mk("twin", category="bottom", name="Baggy blue jeans", colors=["blue"], sizes=NO_M),
          _mk("other", category="bottom", name="Chinos")])
    _rank(monkeypatch, [])
    params = {"user_id": "u", "seed": "jeans"}
    assert _ids(client.get("/feed", params=params).json()) == ["jeans", "other", "twin"]
    # later loads of the same seeded feed: still similar to the seed, the seed card itself is gone
    assert _ids(client.get("/feed", params={**params, "seed_shown": "true"}).json()) == ["other", "twin"]
    assert _ids(client.get("/feed", params={**params, "seed_shown": "true", "limit": 1}).json()) == ["other"]
    assert client.get("/feed", params={**params, "seed": "nope", "seed_shown": "true"}).status_code == 404


# ---------- Discover: same size fields + in-your-size first ----------

def test_text_search_in_your_size_first(client, monkeypatch):
    from app.commerce import search
    _put({"body_profile": {"usual_sizes": {"top": "M"}}},
         [_mk("a", name="Tee tee classic", sizes=NO_M), _mk("b", name="Tee plain"),
          _mk("c", name="Tee zip", sizes=NO_M), _mk("d", name="Tee boxy")])
    anchors = []
    monkeypatch.setattr(search, "complete_look_route", lambda req: anchors.append(req.product_id) or {"items": []})
    similar = client.get("/search", params={"user_id": "u", "q": "tee"}).json()["similar"]
    # relevance alone: a (2 hits), then d, b, c by name; in your size moves d and b up, nothing is hidden
    assert [(p["id"], p["your_size"], p["in_your_size"]) for p in similar] == [
        ("d", "M", True), ("b", "M", True), ("a", None, False), ("c", None, False)]
    assert anchors == ["d"]  # goes_with completes the first card shown


def test_text_search_no_size_info_keeps_relevance(client):
    _put({}, [_mk("a", name="Tee tee classic", sizes=NO_M), _mk("b", name="Tee plain")])
    similar = client.get("/search", params={"user_id": "u", "q": "tee"}).json()["similar"]
    assert [(p["id"], p["your_size"], p["in_your_size"]) for p in similar] == [("a", None, None), ("b", None, None)]


def test_photo_search_in_your_size_first(client, monkeypatch):
    from app.ai import service
    _put({"body_profile": {"usual_sizes": {"top": "M"}}}, [_mk("a", sizes=NO_M), _mk("b"), _mk("c", sizes=NO_M)])
    monkeypatch.setattr(service, "tag_fit", lambda url: [{"label": "white tee", "category": "top"}])
    monkeypatch.setattr(service, "shop_fit", lambda uid, tags, keep=None: [
        {"id": pid, "reason": f"why {pid}", "score": s, "matched_tag": "white tee"}
        for pid, s in (("a", 0.9), ("b", 0.8), ("c", 0.7))])
    r = client.post("/search/photo", data={"user_id": "u"}, files={"file": ("fit.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200, r.text
    similar = r.json()["similar"]
    assert [(p["id"], p["in_your_size"], p["reason"]) for p in similar] == [
        ("b", True, "why b"), ("a", False, "why a"), ("c", False, "why c")]  # AI order inside each group
    assert similar[0]["your_size"] == "M"


def test_trending_cards_carry_size_fields(client, monkeypatch):
    _put({"body_profile": {"usual_sizes": {"top": "M"}}}, [_mk("a", sizes=NO_M), _mk("b")])
    _rank(monkeypatch, [])
    assert client.put("/wishlist/someone/items/a").status_code == 200
    trending = client.get("/search/styles", params={"user_id": "u"}).json()["trending"]
    assert [(p["id"], p["trend_count"], p["your_size"], p["in_your_size"]) for p in trending] == [
        ("a", 1, None, False), ("b", 0, "M", True)]  # trending order kept; the feed top-up is sized too
