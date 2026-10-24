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


def test_cart_change_size_atomic(client):
    from app.store import store
    uid = "u_resize"
    client.post(f"/cart/{uid}/items", json={"product_id": "hm-demo-1", "size": "S", "qty": 2})
    url = f"/cart/{uid}/items/hm-demo-1"
    # plain move: quantity kept, size changed, one line
    r = client.patch(url, json={"size": "S", "new_size": "M"})
    assert r.status_code == 200, r.text
    cart = r.json()
    assert set(cart) == {"user_id", "groups", "total_usd", "count"}  # same shape as the other cart routes
    lines = [(i["size"], i["qty"]) for g in cart["groups"] for i in g["items"]]
    assert lines == [("M", 2)] and cart["count"] == 2
    # merge into an existing line of the new size
    client.post(f"/cart/{uid}/items", json={"product_id": "hm-demo-1", "size": "L", "qty": 1})
    cart = client.patch(url, json={"size": "M", "new_size": "L"}).json()
    lines = [(i["size"], i["qty"]) for g in cart["groups"] for i in g["items"]]
    assert lines == [("L", 3)] and cart["count"] == 3
    assert [(i["size"], i["qty"]) for i in store.get("carts", uid)["items"]] == [("L", 3)]
    # errors
    assert client.patch(url, json={"size": "L", "new_size": "XL"}).status_code == 409    # sold out
    assert client.patch(url, json={"size": "L", "new_size": "XXXL"}).status_code == 409  # not offered
    assert client.patch(url, json={"size": "M", "new_size": "S"}).status_code == 404     # no such line
    assert client.patch(f"/cart/{uid}/items/nope", json={"size": "L", "new_size": "S"}).status_code == 404
    assert client.patch(url, json={"size": "L"}).status_code == 422
    assert client.patch(url, json={"size": "L", "new_size": "L"}).json()["count"] == 3  # no-op


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


# ---------- wishlist (independent of swipes) ----------

def test_wishlist_put_is_idempotent_and_keeps_feed(client, monkeypatch):
    from app.ai import memory
    from app.store import store
    calls = []
    monkeypatch.setattr(memory, "record_swipe", lambda u, p, a: calls.append((u, p["id"], a)))
    for _ in range(2):
        r = client.put("/wishlist/u_wish/items/hm-demo-1")
        assert r.status_code == 200 and r.json() == {"user_id": "u_wish", "product_id": "hm-demo-1", "saved": True}
    assert calls == [("u_wish", "hm-demo-1", "wishlist")]
    assert len(store.list("wishlist", user_id="u_wish")) == 1 and not store.list("swipes", user_id="u_wish")
    store.put("users", "u_wish", {"id": "u_wish", "price_ranges": RANGES})
    assert "hm-demo-1" in {c["id"] for c in client.get("/feed", params={"user_id": "u_wish"}).json()}

    client.put("/wishlist/u_wish/items/uniqlo-demo-1")
    assert client.get("/wishlist/u_wish/ids").json() == ["uniqlo-demo-1", "hm-demo-1"]  # newest first
    items = client.get("/wishlist/u_wish").json()
    assert [p["id"] for p in items] == ["uniqlo-demo-1", "hm-demo-1"] and items[0]["name"]


def test_wishlist_delete_is_idempotent(client):
    client.put("/wishlist/u_del/items/hm-demo-1")
    for _ in range(2):
        r = client.delete("/wishlist/u_del/items/hm-demo-1")
        assert r.status_code == 200 and r.json()["saved"] is False
    assert client.get("/wishlist/u_del/ids").json() == []
    assert client.delete("/wishlist/u_del/items/never-saved").json()["saved"] is False


def test_wishlist_unknown_product_404(client):
    r = client.put("/wishlist/u_wish/items/nope")
    assert r.status_code == 404 and r.json() == {"detail": "unknown product"}


