import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"
os.environ["NESSIE_API_KEY"] = ""  # set before app.main's load_dotenv: checkout stays offline

RANGES = {"top": [10, 40], "bottom": [20, 60], "outerwear": [30, 90]}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data = tmp_path_factory.mktemp("commerce")
    backend = os.path.dirname(os.path.dirname(__file__))
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=backend, check=True,
                   env={**os.environ, "DATA_DIR": str(data)})
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        store.root = Path(data)  # store is built at import; point it at this module's fresh data
    store.put("products", "zara-sold-out", {
        "id": "zara-sold-out", "retailer": "zara", "name": "Gone tee", "brand": "Zara", "category": "top",
        "price_usd": 20.0, "sizes": [{"name": "M", "in_stock": False}], "in_stock": False,
        "image_url": "https://x/y.jpg", "product_url": "https://x", "source": "ingest"})
    for uid in ("u_feed", "u_disc", "u_cart", "u_chk"):
        store.put("users", uid, {"id": uid, "display_name": uid, "price_ranges": RANGES})
    return TestClient(app)


def test_feed_filters_and_reasons(client):
    r = client.get("/feed", params={"user_id": "u_feed"})
    assert r.status_code == 200
    cards = r.json()
    ids = {c["id"] for c in cards}
    assert ids == {"hm-demo-1", "zara-demo-1", "uniqlo-demo-1", "asos-demo-1"}  # no sold-out, no $130 bomber
    assert all("reason" in c and "score" in c and "pairs_with" in c for c in cards)
    assert all(c["retailer"] and c["image_url"] for c in cards)


def test_feed_filters_by_category(client):
    cards = client.get("/feed", params={"user_id": "u_feed", "category": "outerwear"}).json()
    assert [c["id"] for c in cards] == ["zara-demo-1"]


def test_discard_removes_from_feed(client):
    r = client.post("/swipe", json={"user_id": "u_disc", "product_id": "hm-demo-1", "action": "discard"})
    assert r.status_code == 200
    ids = {c["id"] for c in client.get("/feed", params={"user_id": "u_disc"}).json()}
    assert "hm-demo-1" not in ids and ids


def test_save_goes_to_wishlist(client):
    client.post("/swipe", json={"user_id": "u_disc", "product_id": "asos-demo-1", "action": "save"})
    assert [p["id"] for p in client.get("/wishlist/u_disc").json()] == ["asos-demo-1"]


def test_out_of_stock_size_422(client):
    r = client.post("/cart/u_cart/items", json={"product_id": "hm-demo-1", "size": "XL"})
    assert r.status_code == 422
    r = client.post("/cart/u_cart/items", json={"product_id": "hm-demo-1", "size": "XXXL"})
    assert r.status_code == 422


def test_cart_groups_by_retailer(client):
    client.post("/cart/u_cart/items", json={"product_id": "hm-demo-1", "size": "M", "qty": 2})
    client.post("/swipe", json={"user_id": "u_cart", "product_id": "zara-demo-1", "action": "like", "size": "S"})
    cart = client.get("/cart/u_cart").json()
    groups = {g["retailer"]: g for g in cart["groups"]}
    assert set(groups) == {"hm", "zara"}
    assert groups["hm"]["subtotal_usd"] == 25.98
    assert groups["zara"]["subtotal_usd"] == 59.90
    assert cart["total_usd"] == 85.88 and cart["count"] == 3
    assert groups["hm"]["items"][0]["product"]["name"] == "Cropped baby tee"

    cart = client.delete("/cart/u_cart/items/zara-demo-1", params={"size": "S"}).json()
    assert [g["retailer"] for g in cart["groups"]] == ["hm"]


def test_checkout_one_purchase_per_retailer(client):
    for pid in ("hm-demo-1", "uniqlo-demo-1", "asos-demo-1"):
        client.post("/cart/u_chk/items", json={"product_id": pid, "size": "M"})
    r = client.post("/checkout/u_chk")
    assert r.status_code == 200
    body = r.json()
    assert sorted(p["retailer"] for p in body["purchases"]) == ["asos", "hm", "uniqlo"]
    assert all(p["status"] == "pending_nessie" and p["merchant_id"] is None for p in body["purchases"])
    assert body["total_usd"] == round(12.99 + 24.90 + 28.00, 2)
    assert client.get("/cart/u_chk").json()["count"] == 0
    from app.store import store
    assert store.get("orders", body["order_id"])["user_id"] == "u_chk"
    assert client.post("/checkout/u_chk").status_code == 400


def test_product_404(client):
    assert client.get("/products/nope").status_code == 404
    assert client.get("/products/hm-demo-1").json()["retailer"] == "hm"


def test_interleave_dedupes_styles_and_mixes_stores():
    from app.commerce.router import _interleave
    mk = lambda i, r, c, n: {"id": i, "retailer": r, "category": c, "name": n}
    out = _interleave([mk("a", "hm", "bottom", "Harper Jeans"), mk("b", "hm", "bottom", "Harper Jeans"),
                       mk("c", "hm", "bottom", "Mom Jeans"), mk("d", "hm", "top", "Tee"),
                       mk("e", "uniqlo", "top", "Supima Tee")])
    assert [p["id"] for p in out] == ["a", "e", "d", "c"]
