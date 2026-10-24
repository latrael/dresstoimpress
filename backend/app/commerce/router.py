"""Commerce: /feed /products /swipe /cart /wishlist /checkout (Nabil).

Collections: products (ingest/live_search/seed), swipes ("{user}:{product}"), carts (doc id = user_id),
orders. Swipe actions are mapped to the memory vocabulary (cart / wishlist / discard) before storing,
so ai.memory and ai.service.pair read them as-is.
"""
from __future__ import annotations

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

    # rank a wider pool than we show, so de-duping styles and mixing stores still fills the page
    ranked = pair(user_id, list(cands), k=min(50, limit * 3))
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
    in_cart = False
    if req.action == "like" and req.size:
        _add_to_cart(req.user_id, req.product_id, req.size, 1)
        in_cart = True
    return {"user_id": req.user_id, "product_id": req.product_id, "action": req.action, "in_cart": in_cart}


@router.get("/wishlist/{user_id}")
def wishlist(user_id: str):
    saves = sorted(store.list("swipes", user_id=user_id, action="wishlist"), key=lambda s: s["at"], reverse=True)
    return [p for s in saves if (p := store.get("products", s["product_id"]))]


# ---------- cart ----------

def _check_size(p: dict, size: str) -> None:
    s = next((s for s in _sizes(p) if s.get("name") == size), None)
    if not s:
        raise HTTPException(422, f"size {size} not offered")
    if not _size_ok(s) or not p.get("in_stock", True):
        raise HTTPException(422, f"size {size} sold out")


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

def create_nessie_purchase(account_id: str, merchant_id: str | None, amount: float, description: str) -> dict:
    """NESSIE STUB. TODO: POST http://api.nessieisreal.com/accounts/{account_id}/purchases?key=NESSIE_API_KEY
    body {merchant_id, medium: "balance", purchase_date, amount, description}. Return the created purchase."""
    raise NotImplementedError("Nessie not wired yet")


@router.post("/checkout/{user_id}")
def checkout(user_id: str):
    """One purchase per retailer. Status stays `pending_nessie` until the Nessie call is wired."""
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
            try:
                res = create_nessie_purchase(os.getenv("NESSIE_ACCOUNT_ID", ""), purchase["merchant_id"],
                                             purchase["amount_usd"], f"dresstoimpress {order_id} {g['retailer']}")
                purchase.update(status="paid", nessie_id=res.get("_id"))
            except NotImplementedError:
                pass
            except Exception as e:  # noqa: BLE001
                log.warning("nessie purchase failed: %s", e)
                purchase["status"] = "nessie_failed"
        purchases.append(purchase)
    store.put("orders", order_id, {"id": order_id, "user_id": user_id, "purchases": purchases,
                                   "total_usd": cart["total_usd"], "created_at": _now()})
    store.put("carts", user_id, {"user_id": user_id, "items": []})
    return {"order_id": order_id, "purchases": purchases, "total_usd": cart["total_usd"]}
