"""The Niche Card (Nabil, Oct 25): the user's Capital One Nessie account and purchase history, read live from Nessie.

GET /wallet/{user_id} -> {live, account, spent_usd, spent_month_usd, purchases}
- `account`: {last4, nickname, type, balance, rewards} straight from Nessie (the sandbox never lowers `balance`
  after purchases, so the app shows what was spent, from the purchases, not the balance), or null before the
  user's first checkout (reading never creates an account).
- `purchases`: newest first, Nessie's own records joined to our orders by Nessie purchase id: the store, our exact
  amount (Nessie keeps whole dollars), the items, the order id. Nessie purchases with no matching order still show.
- `live: false`: Nessie couldn't be reached (or no key), so the list comes from our saved orders instead.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter

from ..store import store
from . import nessie

log = logging.getLogger(__name__)
router = APIRouter(tags=["wallet"])


def _ours(user_id: str) -> dict[str, dict]:
    """Our paid store purchases by Nessie id, each with its order id and time."""
    out = {}
    for o in store.list("orders", user_id=user_id):
        for p in o.get("purchases") or []:
            if p.get("nessie_id"):
                out[p["nessie_id"]] = {**p, "order_id": o["id"], "created_at": o.get("created_at")}
    return out


def _row(nessie_id: str | None, ours: dict | None, theirs: dict | None, merchants: dict[str, str]) -> dict:
    retailer = (ours or {}).get("retailer") or merchants.get((theirs or {}).get("merchant_id") or "")
    date = (theirs or {}).get("purchase_date") or ((ours or {}).get("created_at") or "")[:10]
    return {
        "nessie_id": nessie_id, "retailer": retailer,
        "store_name": nessie.MERCHANTS.get(retailer or "", (retailer or "Store").title()),
        "amount_usd": (ours or {}).get("amount_usd", (theirs or {}).get("amount")),
        "nessie_amount": (theirs or {}).get("amount"),
        "date": date, "status": (theirs or {}).get("status") or (ours or {}).get("status"),
        "description": (theirs or {}).get("description") or "",
        "order_id": (ours or {}).get("order_id"),
        "items": [{"name": i.get("name", ""), "size": i.get("size"), "qty": i.get("qty", 1)}
                  for i in (ours or {}).get("items") or []],
    }


@router.get("/wallet/{user_id}")
def wallet(user_id: str):
    ours = _ours(user_id)
    merchants = {mid: r for r, mid in (store.get("nessie", "merchants") or {}).items()}
    account_id, account, rows, live = nessie.account_of(user_id), None, [], False
    if account_id and os.getenv("NESSIE_API_KEY"):
        try:
            a = nessie.get_account(account_id)
            account = {"last4": account_id[-4:], "nickname": a.get("nickname"), "type": a.get("type"),
                       "balance": a.get("balance"), "rewards": a.get("rewards")}
            rows = [_row(t.get("_id"), ours.get(t.get("_id")), t, merchants) for t in nessie.list_purchases(account_id)]
            live = True
        except nessie.NessieError as e:
            log.warning("wallet: nessie unreachable for %s: %s", user_id, e)
    if not live:  # Nessie down / no key / no account yet: our own receipts
        rows = [_row(nid, p, None, merchants) for nid, p in ours.items()]
    rows.sort(key=lambda r: (r["date"] or "", r["nessie_id"] or ""), reverse=True)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    paid = [r for r in rows if r["status"] in ("completed", "paid", "executed", "pending")]
    return {"live": live, "account": account,
            "spent_usd": round(sum(r["amount_usd"] or 0 for r in paid), 2),
            "spent_month_usd": round(sum(r["amount_usd"] or 0 for r in paid if (r["date"] or "").startswith(month)), 2),
            "purchases": rows}
