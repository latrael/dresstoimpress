import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"


def _p(pid, retailer, name, cat, price, sale=None, **kw):
    return {"id": pid, "retailer": retailer, "name": name, "brand": retailer.upper(), "category": cat,
            "price_usd": price, "sale_price_usd": sale, "colors": [], "style_tags": [], "label": "",
            "sizes": [{"name": "M", "in_stock": True}], "in_stock": True, "image_url": "https://x/y.jpg",
            "product_url": "https://x", "source": "ingest", **kw}


PRODUCTS = [
    _p("hm:1:blue", "hm", "Baggy Jeans", "bottom", 30.0, colors=["light blue"], style_tags=["y2k"]),
    _p("hm:2:black", "hm", "Slim Jeans", "bottom", 25.0, colors=["black"], label="black slim jeans"),
    _p("zara:3:white", "zara", "Baby Tee", "top", 15.0, sale=9.0, colors=["white"], style_tags=["y2k"]),
    _p("zara:4:blue", "zara", "Denim Jacket", "outerwear", 60.0, colors=["blue"]),
    _p("asos:5:red", "asos", "Gone Jeans", "bottom", 20.0, in_stock=False,
       sizes=[{"name": "M", "in_stock": False}]),
]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        store.root = Path(tmp_path_factory.mktemp("search"))  # fresh data for this module
    for p in PRODUCTS:
        store.put("products", p["id"], p)
    return TestClient(app)


def _ids(client, **params):
    r = client.get("/products", params=params)
    assert r.status_code == 200, r.text
    return [p["id"] for p in r.json()["items"]]


def test_every_word_must_match(client):
    assert set(_ids(client, q="jeans")) == {"hm:1:blue", "hm:2:black"}  # sold-out Gone Jeans hidden
    assert _ids(client, q="BLUE jeans") == ["hm:1:blue"]  # colour + name, case-insensitive
    assert _ids(client, q="y2k tee") == ["zara:3:white"]  # style tag + name
    assert _ids(client, q="zara") == ["zara:3:white", "zara:4:blue"]  # brand; relevance tie -> name


def test_relevance_counts_hits(client):
    assert _ids(client, q="black") == ["hm:2:black"]
    assert _ids(client, q="jeans")[0] == "hm:2:black"  # name + label beats name only


def test_filters_and_stock(client):
    assert _ids(client, category="bottom") == ["hm:1:blue", "hm:2:black"]
    assert _ids(client, category="bottom", in_stock="false") == ["hm:1:blue", "asos:5:red", "hm:2:black"]
    assert _ids(client, retailer="zara", category="top") == ["zara:3:white"]


def test_sort_by_price(client):
    assert _ids(client, sort="price_asc") == ["zara:3:white", "hm:2:black", "hm:1:blue", "zara:4:blue"]
    assert _ids(client, sort="price_desc") == ["zara:4:blue", "hm:1:blue", "hm:2:black", "zara:3:white"]
    assert client.get("/products", params={"sort": "cheap"}).status_code == 422


def test_paging(client):
    r = client.get("/products", params={"sort": "price_asc", "limit": 3}).json()
    assert (r["total"], r["limit"], r["offset"], r["next_offset"], len(r["items"])) == (4, 3, 0, 3, 3)
    r = client.get("/products", params={"sort": "price_asc", "limit": 3, "offset": 3}).json()
    assert [p["id"] for p in r["items"]] == ["zara:4:blue"] and r["next_offset"] is None
    assert client.get("/products", params={"limit": 0}).json()["limit"] == 1
    assert client.get("/products", params={"limit": 500}).json()["limit"] == 100


def test_empty_result(client):
    r = client.get("/products", params={"q": "ballgown"}).json()
    assert r == {"items": [], "total": 0, "limit": 24, "offset": 0, "next_offset": None}


def test_detail_route_still_resolves(client):
    assert client.get("/products/zara:3:white").json()["name"] == "Baby Tee"
    assert client.get("/products/nope").status_code == 404
