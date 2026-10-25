"""Capital One Nessie client (sandbox bank API). Auth is ?key=NESSIE_API_KEY; HTTPS only (http hangs).

Ids are cached in the store collection `nessie`: doc `merchants` {retailer: merchant_id} and doc `accounts`
{user_id: {customer_id, account_id}}, so each retailer/user is created on Nessie once.
Quirks: every POST answers {"code": 201, "message", "objectCreated": {..., "_id"}}; `amount` is stored as an
int (cents are truncated); ids aren't validated; GET /accounts/{id}/purchases 400s if any purchase on the
account lacks `status`, so we always send one.
"""
from __future__ import annotations

import os
from datetime import date

import httpx

from ..store import store

BASE = "https://api.nessieisreal.com"
DEMO_USER = "u_demo"  # NESSIE_ACCOUNT_ID, if set, is used for this user instead of creating one
MERCHANTS = {"hm": "H&M", "uniqlo": "Uniqlo", "zara": "Zara", "mango": "Mango", "asos": "ASOS",
             "princesspolly": "Princess Polly", "edikted": "Edikted", "brandymelville": "Brandy Melville",
             "trueclassic": "True Classic", "kith": "Kith", "stussy": "Stüssy"}
ADDRESS = {"street_number": "2650", "street_name": "Telegraph Ave", "city": "Berkeley", "state": "CA",
           "zip": "94704"}
GEOCODE = {"lat": 37.8611, "lng": -122.2588}


class NessieError(RuntimeError):
    pass


def _call(method: str, path: str, body: dict | None = None):
    try:
        r = httpx.request(method, BASE + path, params={"key": os.environ["NESSIE_API_KEY"]}, json=body, timeout=15)
    except httpx.HTTPError as e:
        raise NessieError(f"{method} {path}: {type(e).__name__}") from None  # never echo the URL (has the key)
    if r.status_code >= 400:
        raise NessieError(f"{method} {path}: {r.status_code} {r.text[:200]}")
    return r.json()


def _created(method: str, path: str, body: dict) -> dict:
    obj = (_call(method, path, body) or {}).get("objectCreated") or {}
    if not obj.get("_id"):
        raise NessieError(f"{method} {path}: no objectCreated._id")
    return obj


def create_customer(first_name: str, last_name: str, address: dict = ADDRESS) -> dict:
    return _created("POST", "/customers", {"first_name": first_name, "last_name": last_name, "address": address})


def create_account(customer_id: str, nickname: str, type: str = "Credit Card", balance: int = 5000) -> dict:
    return _created("POST", f"/customers/{customer_id}/accounts",
                    {"type": type, "nickname": nickname, "rewards": 0, "balance": balance})


def create_merchant(name: str, category: str = "clothing") -> dict:
    return _created("POST", "/merchants", {"name": name, "category": category, "address": ADDRESS,
                                           "geocode": GEOCODE})


def create_purchase(account_id: str, merchant_id: str, amount: float, description: str,
                    status: str = "completed") -> dict:
    return _created("POST", f"/accounts/{account_id}/purchases", {
        "merchant_id": merchant_id, "medium": "balance", "purchase_date": date.today().isoformat(),
        "amount": round(amount), "status": status, "description": description})


def list_purchases(account_id: str) -> list[dict]:
    return _call("GET", f"/accounts/{account_id}/purchases")


def get_account(account_id: str) -> dict:
    return _call("GET", f"/accounts/{account_id}")


def account_of(user_id: str) -> str | None:
    """The user's Nessie account id if they have one (never creates it: reads stay side-effect free)."""
    if user_id == DEMO_USER and os.getenv("NESSIE_ACCOUNT_ID"):
        return os.environ["NESSIE_ACCOUNT_ID"]
    return ((store.get("nessie", "accounts") or {}).get(user_id) or {}).get("account_id")


def ensure_merchant(retailer: str) -> str:
    ids = store.get("nessie", "merchants") or {}
    if retailer not in ids:
        ids[retailer] = create_merchant(MERCHANTS.get(retailer, retailer.title()))["_id"]
        store.put("nessie", "merchants", ids)
    return ids[retailer]


def ensure_account(user_id: str) -> str:
    if user_id == DEMO_USER and os.getenv("NESSIE_ACCOUNT_ID"):
        return os.environ["NESSIE_ACCOUNT_ID"]
    accts = store.get("nessie", "accounts") or {}
    if user_id not in accts:
        cust = create_customer("DressToImpress", user_id)
        acct = create_account(cust["_id"], f"dresstoimpress {user_id}")
        accts[user_id] = {"customer_id": cust["_id"], "account_id": acct["_id"]}
        store.put("nessie", "accounts", accts)
    return accts[user_id]["account_id"]
