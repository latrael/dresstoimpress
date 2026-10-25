import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"


def _p(pid, retailer, name, cat, price, **kw):
    return {"id": pid, "retailer": retailer, "name": name, "brand": retailer.upper(), "category": cat,
            "price_usd": price, "sale_price_usd": None, "colors": [], "style_tags": [], "label": "",
            "sizes": [{"name": "M", "in_stock": True}], "in_stock": True, "image_url": "https://x/y.jpg",
            "product_url": "https://x", "source": "ingest", **kw}


PRODUCTS = [
    _p("hm:1:blue", "hm", "Baggy Jeans", "bottom", 30.0, colors=["light blue"], style_tags=["y2k"]),
    _p("hm:1:black", "hm", "Baggy Jeans", "bottom", 30.0, colors=["black"], style_tags=["y2k"]),  # colour variant
    _p("hm:2:black", "hm", "Slim Jeans", "bottom", 25.0, colors=["black"], label="black slim jeans",
       style_tags=["minimalist"]),
    _p("zara:3:white", "zara", "Baby Tee", "top", 15.0, colors=["white"], style_tags=["y2k", "minimalist"]),
    _p("zara:4:blue", "zara", "Denim Jacket", "outerwear", 60.0, colors=["blue"], style_tags=["streetwear"]),
    _p("hm:6:white", "hm", "Chunky Sneakers", "shoes", 50.0, colors=["white"], style_tags=["streetwear", "casual"]),
    _p("asos:5:red", "asos", "Gone Jeans", "bottom", 20.0, style_tags=["y2k"], in_stock=False,
       sizes=[{"name": "M", "in_stock": False}]),
]
CLOSET_TEE = {"id": "ci_tee", "user_id": "u_closet", "image_url": "https://x/tee.jpg", "category": "top",
              "color": "white", "pattern": "solid", "style_tags": ["minimalist"], "formality": 2,
              "source": "photo", "label": "white tee"}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        store.root = Path(tmp_path_factory.mktemp("discover"))  # fresh data for this module
    for p in PRODUCTS:
        store.put("products", p["id"], p)
    store.put("closet_items", CLOSET_TEE["id"], CLOSET_TEE)
    return TestClient(app)


def _search(client, q, user_id="u_new"):
    r = client.get("/search", params={"user_id": user_id, "q": q})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- GET /search ----------

def test_text_search_shape_and_relevance(client):
    r = _search(client, "jeans")
    assert set(r) == {"query", "similar", "goes_with", "vibe"} and r["query"] == "jeans" and r["vibe"] is None
    # name + label beats name only; one card per style (colour variants collapse); sold-out Gone Jeans hidden
    assert [p["id"] for p in r["similar"]] == ["hm:2:black", "hm:1:black"]
    assert r["similar"][0]["sizes"] == [{"name": "M", "in_stock": True}]  # stored Product shape, like /products
    # complete the look around the #1 result, from the catalog for a user with no closet
    gw = r["goes_with"]
    assert gw and all(not g["from_closet"] and g["reason"] for g in gw)
    assert "hm:2:black" not in {g["id"] for g in gw}
    assert {"top", "shoes"} <= {g["category"] for g in gw}
    assert all(g["in_stock"] for g in gw)


def test_goes_with_uses_closet_first(client):
    gw = _search(client, "jeans", user_id="u_closet")["goes_with"]
    tops = [g for g in gw if g["category"] == "top"]
    assert tops == [{**CLOSET_TEE, "from_closet": True, "reason": tops[0]["reason"]}]
    assert not any(g["id"] == "zara:3:white" for g in gw)  # the catalog tee isn't suggested on top of it


def test_blank_query_and_no_results(client):
    assert _search(client, "") == {"query": "", "similar": [], "goes_with": [], "vibe": None}
    assert _search(client, "   ") == {"query": "   ", "similar": [], "goes_with": [], "vibe": None}
    r = _search(client, "ballgown")  # no keyword hits and nothing vibe() can map
    assert (r["similar"], r["goes_with"]) == ([], []) and r["vibe"]["source"] == "rules"


def test_goes_with_falls_back_to_empty(client, monkeypatch):
    from app.commerce import search

    def boom(req):
        raise RuntimeError("engine down")
    monkeypatch.setattr(search, "complete_look_route", boom)
    r = _search(client, "tee")
    assert [p["id"] for p in r["similar"]] == ["zara:3:white"] and r["goes_with"] == []


# ---------- GET /search/styles ----------

def test_style_chips_count_in_stock_only(client):
    r = client.get("/search/styles", params={"user_id": "u_new"}).json()
    # y2k: both Baggy Jeans colours + Baby Tee (sold-out Gone Jeans not counted); "casual" isn't a style tag
    assert r["styles"] == [{"tag": "y2k", "count": 3}, {"tag": "minimalist", "count": 2},
                           {"tag": "streetwear", "count": 2}]


