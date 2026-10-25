"""Fixes from the overnight AI quality pass (scripts/ai_quality_check.py, Sat ~1:30 AM)."""
import pytest

CLOSET = [
    {"id": "c1", "user_id": "u_q", "category": "bottom", "color": "black", "pattern": "solid", "style_tags": [],
     "label": "black cargos", "image_url": "https://img/c1.jpg"},
    {"id": "c2", "user_id": "u_q", "category": "bottom", "color": "light blue", "pattern": "solid", "style_tags": [],
     "label": "baggy jeans", "image_url": "https://img/c2.jpg"},
    {"id": "c3", "user_id": "u_q", "category": "shoes", "color": "white", "pattern": "solid", "style_tags": [],
     "label": "white sneakers", "image_url": "https://img/c3.jpg"},
]


@pytest.mark.parametrize("reason,unknown", [
    ("baggy denim that layers with your black tees", True),          # no tees in the closet
    ("pairs with your favorite leather jacket", True),
    ("dark baggy jeans that match your black cargo style", False),    # cargo = cargos
    ("plum hoodie that complements your denim blue jeans", False),
    ("works with your black cargos and white sneakers", False),
    ("pairs nicely with your baggy jeans for a grunge look", False),
    ("a clean everyday tee", False),                                  # no "your ..." claim at all
])
def test_unknown_closet_reference(reason, unknown):
    from app.ai.service import _unknown_closet_ref

    assert _unknown_closet_ref(reason, CLOSET) is unknown


def _setup(tmp_path, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    for c in CLOSET:
        store.put("closet_items", c["id"], c)
    store.put("users", "u_q", {"id": "u_q", "display_name": "Q", "price_ranges": {"top": [10, 30]}})
    base = {"retailer": "hm", "brand": "H&M", "category": "top", "colors": ["black"], "style_tags": [],
            "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p"}
    store.put("products", "cheap", {**base, "id": "cheap", "name": "Tee A", "price_usd": 15.0})
    store.put("products", "pricey", {**base, "id": "pricey", "name": "Tee B", "price_usd": 80.0})
    return service, store


def test_pair_is_budget_first_and_fixes_made_up_closet_items(tmp_path, monkeypatch):
    service, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(service, "ai_json", lambda prompt, **k: [
        {"product_id": "pricey", "score": 0.95, "reason": "goes with your baggy jeans", "pairs_with": ["c2"]},
        {"product_id": "cheap", "score": 0.6, "reason": "layers with your black tees", "pairs_with": []},
    ])
    out = service.pair("u_q", ["cheap", "pricey"], k=2)
    assert [r.product_id for r in out] == ["cheap", "pricey"]          # in budget ranks first despite score
    cheap = out[0]
    assert "tees" not in cheap.reason and cheap.reason.lower().startswith("pairs with your ")
    assert cheap.pairs_with and cheap.pairs_with[0] in {"c1", "c2"}  # a real bottom for a top
    assert out[1].reason == "Goes with your baggy jeans"              # good reasons untouched


def test_shop_fit_exact_item_first_and_colour_variants_collapse(tmp_path, monkeypatch):
    from app.store import store

    _setup(tmp_path, monkeypatch)
    from app.ai import service

    base = {"retailer": "hm", "brand": "H&M", "category": "outerwear", "price_usd": 49.99, "style_tags": [],
            "image_url": "https://img/j.jpg", "product_url": "https://hm.com/j", "in_stock": True}
    store.put("products", "bomber", {**base, "id": "bomber", "name": "Lightweight Bomber Jacket", "colors": ["black"]})
    store.put("products", "puffer_b", {**base, "id": "puffer_b", "name": "Slim-Fit Lightweight Puffer Jacket", "colors": ["black"]})
    store.put("products", "puffer_n", {**base, "id": "puffer_n", "name": "Slim-Fit Lightweight Puffer Jacket", "colors": ["navy"]})
    tag = {"label": "slim-fit lightweight puffer jacket", "category": "outerwear", "color": "black"}
    out = service.shop_fit("u_q", [tag])
    ids = [p["id"] for p in out]
    assert ids[0] == "puffer_b" and "puffer_n" not in ids and "bomber" in ids


@pytest.mark.parametrize("h,w,allowed", [(158, 50, {"0", "2", "4"}), (172, 68, {"6", "8", "10"})])
def test_womens_numeric_estimate(h, w, allowed):
    from app.ai.sizing import recommend_size

    jeans = {"category": "bottom", "retailer": "hm", "sizes": ["0", "2", "4", "6", "8", "10", "12", "14", "16"]}
    r = recommend_size(jeans, h, w)
    assert r["size"] in allowed and r["confidence"] == "low"


def test_mens_waist_estimate_unchanged():
    from app.ai.sizing import recommend_size

    jeans = {"category": "bottom", "retailer": "hm", "sizes": ["28/32", "30/32", "32/32", "34/32", "36/32"]}
    assert recommend_size(jeans, 172, 68)["size"] in {"32/32", "34/32"}


def test_ai_errors_are_plain_messages(monkeypatch):
    from fastapi.testclient import TestClient

    from app.ai import service
    from app.ai.llm import BadModelOutput
    from app.main import app

    def boom(*a, **k):
        raise BadModelOutput("claude: Error code: 401 - {'request_id': 'req_123', 'x-api-key': 'sk-...'}")
    monkeypatch.setattr(service, "tag_closet_item", boom)
    r = TestClient(app).post("/closet/tag", json={"user_id": "u", "image_url": "https://img/x.jpg"})
    assert r.status_code == 502
    assert r.json()["detail"] == "photo tagging is unavailable right now, try again in a minute"
    assert "req_" not in r.text and "401" not in r.text
