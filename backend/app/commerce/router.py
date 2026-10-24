"""Commerce: /feed /products /swipe /cart /wishlist /checkout /orders (Nabil).

Collections: products (ingest/live_search/seed), swipes ("{user}:{product}"), wishlist ("{user}:{product}",
independent of swipes so saving never dismisses from the feed), carts (doc id = user_id), orders, nessie
(cached Nessie ids, see nessie.py). Swipe actions are mapped to the memory vocabulary
(cart / wishlist / discard) before storing, so ai.memory and ai.service.pair read them as-is.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from itertools import zip_longest
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai import memory
from ..ai.service import _in_budget, pair
from ..store import store
from . import nessie

log = logging.getLogger(__name__)
router = APIRouter(tags=["commerce"])

# app vocabulary -> ai.memory vocabulary (memory.LIKED = cart/wishlist/share)
MEMORY_ACTION = {"like": "cart", "save": "wishlist", "discard": "discard"}


class SwipeRequest(BaseModel):
    user_id: str
    product_id: str
    action: Literal["like", "save", "discard"]
    size: Optional[str] = None


class CartAdd(BaseModel):
    product_id: str
    size: str
    qty: int = Field(1, ge=1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _product(pid: str) -> dict:
    p = store.get("products", pid)
    if not p:
        raise HTTPException(404, "unknown product")
    return p


def _sizes(p: dict) -> list[dict]:
    """Sizes as [{name, in_stock}] whatever shape they were stored in."""
    return [s if isinstance(s, dict) else {"name": str(s), "in_stock": True} for s in p.get("sizes") or []]


def _size_ok(s: dict) -> bool:
    return bool(s.get("in_stock", s.get("inStock", True)))


def _buyable(p: dict) -> bool:
    sizes = _sizes(p)
    return p.get("in_stock", True) and (not sizes or any(_size_ok(s) for s in sizes))


def _price(p: dict) -> float:
    return float(p.get("sale_price_usd") or p.get("price_usd") or 0)


def _round_robin(products: list[dict], key: str) -> list[dict]:
    """Round-robin across values of `key`, keeping each group's order."""
    groups: dict[str, list[dict]] = {}
    for p in products:
        groups.setdefault(p.get(key, ""), []).append(p)
    return [p for row in zip_longest(*groups.values()) for p in row if p]


def _interleave(products: list[dict]) -> list[dict]:
    """One card per style (H&M lists each colour as its own article), then alternate categories
    within each retailer and retailers overall, so the feed isn't ten pairs of jeans."""
    seen, unique = set(), []
    for p in products:
        style = (p.get("retailer"), p.get("name", "").strip().lower())
        if style not in seen:
            seen.add(style)
            unique.append(p)
    by_ret: dict[str, list[dict]] = {}
    for p in unique:
        by_ret.setdefault(p.get("retailer", ""), []).append(p)
    mixed = [_round_robin(ps, "category") for ps in by_ret.values()]
    return [p for row in zip_longest(*mixed) for p in row if p]


def _swiped(user_id: str) -> set[str]:
    return {s["product_id"] for s in store.list("swipes", user_id=user_id)}


# ---------- feed / products ----------

@router.get("/feed")
def feed(user_id: str, limit: int = 20, category: Optional[str] = None, retailer: Optional[str] = None):
    """In-stock, in-budget, unswiped products ordered by ai.service.pair(), plus reason/score/pairs_with."""
    ranges = (store.get("users", user_id) or {}).get("price_ranges", {})
    swiped = _swiped(user_id)
    where = {k: v for k, v in {"category": category, "retailer": retailer}.items() if v}
    cands = {p["id"]: p for p in store.list("products", **where)
             if p["id"] not in swiped and _buyable(p) and _in_budget(p, ranges)}
    if not cands:
        return []

    # Claude sees up to 50 candidates (pair caps it) but writes ~24 reasons (one per ranked item, the slow
    # part); the unranked rest tops up the page so de-duping styles and mixing stores still fills it
    ranked = pair(user_id, list(cands), k=min(24, limit * 2))
    picked = [{**cands[r.product_id], "reason": r.reason, "score": r.score, "pairs_with": r.pairs_with}
              for r in ranked if r.product_id in cands]
    seen = {p["id"] for p in picked}
    rest = [{**p, "reason": "", "score": 0.0, "pairs_with": []} for pid, p in cands.items() if pid not in seen]
    return _interleave(picked + rest)[:limit]


@router.get("/products/{product_id}")
def get_product(product_id: str):
    return _product(product_id)


# ---------- swipe / wishlist ----------

