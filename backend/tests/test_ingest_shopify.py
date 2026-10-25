"""Shopify stores (autofacts/shopify) -> Products, and GET /stores."""
import copy
import json
import os
from collections import Counter
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

from app.commerce.ingest import NORMALIZERS  # noqa: E402
from app.commerce.ingest_shopify import normalize_shopify  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
RAW = json.loads((FIX / "shopify_raw.json").read_text())  # one real Princess Polly product, trimmed


def _item(**kw):
    it = copy.deepcopy(RAW[0])
    it.update(kw)
    return it


def test_princess_polly_product():
    [p] = normalize_shopify(RAW)
    assert p["id"].startswith("princesspolly:") and p["id"].endswith(":red-gingham")
    assert (p["retailer"], p["brand"], p["department"], p["category"]) == \
        ("princesspolly", "Princess Polly", "women", "top")
    assert (p["price_usd"], p["sale_price_usd"]) == (39.0, 12.0)  # cents; compare-at price -> sale
    assert [s["name"] for s in p["sizes"]] == ["0", "2", "4", "6"]  # "US 0" -> "0"
    assert p["image_url"].startswith("https://cdn.shopify.com/") and p["images"][0]["url"] == p["image_url"]
    assert p["description"] == "Halter gingham top\nGood stretch"
    assert NORMALIZERS["shopify"] is normalize_shopify


def test_one_product_per_colour_with_its_own_stock_and_photo():
    it = _item(options=[{"type": "Size", "values": []}, {"type": "Color", "values": []}],
               variants=[{"id": "1", "options": ["S", "Black"], "price": {"current": 5000, "stockStatus": "InStock"}},
                         {"id": "2", "options": ["M", "Black"], "price": {"current": 5000, "stockStatus": "OutOfStock"}},
                         {"id": "3", "options": ["S", "Cream"], "price": {"current": 5000, "stockStatus": "OutOfStock"}}],
               medias=[{"url": "https://cdn.shopify.com/cream.jpg", "variantIds": ["3"]},
                       {"url": "https://cdn.shopify.com/black.jpg", "variantIds": ["1", "2"]}])
    black, cream = normalize_shopify([it])  # in-stock colour first
    assert black["id"].endswith(":black") and black["sizes"] == [{"name": "S", "in_stock": True},
                                                                  {"name": "M", "in_stock": False}]
    assert black["image_url"].endswith("black.jpg") and cream["image_url"].endswith("cream.jpg")
    assert (black["in_stock"], cream["in_stock"], black["sale_price_usd"]) == (True, False, None)


def test_waist_and_length_sizes_and_store_words():
    it = _item(title="FLEECE PANT", categories=["BOTTOMS"],
               source={**RAW[0]["source"], "canonicalUrl": "https://www.stussy.com/products/fleece-pant"},
               options=[{"type": "Waist"}, {"type": "Length"}],
               variants=[{"id": "1", "options": ["32", "30"], "price": {"current": 11000, "stockStatus": "InStock"}}])
    [p] = normalize_shopify([it])
    assert (p["retailer"], p["department"], p["category"]) == ("stussy", "unisex", "bottom")
    assert p["sizes"] == [{"name": "32x30", "in_stock": True}]
    tee = _item(title="Short Sleeve Crew", categories=["Short Sleeve Crew"],
                source={**RAW[0]["source"], "canonicalUrl": "https://trueclassictees.com/products/crew"})
    assert normalize_shopify([tee])[0]["category"] == "top"


