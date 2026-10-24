import os
import uuid

import httpx
import pytest

os.environ["MOCK_AI"] = "1"
os.environ.setdefault("NESSIE_API_KEY", "")  # before app.main's load_dotenv; each test sets its own


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fresh store + a fake Nessie that records every call."""
    from fastapi.testclient import TestClient
    from app.commerce import nessie
    from app.main import app
    from app.store import store
    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setenv("NESSIE_API_KEY", "test-key")
    monkeypatch.delenv("NESSIE_ACCOUNT_ID", raising=False)
    for pid, ret, price in (("hm-1", "hm", 12.99), ("hm-2", "hm", 20.0), ("uq-1", "uniqlo", 24.9)):
        store.put("products", pid, {"id": pid, "retailer": ret, "name": f"Item {pid}", "category": "top",
                                    "price_usd": price, "sizes": [{"name": "M", "in_stock": True}], "in_stock": True})
    calls, fail = [], {"on": None}

    def fake(method, url, params=None, json=None, timeout=None):
        path = url.removeprefix(nessie.BASE)
        calls.append((method, path, json))
        assert params == {"key": "test-key"}
        if fail["on"] and fail["on"] in path:
            return httpx.Response(400, text="1 validation error", request=httpx.Request(method, url))
        if method == "GET":
            return httpx.Response(200, json=[], request=httpx.Request(method, url))
        obj = {**(json or {}), "_id": uuid.uuid4().hex}
        return httpx.Response(201, json={"code": 201, "message": "Created", "objectCreated": obj},
                              request=httpx.Request(method, url))

    monkeypatch.setattr(nessie.httpx, "request", fake)
    c = TestClient(app)

    def buy(user, *pids):
        for pid in pids:
            c.post(f"/cart/{user}/items", json={"product_id": pid, "size": "M"})
        return c.post(f"/checkout/{user}")
    return c, calls, fail, buy, store


def _n(calls, suffix):
    return sum(1 for m, p, _ in calls if m == "POST" and p.endswith(suffix))


def test_one_paid_purchase_per_retailer(env):
    c, calls, _, buy, _ = env
    r = buy("u_a", "hm-1", "hm-2", "uq-1")
    assert r.status_code == 200
    ps = {p["retailer"]: p for p in r.json()["purchases"]}
    assert set(ps) == {"hm", "uniqlo"} and all(p["status"] == "paid" and p["nessie_id"] for p in ps.values())
    assert all(p["merchant_id"] for p in ps.values())
    bodies = [b for m, p, b in calls if p.endswith("/purchases")]
    assert len(bodies) == 2
    hm = next(b for b in bodies if b["merchant_id"] == ps["hm"]["merchant_id"])
    assert hm["description"] == "dresstoimpress: 2 items (Item hm-1, Item hm-2)"
    assert hm["medium"] == "balance" and hm["status"] == "completed" and hm["amount"] == 33
    assert len(hm["purchase_date"]) == 10  # YYYY-MM-DD
    names = sorted(b["name"] for m, p, b in calls if p == "/merchants")
    assert names == ["H&M", "Uniqlo"]


def test_merchants_and_accounts_cached(env):
    c, calls, _, buy, store = env
    buy("u_b", "hm-1", "uq-1")
    assert (_n(calls, "/customers"), _n(calls, "/accounts"), _n(calls, "/merchants")) == (1, 1, 2)
    calls.clear()
    assert all(p["status"] == "paid" for p in buy("u_b", "hm-2", "uq-1").json()["purchases"])
    assert (_n(calls, "/customers"), _n(calls, "/accounts"), _n(calls, "/merchants")) == (0, 0, 0)
    assert _n(calls, "/purchases") == 2
    assert set(store.get("nessie", "merchants")) == {"hm", "uniqlo"}
    assert set(store.get("nessie", "accounts")["u_b"]) == {"customer_id", "account_id"}
    calls.clear()
    buy("u_other", "hm-1")  # new user: new customer+account, merchant reused
    assert (_n(calls, "/customers"), _n(calls, "/merchants")) == (1, 0)


def test_account_override_for_demo_user(env, monkeypatch):
    c, calls, _, buy, _ = env
    monkeypatch.setenv("NESSIE_ACCOUNT_ID", "acct-env")
    buy("u_demo", "hm-1")
    assert _n(calls, "/customers") == 0
    assert any(p == "/accounts/acct-env/purchases" for _, p, _ in calls)


def test_failure_is_nessie_failed_and_order_kept(env):
    c, calls, fail, buy, store = env
    fail["on"] = "/purchases"
    r = buy("u_c", "hm-1", "uq-1")
    assert r.status_code == 200
    ps = r.json()["purchases"]
    assert all(p["status"] == "nessie_failed" and "400" in p["error"] and "test-key" not in p["error"] for p in ps)
    assert store.get("orders", r.json()["order_id"])["purchases"][0]["status"] == "nessie_failed"
    assert c.get("/cart/u_c").json()["count"] == 0


def test_no_key_stays_pending(env, monkeypatch):
    c, calls, _, buy, _ = env
    monkeypatch.setenv("NESSIE_API_KEY", "")
    ps = buy("u_d", "hm-1", "uq-1").json()["purchases"]
    assert all(p["status"] == "pending_nessie" and p["merchant_id"] is None for p in ps)
    assert calls == []


def test_orders_newest_first(env):
    c, _, _, buy, _ = env
    first = buy("u_e", "hm-1").json()["order_id"]
    second = buy("u_e", "uq-1").json()["order_id"]
    buy("u_f", "hm-2")
    assert [o["id"] for o in c.get("/orders/u_e").json()] == [second, first]
    assert c.get("/orders/nobody").json() == []


# ---------- POST /orders/{order_id}/retry ----------

def test_retry_paid_order_is_noop(env):
    c, calls, _, buy, _ = env
    r = buy("u_r1", "hm-1", "uq-1").json()
    calls.clear()
    for _ in range(2):  # safe to repeat
        again = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r1"})
        assert again.status_code == 200 and again.json() == r
    assert calls == []  # no new Nessie call


def test_retry_failed_purchase_becomes_paid_and_leaves_paid_store_alone(env):
    c, calls, fail, buy, store = env
    buy("u_r2", "uq-1")  # caches the uniqlo merchant, so only hm can fail below
    fail["on"] = "/merchants"  # hm's merchant creation fails; uniqlo pays
    r = buy("u_r2", "hm-1", "uq-1").json()
    ps = {p["retailer"]: p for p in r["purchases"]}
    assert ps["hm"]["status"] == "nessie_failed" and ps["uniqlo"]["status"] == "paid"
    uq_paid = ps["uniqlo"]

    fail["on"] = None
    calls.clear()
    out = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r2"})
    assert out.status_code == 200
    ps = {p["retailer"]: p for p in out.json()["purchases"]}
    assert ps["hm"]["status"] == "paid" and ps["hm"]["nessie_id"] and "error" not in ps["hm"]
    assert ps["uniqlo"] == uq_paid  # the already-paid store is untouched
    assert _n(calls, "/purchases") == 1  # only hm was charged
    hm_body = next(b for m, p, b in calls if p.endswith("/purchases"))
    assert hm_body["merchant_id"] == ps["hm"]["merchant_id"] and hm_body["amount"] == 13
    stored = {p["retailer"]: p for p in store.get("orders", r["order_id"])["purchases"]}
    assert stored["hm"]["status"] == "paid"

    calls.clear()  # everything is paid now: retry is a no-op
    assert c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r2"}).json() == out.json()
    assert calls == []


def test_retry_fails_again_stays_failed(env):
    c, _, fail, buy, store = env
    fail["on"] = "/purchases"
    r = buy("u_r3", "hm-1").json()
    out = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r3"})
    assert out.status_code == 200
    p = out.json()["purchases"][0]
    assert p["status"] == "nessie_failed" and "400" in p["error"] and "test-key" not in p["error"]
    assert p["retried_at"]
    assert store.get("orders", r["order_id"])["purchases"][0]["status"] == "nessie_failed"


def test_retry_one_retailer_only(env):
    c, calls, fail, buy, _ = env
    fail["on"] = "/purchases"
    r = buy("u_r4", "hm-1", "uq-1").json()
    fail["on"] = None
    calls.clear()
    out = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r4", "retailer": "uniqlo"}).json()
    ps = {p["retailer"]: p for p in out["purchases"]}
    assert ps["uniqlo"]["status"] == "paid" and ps["hm"]["status"] == "nessie_failed"
    assert _n(calls, "/purchases") == 1
    assert c.post(f"/orders/{r['order_id']}/retry",
                  params={"user_id": "u_r4", "retailer": "zara"}).status_code == 404


def test_retry_pending_needs_key(env, monkeypatch):
    c, calls, _, buy, _ = env
    monkeypatch.setenv("NESSIE_API_KEY", "")
    r = buy("u_r5", "hm-1").json()
    out = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r5"})
    assert out.status_code == 503 and calls == []
    monkeypatch.setenv("NESSIE_API_KEY", "test-key")
    out = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "u_r5"}).json()
    assert out["purchases"][0]["status"] == "paid"


def test_retry_does_not_touch_other_orders(env):
    c, _, fail, buy, store = env
    fail["on"] = "/purchases"
    first = buy("u_r6", "hm-1").json()
    second = buy("u_r6", "hm-2").json()
    fail["on"] = None
    c.post(f"/orders/{first['order_id']}/retry", params={"user_id": "u_r6"})
    assert store.get("orders", first["order_id"])["purchases"][0]["status"] == "paid"
    assert store.get("orders", second["order_id"])["purchases"][0]["status"] == "nessie_failed"


def test_retry_404_and_403(env):
    c, calls, fail, buy, store = env
    fail["on"] = "/purchases"
    r = buy("u_r7", "hm-1").json()
    fail["on"] = None
    calls.clear()
    assert c.post("/orders/nope/retry", params={"user_id": "u_r7"}).status_code == 404
    bad = c.post(f"/orders/{r['order_id']}/retry", params={"user_id": "someone_else"})
    assert bad.status_code == 403 and bad.json() == {"detail": "not your order"}
    assert c.post(f"/orders/{r['order_id']}/retry").status_code == 422  # user_id is required
    assert calls == []
    assert store.get("orders", r["order_id"])["purchases"][0]["status"] == "nessie_failed"