@router.post("/swipe")
def swipe(req: SwipeRequest):
    p = _product(req.product_id)
    if req.action == "like" and req.size:
        _check_size(p, req.size)  # 422 before anything is recorded
    action = MEMORY_ACTION[req.action]
    store.put("swipes", f"{req.user_id}:{req.product_id}", {
        "user_id": req.user_id, "product_id": req.product_id, "action": action,
        "swipe": req.action, "size": req.size, "at": _now(),
    })
    memory.record_swipe(req.user_id, p, action)
    if req.action == "save":  # legacy save: still dismisses (swipe above) and joins the wishlist
        _save(req.user_id, req.product_id)
    in_cart = False
    if req.action == "like" and req.size:
        _add_to_cart(req.user_id, req.product_id, req.size, 1)
        in_cart = True
    return {"user_id": req.user_id, "product_id": req.product_id, "action": req.action, "in_cart": in_cart}


def _delete(collection: str, doc_id: str) -> None:
    if hasattr(store, "db"):  # FirestoreStore
        store.db.collection(collection).document(doc_id).delete()
        return
    with store._lock:  # JsonStore has no delete; edit the file directly (as scripts/load_products.py)
        data = store._load(collection)
        if data.pop(doc_id, None) is not None:
            store._path(collection).write_text(json.dumps(data, indent=2))


def _save(user_id: str, product_id: str) -> None:
    store.put("wishlist", f"{user_id}:{product_id}", {"user_id": user_id, "product_id": product_id, "saved_at": _now()})


def _legacy_save(user_id: str, product_id: str) -> Optional[dict]:
    """Pre-wishlist saves only exist as swipes with action=wishlist; `unsaved` marks a DELETE."""
    s = store.get("swipes", f"{user_id}:{product_id}")
    return s if s and s.get("action") == "wishlist" and not s.get("unsaved") else None


def _saved(user_id: str) -> list[dict]:
    """[{product_id, saved_at}] newest first: wishlist docs plus legacy swipe saves, de-duplicated."""
    rows = {s["product_id"]: s["at"] for s in store.list("swipes", user_id=user_id, action="wishlist")
            if not s.get("unsaved")}
    rows.update({w["product_id"]: w["saved_at"] for w in store.list("wishlist", user_id=user_id)})
    return [{"product_id": pid, "saved_at": at} for pid, at in sorted(rows.items(), key=lambda r: r[1], reverse=True)]


@router.put("/wishlist/{user_id}/items/{product_id}")
def wishlist_put(user_id: str, product_id: str):
    """Ensure saved (idempotent). No swipe record, so the product stays in the feed."""
    p = _product(product_id)
    if not store.get("wishlist", f"{user_id}:{product_id}"):
        if not _legacy_save(user_id, product_id):
            memory.record_swipe(user_id, p, "wishlist")  # first save only
        _save(user_id, product_id)
    return {"user_id": user_id, "product_id": product_id, "saved": True}


@router.delete("/wishlist/{user_id}/items/{product_id}")
def wishlist_delete(user_id: str, product_id: str):
    """Ensure unsaved (idempotent). A legacy swipe save stays a swipe (still dismissed) but leaves the wishlist."""
    _delete("wishlist", f"{user_id}:{product_id}")
    if s := _legacy_save(user_id, product_id):
        store.put("swipes", f"{user_id}:{product_id}", {**s, "unsaved": True})
    return {"user_id": user_id, "product_id": product_id, "saved": False}


@router.get("/wishlist/{user_id}")
def wishlist(user_id: str):
    return [p for s in _saved(user_id) if (p := store.get("products", s["product_id"]))]


@router.get("/wishlist/{user_id}/ids")
def wishlist_ids(user_id: str):
    return [p["id"] for p in wishlist(user_id)]  # same set as GET /wishlist (skips dropped products)


# ---------- cart ----------

def _size_problem(p: dict, size: str) -> Optional[str]:
    s = next((s for s in _sizes(p) if s.get("name") == size), None)
    if not s:
        return f"size {size} is not offered for {p.get('name', p['id'])}"
    if not _size_ok(s) or not p.get("in_stock", True):
        return f"size {size} is sold out for {p.get('name', p['id'])}"
    return None


def _check_size(p: dict, size: str) -> None:
    if msg := _size_problem(p, size):
        raise HTTPException(422, msg)


def _cart(user_id: str) -> dict:
    return store.get("carts", user_id) or {"user_id": user_id, "items": []}


def _add_to_cart(user_id: str, product_id: str, size: str, qty: int) -> dict:
    cart = _cart(user_id)
    item = next((i for i in cart["items"] if i["product_id"] == product_id and i["size"] == size), None)
    if item:
        item["qty"] += qty
    else:
        cart["items"].append({"product_id": product_id, "size": size, "qty": qty, "added_at": _now()})
    store.put("carts", user_id, cart)
    return cart