def test_trending_counts_users_and_tops_up(client):
    from app.store import store

    for uid in ("t1", "t2"):
        assert client.put(f"/wishlist/{uid}/items/zara:4:blue").status_code == 200
    client.post("/swipe", json={"user_id": "t3", "product_id": "zara:4:blue", "action": "save"})  # legacy save
    client.post("/cart/t3/items", json={"product_id": "zara:4:blue", "size": "M"})  # same user, other signal
    client.post("/cart/t1/items", json={"product_id": "hm:6:white", "size": "M", "qty": 3})  # qty doesn't count
    client.post("/cart/t4/items", json={"product_id": "hm:2:black", "size": "M"})
    assert client.post("/checkout/t4").status_code == 200  # ordered (cart now empty)
    client.post("/cart/t5/items", json={"product_id": "asos:5:red", "size": "M"})  # sold out: refused

    r = client.get("/search/styles", params={"user_id": "u_new", "limit": 4}).json()
    trending = [(p["id"], p["trend_count"]) for p in r["trending"]]
    assert trending[:3] == [("zara:4:blue", 4), ("hm:6:white", 1), ("hm:2:black", 1)]  # tie -> name
    assert len(trending) == 4 and trending[3][1] == 0  # topped up from u_new's feed
    assert trending[3][0] not in {"zara:4:blue", "hm:6:white", "hm:2:black"}
    assert "reason" in r["trending"][3]  # top-ups are feed cards

    full = client.get("/search/styles", params={"user_id": "u_new"}).json()["trending"]
    ids = [p["id"] for p in full]
    assert len(ids) == len(set(ids)) == 5  # 5 in-stock styles; Baggy Jeans colours collapse
    assert "asos:5:red" not in ids
    assert not store.list("fitcheck_posts")  # reading trending writes nothing


# ---------- POST /search/photo ----------

def _photo(client, user_id="u_cam"):
    return client.post("/search/photo", data={"user_id": user_id},
                       files={"file": ("fit.png", b"\x89PNG fake", "image/png")})


def test_photo_search_shape(client):
    from app.store import store

    r = _photo(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"photo_url", "tags", "similar", "goes_with"}
    assert "/static/uploads/" in body["photo_url"]
    assert [t["label"] for t in body["tags"]] == ["light-wash baggy jeans", "white baby tee"]  # MOCK_AI tagger
    ids = [p["id"] for p in body["similar"]]
    assert ids[0] == "hm:1:blue" and "zara:3:white" in ids and "asos:5:red" not in ids
    top = body["similar"][0]
    assert top["matched_tag"] == "light-wash baggy jeans" and top["reason"]
    assert top["sizes"] == [{"name": "M", "in_stock": True}]  # stored Product shape, not the AI's view
    assert body["goes_with"] and "hm:1:blue" not in {g["id"] for g in body["goes_with"]}
    # a search is not a post and not a closet upload
    assert not store.list("fitcheck_posts") and not store.list("closet_items", user_id="u_cam")


def test_photo_search_tagging_down_is_502(client, monkeypatch):
    from app.ai import service
    from app.ai.llm import BadModelOutput

    def down(url):
        raise BadModelOutput("claude: 529 overloaded")
    monkeypatch.setattr(service, "tag_fit", down)
    r = _photo(client)
    assert r.status_code == 502 and "529" not in r.text  # plain message, provider details only in the log
    assert "unavailable" in r.json()["detail"]


def test_photo_search_no_garments(client, monkeypatch):
    from app.ai import service

    monkeypatch.setattr(service, "tag_fit", lambda url: [])
    r = _photo(client)
    assert r.status_code == 200
    assert {k: v for k, v in r.json().items() if k != "photo_url"} == {"tags": [], "similar": [], "goes_with": []}


def test_photo_search_needs_a_file(client):
    assert client.post("/search/photo", data={"user_id": "u_cam"}).status_code == 422


# ---------- vibe search (Adam's vibe() turns a sentence into filters) ----------

def test_sentence_goes_through_vibe(client, monkeypatch):
    from app.commerce import search
    seen = []

    def fake_vibe(q):
        seen.append(q)
        return {"styles": ["streetwear"], "categories": ["shoes"], "colors": ["white"], "keywords": [],
                "source": "rules"}
    monkeypatch.setattr(search, "vibe", fake_vibe)
    r = _search(client, "fit for a rooftop party")
    assert seen == ["fit for a rooftop party"] and r["vibe"]["styles"] == ["streetwear"]
    # streetwear + shoes + white (6) > streetwear (3) > white only (1); non-matching items are left out
    assert [p["id"] for p in r["similar"]] == ["hm:6:white", "zara:4:blue", "zara:3:white"]


def test_keyword_hits_stay_first_for_sentences(client, monkeypatch):
    from app.commerce import search
    monkeypatch.setattr(search, "vibe", lambda q: {"styles": ["y2k"], "categories": [], "colors": [],
                                                   "keywords": [], "source": "rules"})
    ids = [p["id"] for p in _search(client, "black slim jeans")["similar"]]
    assert ids[0] == "hm:2:black" and "zara:3:white" in ids  # exact match first, vibe extras after


def test_no_keyword_hits_falls_back_to_vibe_and_short_hits_skip_it(client, monkeypatch):
    from app.commerce import search
    calls = []
    monkeypatch.setattr(search, "vibe", lambda q: calls.append(q) or {
        "styles": ["y2k"], "categories": [], "colors": [], "keywords": ["baby tee"], "source": "rules"})
    assert [p["id"] for p in _search(client, "2000s")["similar"]][0] == "zara:3:white"  # y2k + keyword
    assert calls == ["2000s"]
    _search(client, "jeans")
    assert calls == ["2000s"]  # a one-word query with hits never calls vibe()
