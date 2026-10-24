import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"
# app.* is imported inside tests: test_ai sets DATA_DIR before the store is first imported
ALL = ["top", "bottom", "outerwear", "shoes", "dress", "accessory"]


@pytest.mark.parametrize("text,styles,budgets", [
    ("Y2K, tops under $40", ["y2k"], {"top": [0, 40]}),
    ("streetwear, jeans $20-60 and jackets under 100", ["streetwear"], {"bottom": [20, 60], "outerwear": [0, 100]}),
    ("minimal stuff, everything under $50", ["minimalist"], {c: [0, 50] for c in ALL}),
    ("", [], {}),
    ("90s grunge, sneakers between 50 and 120; dresses around $60", ["vintage", "grunge"],
     {"shoes": [50, 120], "dress": [42, 78]}),
    ("gym fits, hoodies < 35, bags max $80", ["athleisure"], {"top": [0, 35], "accessory": [0, 80]}),
    ("under $30 tees", [], {"top": [0, 30]}),
])
def test_parse_prefs(text, styles, budgets):
    from app.commerce.users import parse_prefs
    out = parse_prefs(text)
    assert out["styles"] == styles and out["budgets"] == budgets


def test_parse_unmatched_and_no_bare_numbers():
    from app.commerce.users import parse_prefs
    out = parse_prefs("boho shirts max 25 and cool hats, size 10")
    assert out["budgets"] == {"top": [0, 25]} and out["unmatched"] == "cool hats size 10"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.commerce.router import router as commerce_router
    from app.commerce.users import router
    from app.store import store
    old = getattr(store, "root", None)
    if old is not None:
        store.root = Path(tmp_path_factory.mktemp("users"))  # fresh store for this module, restored after
    for uid in ("u_adam", "u_nabil"):
        store.put("users", uid, {"id": uid, "display_name": uid})
    for pid, cat, price in [("t-cheap", "top", 12.0), ("t-mid", "top", 24.9), ("t-pricey", "top", 39.0),
                            ("b-1", "bottom", 45.0)]:
        store.put("products", pid, {
            "id": pid, "retailer": "hm", "name": pid, "brand": "H&M", "category": cat, "price_usd": price,
            "sizes": [{"name": "M", "in_stock": True}], "in_stock": True, "image_url": "https://x/y.jpg",
            "product_url": "https://x", "style_tags": [], "source": "seed"})
    app = FastAPI()
    app.include_router(router)
    app.include_router(commerce_router)
    yield TestClient(app)
    if old is not None:
        store.root = old


def test_create_get_and_conflict(client):
    r = client.post("/users", json={"display_name": "Zoë Q", "style_text": "Y2K, tops under $40"})
    assert r.status_code == 200
    u = r.json()
    assert u["id"].startswith("u_zo-q-") and len(u["id"]) == len("u_zo-q-") + 4
    assert u["price_ranges"] == {"top": [0, 40]} and u["friends"] == []
    assert client.get(f"/users/{u['id']}").json() == u
    assert client.post("/users", json={"id": u["id"], "display_name": "dup"}).status_code == 409


def test_create_explicit_ranges_win(client):
    u = client.post("/users", json={"id": "u_x", "display_name": "X", "style_text": "tops under 40",
                                    "price_ranges": {"shoes": [10, 90]}}).json()
    assert u["price_ranges"] == {"shoes": [10, 90]}
    assert client.post("/users", json={"display_name": "Bad", "price_ranges": {"hats": [0, 9]}}).status_code == 422


def test_get_and_patch_404(client):
    assert client.get("/users/nope").status_code == 404
    assert client.patch("/users/nope", json={"display_name": "x"}).status_code == 404


def test_patch_merges_budgets(client):
    client.post("/users", json={"id": "u_p", "display_name": "P", "style_text": "tops under 40, jeans 20-60"})
    u = client.patch("/users/u_p", json={"style_text": "jeans under 30", "friends": ["u_adam"]}).json()
    assert u["price_ranges"] == {"top": [0, 40], "bottom": [0, 30]}
    assert u["style_text"] == "jeans under 30" and u["friends"] == ["u_adam"] and u["display_name"] == "P"
    u = client.patch("/users/u_p", json={"style_text": "shoes under 99", "price_ranges": {"dress": [5, 50]}}).json()
    assert u["price_ranges"] == {"dress": [5, 50]}  # explicit ranges replace


def test_onboarding_creates_then_updates(client):
    r = client.post("/onboarding", json={"display_name": "Mia", "text": "Y2K, tops under $40"}).json()
    u = r["user"]
    assert r["parsed"] == {"styles": ["y2k"], "budgets": {"top": [0, 40]}, "unmatched": ""}
    assert u["id"].startswith("u_mia-") and u["style_text"] == "Y2K, tops under $40"
    assert u["friends"] == ["u_adam", "u_nabil"]  # u_ryan isn't in the store
    r = client.post("/onboarding", json={"user_id": u["id"], "text": "streetwear, shoes under 80"}).json()
    assert r["user"]["price_ranges"] == {"top": [0, 40], "shoes": [0, 80]}
    assert r["user"]["display_name"] == "Mia" and r["user"]["friends"] == ["u_adam", "u_nabil"]


def test_onboarding_with_new_user_id(client):
    u = client.post("/onboarding", json={"user_id": "u_new", "text": ""}).json()["user"]
    assert u["id"] == "u_new" and u["display_name"] == "u_new" and u["price_ranges"] == {}


def test_onboarding_budget_filters_feed(client):
    uid = client.post("/onboarding", json={"display_name": "Feed", "text": "tops under $15"}).json()["user"]["id"]
    cards = client.get("/feed", params={"user_id": uid}).json()
    tops = [c for c in cards if c["category"] == "top"]
    assert [c["id"] for c in tops] == ["t-cheap"]
    assert all((c.get("sale_price_usd") or c["price_usd"]) <= 15 for c in tops)
    assert "b-1" in {c["id"] for c in cards}  # other categories untouched


def test_patch_preferred_stores_and_onboarded(client):
    from app.store import store
    store.put("users", "u_old", {"id": "u_old", "display_name": "Old"})  # saved before these fields existed
    u = client.get("/users/u_old").json()
    assert u["preferred_stores"] == [] and u["onboarded"] is False
    u = client.patch("/users/u_old", json={"preferred_stores": ["hm", "uniqlo"], "onboarded": True}).json()
    assert u["preferred_stores"] == ["hm", "uniqlo"] and u["onboarded"] is True
    assert client.get("/users/u_old").json() == u
    u = client.post("/onboarding", json={"user_id": "u_old", "text": "y2k"}).json()["user"]
    assert u["preferred_stores"] == ["hm", "uniqlo"] and u["onboarded"] is True  # onboarding keeps them
    assert client.patch("/users/u_old", json={"preferred_stores": []}).json()["preferred_stores"] == []