def _grouped(user_id: str) -> dict:
    groups: dict[str, dict] = {}
    for i in _cart(user_id)["items"]:
        p = store.get("products", i["product_id"])
        if not p:
            continue  # product dropped from the catalog
        g = groups.setdefault(p["retailer"], {"retailer": p["retailer"], "items": [], "subtotal_usd": 0.0})
        g["items"].append({**i, "product": p})
        g["subtotal_usd"] = round(g["subtotal_usd"] + _price(p) * i["qty"], 2)
    gs = list(groups.values())
    return {"user_id": user_id, "groups": gs, "total_usd": round(sum(g["subtotal_usd"] for g in gs), 2),
            "count": sum(i["qty"] for g in gs for i in g["items"])}


@router.post("/cart/{user_id}/items")
def cart_add(user_id: str, req: CartAdd):
    _check_size(_product(req.product_id), req.size)
    _add_to_cart(user_id, req.product_id, req.size, req.qty)
    return _grouped(user_id)


@router.get("/cart/{user_id}")
def cart_get(user_id: str):
    return _grouped(user_id)


@router.delete("/cart/{user_id}/items/{product_id}")
def cart_remove(user_id: str, product_id: str, size: Optional[str] = None):
    """Removes that product (only the given size, if `size` is passed)."""
    cart = _cart(user_id)
    cart["items"] = [i for i in cart["items"]
                     if not (i["product_id"] == product_id and (size is None or i["size"] == size))]
    store.put("carts", user_id, cart)
    return _grouped(user_id)


# ---------- checkout ----------

def _pay(user_id: str, purchase: dict) -> None:
    """Real Nessie purchase for one retailer group; failures are recorded on the purchase, never raised."""
    items = purchase["items"]
    n = sum(i["qty"] for i in items)
    desc = f"dresstoimpress: {n} item{'s' * (n != 1)} ({', '.join(i['name'] for i in items)})"[:250]
    try:
        account_id = nessie.ensure_account(user_id)
        purchase["merchant_id"] = nessie.ensure_merchant(purchase["retailer"])
        res = nessie.create_purchase(account_id, purchase["merchant_id"], purchase["amount_usd"], desc)
        purchase.update(status="paid", nessie_id=res["_id"], nessie_account_id=account_id)
    except Exception as e:  # noqa: BLE001
        log.warning("nessie purchase failed: %s", e)
        purchase.update(status="nessie_failed", error=str(e)[:200])


@router.post("/checkout/{user_id}")
def checkout(user_id: str):
    """One Nessie purchase per retailer (`paid`), or `pending_nessie` when NESSIE_API_KEY isn't set.
    409 {message, unavailable: [{product_id, size}]} if any item went out of stock; nothing is charged."""
    bad, msgs = [], []
    for i in _cart(user_id)["items"]:  # stock may have changed since add: charge nothing, keep the cart
        p = store.get("products", i["product_id"])
        msg = _size_problem(p, i["size"]) if p else f"{i['product_id']} is no longer available"
        if msg:
            bad.append({"product_id": i["product_id"], "size": i["size"]})
            msgs.append(msg)
    if bad:
        raise HTTPException(409, {"message": "; ".join(msgs), "unavailable": bad})
    cart = _grouped(user_id)
    if not cart["groups"]:
        raise HTTPException(400, "cart is empty")
    order_id = uuid.uuid4().hex[:12]
    purchases = []
    for g in cart["groups"]:
        purchase = {
            "retailer": g["retailer"], "merchant_id": None, "amount_usd": g["subtotal_usd"],
            "items": [{"product_id": i["product_id"], "size": i["size"], "qty": i["qty"],
                       "price_usd": _price(i["product"]), "name": i["product"].get("name", "")} for i in g["items"]],
            "status": "pending_nessie",
        }
        if os.getenv("NESSIE_API_KEY"):
            _pay(user_id, purchase)
        purchases.append(purchase)
    order = {"id": order_id, "user_id": user_id, "purchases": purchases,
             "total_usd": cart["total_usd"], "created_at": _now()}
    store.put("orders", order_id, order)
    store.put("carts", user_id, {"user_id": user_id, "items": []})
    return {"order_id": order_id, "purchases": purchases, "total_usd": cart["total_usd"],
            "created_at": order["created_at"]}


@router.get("/orders/{user_id}")
def orders(user_id: str):
    return sorted(store.list("orders", user_id=user_id), key=lambda o: o["created_at"], reverse=True)
