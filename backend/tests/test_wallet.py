"""GET /wallet/{user} (the Niche Card): the Nessie account + purchases read live, joined to our orders; our saved
receipts when Nessie can't be reached; never creates an account on read."""
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    monkeypatch.setattr(store, "root", Path(tmp_path))
    monkeypatch.setenv("NESSIE_API_KEY", "test")
    store.put("nessie", "accounts", {"u_w": {"customer_id": "c1", "account_id": "acct-0001-abcd"}})
    store.put("nessie", "merchants", {"hm": "m-hm", "uniqlo": "m-uq"})
    store.put("orders", "o1", {"id": "o1", "user_id": "u_w", "created_at": f"{TODAY}T10:00:00+00:00", "total_usd": 39.99,
                               "purchases": [{"retailer": "hm", "amount_usd": 39.99, "status": "paid", "nessie_id": "n1",
                                              "items": [{"name": "Baggy Jeans", "size": "M", "qty": 1}]}]})
    return TestClient(app)


THEIRS = [{"_id": "n1", "merchant_id": "m-hm", "amount": 40, "status": "completed", "purchase_date": TODAY,
           "description": "dresstoimpress: 1 item"},
          {"_id": "n2", "merchant_id": "m-uq", "amount": 25, "status": "completed", "purchase_date": "2026-01-02",
           "description": "older"}]


def test_wallet_reads_nessie_live_and_joins_our_orders(client, monkeypatch):
    from app.commerce import nessie
    monkeypatch.setattr(nessie, "get_account", lambda a: {"nickname": "dti u_w", "type": "Credit Card",
                                                          "balance": 5000, "rewards": 0})
    monkeypatch.setattr(nessie, "list_purchases", lambda a: THEIRS)
    w = client.get("/wallet/u_w").json()
    assert w["live"] is True
    assert w["account"] == {"last4": "abcd", "nickname": "dti u_w", "type": "Credit Card", "balance": 5000, "rewards": 0}
    first, second = w["purchases"]  # newest first
    assert (first["nessie_id"], first["store_name"], first["amount_usd"], first["nessie_amount"]) == ("n1", "H&M", 39.99, 40)
    assert first["order_id"] == "o1" and first["items"] == [{"name": "Baggy Jeans", "size": "M", "qty": 1}]
    assert (second["store_name"], second["amount_usd"], second["order_id"]) == ("Uniqlo", 25, None)  # no order: still shown
    assert w["spent_usd"] == 64.99 and w["spent_month_usd"] == 39.99


def test_wallet_falls_back_to_our_receipts_when_nessie_is_down(client, monkeypatch):
    from app.commerce import nessie

    def down(*a):
        raise nessie.NessieError("GET /accounts: ConnectTimeout")
    monkeypatch.setattr(nessie, "get_account", down)
    w = client.get("/wallet/u_w").json()
    assert w["live"] is False and w["account"] is None
    assert [(r["nessie_id"], r["store_name"], r["amount_usd"], r["status"]) for r in w["purchases"]] == \
        [("n1", "H&M", 39.99, "paid")]
    assert w["spent_usd"] == 39.99


def test_wallet_never_creates_an_account(client, monkeypatch):
    from app.commerce import nessie
    from app.store import store
    monkeypatch.setattr(nessie, "create_customer", lambda *a, **k: pytest.fail("a read must not create"))
    w = client.get("/wallet/u_new").json()
    assert w == {"live": False, "account": None, "spent_usd": 0, "spent_month_usd": 0, "purchases": []}
    assert "u_new" not in (store.get("nessie", "accounts") or {})