def test_legacy_swipe_save_dismisses_and_wishlists(client):
    from app.store import store
    store.put("users", "u_leg", {"id": "u_leg", "price_ranges": RANGES})
    client.post("/swipe", json={"user_id": "u_leg", "product_id": "zara-demo-1", "action": "save"})
    assert "zara-demo-1" not in {c["id"] for c in client.get("/feed", params={"user_id": "u_leg"}).json()}
    assert client.get("/wishlist/u_leg/ids").json() == ["zara-demo-1"]
    client.put("/wishlist/u_leg/items/zara-demo-1")  # both sources: still one entry
    assert [p["id"] for p in client.get("/wishlist/u_leg").json()] == ["zara-demo-1"]

    # a save from before the wishlist collection (swipe only) still shows, and DELETE removes it
    store.put("swipes", "u_leg:asos-demo-1", {"user_id": "u_leg", "product_id": "asos-demo-1",
                                              "action": "wishlist", "swipe": "save", "at": "2020-01-01T00:00:00+00:00"})
    assert client.get("/wishlist/u_leg/ids").json() == ["zara-demo-1", "asos-demo-1"]
    client.delete("/wishlist/u_leg/items/asos-demo-1")
    assert client.get("/wishlist/u_leg/ids").json() == ["zara-demo-1"]
    assert "asos-demo-1" not in {c["id"] for c in client.get("/feed", params={"user_id": "u_leg"}).json()}


def test_feed_passes_smaller_k(client, monkeypatch):
    from app.commerce import router
    seen = {}

    def fake_pair(uid, cands, k):
        seen.update(n=len(cands), k=k)
        return []
    monkeypatch.setattr(router, "pair", fake_pair)
    cards = client.get("/feed", params={"user_id": "u_feed", "limit": 5}).json()
    assert seen == {"n": 4, "k": 10} and len(cards) == 4  # unranked top-up still fills the page
    client.get("/feed", params={"user_id": "u_feed", "limit": 20})
    assert seen["k"] == 24


def test_size_error_names_product(client):
    r = client.post("/cart/u_cart/items", json={"product_id": "zara-sold-out", "size": "M"})
    assert r.status_code == 422 and r.json() == {"detail": "size M is sold out for Gone tee"}
    r = client.post("/cart/u_cart/items", json={"product_id": "hm-demo-1", "size": "XXXL"})
    assert r.json()["detail"] == "size XXXL is not offered for Cropped baby tee"


def test_checkout_409_when_stock_changed(client):
    from app.store import store
    store.put("users", "u_409", {"id": "u_409", "price_ranges": RANGES})
    p = {**store.get("products", "uniqlo-demo-1"), "id": "uniqlo-flaky"}
    store.put("products", "uniqlo-flaky", p)
    client.post("/cart/u_409/items", json={"product_id": "uniqlo-flaky", "size": "M"})
    client.post("/cart/u_409/items", json={"product_id": "hm-demo-1", "size": "M"})
    store.put("products", "uniqlo-flaky", {**p, "sizes": [{"name": "M", "in_stock": False}]})
    r = client.post("/checkout/u_409")
    assert r.status_code == 409
    assert r.json()["detail"] == {"message": f"size M is sold out for {p['name']}",
                                  "unavailable": [{"product_id": "uniqlo-flaky", "size": "M"}]}
    assert client.get("/cart/u_409").json()["count"] == 2  # cart kept
    assert not store.list("orders", user_id="u_409")       # nothing charged


def test_feed_ranked_cards_first(client, monkeypatch):
    from app.commerce import router
    from app.models import PairResult
    from app.store import store
    store.put("users", "u_rank", {"id": "u_rank", "price_ranges": RANGES})
    dupe = {**store.get("products", "asos-demo-1"), "id": "asos-demo-1-red"}  # same style, other colour
    store.put("products", dupe["id"], dupe)
    ranked = ["asos-demo-1", "uniqlo-demo-1", "asos-demo-1-red"]
    monkeypatch.setattr(router, "pair", lambda uid, cands, k: [
        PairResult(product_id=pid, score=0.9, reason=f"why {pid}") for pid in ranked])
    try:
        cards = client.get("/feed", params={"user_id": "u_rank"}).json()
    finally:
        store.delete("products", dupe["id"])
    ids = [c["id"] for c in cards]
    assert set(ids[:2]) == {"asos-demo-1", "uniqlo-demo-1"} and all(c["reason"] for c in cards[:2])
    assert set(ids[2:]) == {"hm-demo-1", "zara-demo-1"} and not any(c["reason"] for c in cards[2:])
    assert "asos-demo-1-red" not in ids  # de-duped against the ranked style


def test_product_detail_ids_with_colons(client):
    from app.store import store
    store.put("products", "hm:123:light blue", {**store.get("products", "hm-demo-1"), "id": "hm:123:light blue"})
    try:
        assert client.get("/products/hm:123:light blue").json()["id"] == "hm:123:light blue"
    finally:
        store.delete("products", "hm:123:light blue")