def test_kith_department_and_drops():
    kith = {**RAW[0]["source"], "canonicalUrl": "https://kith.com/products/x"}
    assert normalize_shopify([_item(source=kith)])[0]["department"] == "men"
    assert normalize_shopify([_item(source=kith, title="Kith Women Mercer Tee")])[0]["department"] == "women"
    drops = Counter()
    out = normalize_shopify([_item(title="Gift Card"), _item(source={**kith, "canonicalUrl": "https://shop.example.com/p"}),
                             _item(source={**kith, "currency": "AUD"})], drops)
    assert out == [] and drops == {"shopify_not_apparel": 1, "shopify_unknown_store": 1, "shopify_not_usd": 1}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        monkeypatch.setattr(store, "root", Path(tmp_path))
    for p in normalize_shopify(RAW):
        store.put("products", p["id"], p)
    store.put("products", "hm:1:blue", {**normalize_shopify(RAW)[0], "id": "hm:1:blue", "retailer": "hm",
                                        "department": "men"})
    store.put("products", "hm:2:red", {**normalize_shopify(RAW)[0], "id": "hm:2:red", "retailer": "hm",
                                       "department": None})
    store.put("products", "hm:3:gone", {**normalize_shopify(RAW)[0], "id": "hm:3:gone", "retailer": "hm",
                                        "in_stock": False, "sizes": [{"name": "M", "in_stock": False}]})
    return TestClient(app)


def test_stores_route(client):
    r = client.get("/stores")
    assert r.status_code == 200, r.text
    assert r.json() == [
        {"id": "hm", "name": "H&M", "count": 2, "departments": {"men": 1}},  # sold-out item not counted
        {"id": "princesspolly", "name": "Princess Polly", "count": 1, "departments": {"women": 1}},
    ]


def test_fit_names_and_one_size_become_one_size():
    it = _item(options=[{"type": "Size"}],
               variants=[{"id": "1", "options": ["Regular Fit"], "price": {"current": 3000, "stockStatus": "InStock"}}])
    assert normalize_shopify([it])[0]["sizes"] == [{"name": "One Size", "in_stock": True}]


def test_uniqlo_and_hm_drop_non_apparel():
    from app.commerce.ingest import normalize_hm, normalize_uniqlo
    drops = Counter()
    assert normalize_uniqlo([{"productId": "E1", "name": "Storage Bag | PUFFTECH", "genderName": "UNISEX"}], drops) == []
    assert normalize_hm([{"id": "1", "category": "ladies_accessories_keychains", "title": "Ballet Keychain",
                          "price": 5, "model_image": "https://image.hm.com/x.jpg"}], drops) == []
    assert drops == {"uniqlo_not_apparel": 1, "hm_not_apparel": 1}


def test_shoes_and_accessories_pull():
    """Sprint-4 catalog gap: kids' sneakers and lifestyle goods are dropped, shoe/jewellery words categorise,
    Princess Polly's "SHOE US 7" is size "7"."""
    from app.commerce.ingest import guess_category
    from app.commerce.ingest_shopify import _US

    drops = Counter()
    out = normalize_shopify([_item(title="Jordan 5 Retro PS - Black"), _item(title="Air Max 1 TD - White"),
                             _item(title="Kith for BMW Teddy Bear - Sunglow"), _item(title="HELINOX TABLE ONE HARD TOP"),
                             _item(title="BOXER SHORTS 3 PACK")], drops)
    assert out == [] and drops == {"shopify_kids": 2, "shopify_not_apparel": 3}
    assert {t: guess_category(t) for t in ("Worth It Buckle Detail Sandals Black", "Collegium Pillar Moc-Toe Derby",
                                           "Jordan 5 Retro Sneaker", "Hoop Earrings", "Dear London Ring Pack Gold",
                                           "Rhinestone Pearl Claw Clip", "Sonique Sequin Crochet Sarong")} == {
        "Worth It Buckle Detail Sandals Black": "shoes", "Collegium Pillar Moc-Toe Derby": "shoes",
        "Jordan 5 Retro Sneaker": "shoes", "Hoop Earrings": "accessory", "Dear London Ring Pack Gold": "accessory",
        "Rhinestone Pearl Claw Clip": "accessory", "Sonique Sequin Crochet Sarong": "bottom"}
    assert [_US.sub("", s) for s in ("SHOE US 7", "US 8", "M")] == ["7", "8", "M"]
