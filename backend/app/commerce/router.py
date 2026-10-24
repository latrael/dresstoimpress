"""Commerce: /feed /products /swipe /cart /wishlist /checkout /orders (Nabil).

Collections: products (ingest/live_search/seed), swipes ("{user}:{product}"), wishlist ("{user}:{product}",
independent of swipes so saving never dismisses from the feed), carts (doc id = user_id), orders, nessie
(cached Nessie ids, see nessie.py). Swipe actions are mapped to the memory vocabulary
(cart / wishlist / discard) before storing, so ai.memory and ai.service.pair read them as-is.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from itertools import zip_longest
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai import memory
from ..ai.colors import _label_words, same_color
from ..ai.compat import as_product
from ..ai.complete_look import _as_closet_shape
from ..ai.outfit_rules import score_product
from ..ai.router import _usual_size
from ..ai.service import _in_budget, pair
from ..ai.sizing import recommend_size
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


def _dedupe(products: list[dict], seen: Optional[set] = None) -> list[dict]:
    """One card per style (H&M lists each colour as its own article); `seen` carries styles across lists."""
    seen = set() if seen is None else seen
    unique = []
    for p in products:
        style = (p.get("retailer"), p.get("name", "").strip().lower())
        if style not in seen:
            seen.add(style)
            unique.append(p)
    return unique


def _mix(products: list[dict]) -> list[dict]:
    """Alternate categories within each retailer and retailers overall, so the feed isn't ten pairs of jeans."""
    by_ret: dict[str, list[dict]] = {}
    for p in products:
        by_ret.setdefault(p.get("retailer", ""), []).append(p)
    mixed = [_round_robin(ps, "category") for ps in by_ret.values()]
    return [p for row in zip_longest(*mixed) for p in row if p]


def _interleave(products: list[dict]) -> list[dict]:
    return _mix(_dedupe(products))


def _swiped(user_id: str) -> set[str]:
    return {s["product_id"] for s in store.list("swipes", user_id=user_id)}


# ---------- feed / products ----------

SEED_LEAD = 5        # seeded feed: this many similar cards right after the seed...
SEED_EVERY = 4       # ...then every 4th card is an other-category item that goes with the seed
GOES_WITH_MIN = 0.5  # outfit_rules score for "goes with the seed" (the bar complete_look uses for closet items)


def _size_pick(p: dict, bp: dict) -> Optional[str]:
    """POST /size's pick for a contract-shape product, from an already loaded body_profile (no store reads)."""
    usual = (bp.get("usual_sizes") or {}).get(p.get("category"))
    if not (bp.get("height_cm") and bp.get("weight_kg")):
        return (_usual_size(p, usual) or {}).get("size") if usual else None
    out = recommend_size(p, bp["height_cm"], bp["weight_kg"], fit=bp.get("fit") or "regular",
                         shoe_us=bp.get("shoe_us"), waist_in=bp.get("waist_in"))
    if not out.get("size") and usual:
        out = _usual_size(p, usual) or out
    return out.get("size")


def _size_fields(p: dict, bp: dict) -> dict:
    """your_size: what POST /size would pick (in-stock sizes only). in_your_size: that's also what we'd pick if
    nothing were sold out (false = their size is sold out and your_size is the nearest one left). Both null
    when we know nothing about their size, or can't size this item for them (e.g. shoes without a shoe size)."""
    if not ((bp.get("height_cm") and bp.get("weight_kg")) or bp.get("usual_sizes")):
        return {"your_size": None, "in_your_size": None}
    shaped = as_product(p)
    yours = _size_pick(shaped, bp)
    ideal = _size_pick({**shaped, "sizes": [s["name"] for s in _sizes(p)]}, bp)
    return {"your_size": yours, "in_your_size": None if ideal is None else yours == ideal}


def _card(p: dict, bp: dict, r=None) -> dict:
    return {**p, "reason": r.reason if r else "", "score": r.score if r else 0.0,
            "pairs_with": r.pairs_with if r else [], **_size_fields(p, bp)}


def _style_words(p: dict) -> set[str]:
    return _label_words(f"{p.get('label') or ''} {p.get('name') or ''}")


def _similarity(seed: dict, p: dict) -> float:
    """Rule-based look-alike score: shared colour, style tags, pattern, label words (fit/type: "baggy", "jeans")."""
    color = any(same_color(a, b) for a in seed.get("colors") or [] for b in p.get("colors") or [])
    tags = len(set(seed.get("style_tags") or []) & set(p.get("style_tags") or []))
    pattern = bool(seed.get("pattern")) and seed.get("pattern") == p.get("pattern")
    return 2.0 * color + tags + pattern + len(_style_words(seed) & _style_words(p))


def _weave(similar: list[dict], extra: list[dict]) -> list[dict]:
    """SEED_LEAD similar cards, then an `extra` card as every SEED_EVERY-th; leftovers of either at the end."""
    out, extra = similar[:SEED_LEAD], iter(extra)
    for n, p in enumerate(similar[SEED_LEAD:]):
        if n % (SEED_EVERY - 1) == 0 and (x := next(extra, None)):
            out.append(x)
        out.append(p)
    return out + list(extra)


def _seeded(user_id: str, seed: dict, cands: dict, bp: dict, boosted, limit: int) -> list[dict]:
    """Seed first, then its category by similarity (in your size first), other categories that go with it woven
    in, then the rest as the plain feed tiers it. One pair() call, for reasons only: it never reorders."""
    in_size = {pid: _size_fields(p, bp)["in_your_size"] is True for pid, p in cands.items()}
    styles = {(seed.get("retailer"), seed.get("name", "").strip().lower())}  # drops the seed's colour variants
    same = [p for p in cands.values() if p.get("category") == seed.get("category")]
    same.sort(key=lambda p: (not in_size[p["id"]], -_similarity(seed, p), not boosted(p)))
    anchor = [_as_closet_shape(as_product(seed), "catalog")]
    scored = [(score_product(as_product(p), anchor)["score"], p) for p in cands.values()
              if p.get("category") != seed.get("category")]
    goes = [p for s, p in sorted(scored, key=lambda r: (not in_size[r[1]["id"]], -r[0])) if s >= GOES_WITH_MIN]
    cards = [seed, *_weave(_dedupe(same, styles), _dedupe(goes, styles))]
    used = {p["id"] for p in cards}
    rest = sorted((p for p in cands.values() if p["id"] not in used),
                  key=lambda p: (not in_size[p["id"]], not boosted(p)))
    cards = (cards + _mix(_dedupe(rest, styles)))[:limit]
    reasons = {r.product_id: r for r in pair(user_id, [p["id"] for p in cards], k=min(24, limit * 2))}
    return [_card(p, bp, reasons.get(p["id"])) for p in cards]


@router.get("/feed")
def feed(user_id: str, limit: int = 20, category: Optional[str] = None, retailer: Optional[str] = None,
         seed: Optional[str] = None):
    """In-stock, in-budget, unswiped products ordered by ai.service.pair(), plus reason/score/pairs_with and
    your_size/in_your_size. In-your-size items come first, then preferred stores; nothing is hidden for size.
    `seed` (product id, 404 if unknown): that product first even if swiped, then similar items (see _seeded)."""
    seed_p = _product(seed) if seed else None
    user = store.get("users", user_id) or {}
    bp, ranges = user.get("body_profile") or {}, user.get("price_ranges", {})
    preferred = {str(s).lower() for s in user.get("preferred_stores") or []}
    swiped = _swiped(user_id)
    where = {k: v for k, v in {"category": category, "retailer": retailer}.items() if v}
    cands = {p["id"]: p for p in store.list("products", **where)
             if p["id"] not in swiped and p["id"] != seed and _buyable(p) and _in_budget(p, ranges)}

    def boosted(p: dict) -> bool:
        return str(p.get("retailer", "")).lower() in preferred

    if seed_p:
        return _seeded(user_id, seed_p, cands, bp, boosted, limit)
    if not cands:
        return []

    # size group (in your size first), then preferred stores; pure rules, computed once per candidate
    tier = {pid: (_size_fields(p, bp)["in_your_size"] is not True, not boosted(p)) for pid, p in cands.items()}
    order = sorted(cands, key=tier.get)  # stable; with >50 candidates the AI sees the best tiers
    # Claude sees up to 50 candidates (pair caps it) but writes ~24 reasons (one per ranked item, the slow
    # part); the unranked rest tops up the page so de-duping styles and mixing stores still fills it
    ranked = pair(user_id, order, k=min(24, limit * 2))
    picked = [_card(cands[r.product_id], bp, r) for r in ranked if r.product_id in cands]
    seen = {p["id"] for p in picked}
    rest = [_card(cands[pid], bp) for pid in order if pid not in seen]
    styles: set = set()
    cards: list[dict] = []
    for t in sorted(set(tier.values())):  # in each tier: ranked cards first, then the unranked top-up
        cards += _mix(_dedupe([p for p in picked if tier[p["id"]] == t], styles))
        cards += _mix(_dedupe([p for p in rest if tier[p["id"]] == t], styles))  # never repeats a ranked style
        if len(cards) >= limit:
            break
    return cards[:limit]


def _hits(p: dict, words: list[str]) -> Optional[int]:
    """Total occurrences of the words in name/label/brand/style_tags/colors, or None if any word is missing."""
    hay = " ".join([p.get("name") or "", p.get("label") or "", p.get("brand") or "",
                    *(p.get("style_tags") or []), *(p.get("colors") or [])]).lower()
    counts = [hay.count(w) for w in words]
    return sum(counts) if all(counts) else None


@router.get("/products")
def search_products(q: str = "", category: Optional[str] = None, retailer: Optional[str] = None,
                    in_stock: bool = True, sort: Literal["relevance", "price_asc", "price_desc"] = "relevance",
                    limit: int = 24, offset: int = 0):
    """Catalog search: every word of `q` must match somewhere; `next_offset` is null on the last page."""
    limit, offset = max(1, min(limit, 100)), max(0, offset)
    words = q.lower().split()
    where = {k: v for k, v in {"category": category, "retailer": retailer}.items() if v}
    rows = []
    for p in store.list("products", **where):
        if in_stock and not _buyable(p):
            continue
        if (hits := _hits(p, words)) is not None:
            rows.append((hits, p))
    if sort == "relevance":
        rows.sort(key=lambda r: (-r[0], (r[1].get("name") or "").lower(), r[1]["id"]))
    else:
        rows.sort(key=lambda r: (_price(r[1]), r[1]["id"]), reverse=sort == "price_desc")
    total = len(rows)
    items = [p for _, p in rows[offset:offset + limit]]
    return {"items": items, "total": total, "limit": limit, "offset": offset,
            "next_offset": offset + limit if offset + limit < total else None}


@router.get("/products/{product_id:path}")  # ids are "{retailer}:{code}:{color}"; :path keeps a "/" colour working
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
    store.delete("wishlist", f"{user_id}:{product_id}")
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
        purchase.pop("error", None)  # a retry that succeeds clears the earlier failure
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
    return _receipt(order)


def _receipt(order: dict) -> dict:
    return {"order_id": order["id"], "purchases": order["purchases"], "total_usd": order["total_usd"],
            "created_at": order["created_at"]}


@router.get("/orders/{user_id}")
def orders(user_id: str):
    return sorted(store.list("orders", user_id=user_id), key=lambda o: o["created_at"], reverse=True)


RETRYABLE = ("nessie_failed", "pending_nessie")  # pending_nessie = no Nessie call was ever made (no key)
_retry_lock = threading.Lock()  # two concurrent retries of one order must not both charge it


@router.post("/orders/{order_id}/retry")
def retry_order(order_id: str, user_id: str, retailer: Optional[str] = None):
    """Re-attempt only this order's unpaid store purchases (all of them, or just `retailer`). `paid` purchases
    are never touched, so this is safe to repeat: an all-paid order comes back unchanged with no Nessie call.
    No stock re-check: the order already exists and the amount is the one recorded at checkout.
    404 unknown order/retailer, 403 not the owner, 503 no NESSIE_API_KEY (nothing changes)."""
    with _retry_lock:
        order = store.get("orders", order_id)
        if not order:
            raise HTTPException(404, "unknown order")
        if order.get("user_id") != user_id:
            raise HTTPException(403, "not your order")
        targets = [p for p in order["purchases"] if retailer is None or p["retailer"] == retailer]
        if retailer is not None and not targets:
            raise HTTPException(404, f"no {retailer} purchase in this order")
        todo = [p for p in targets if p.get("status") in RETRYABLE]
        if not todo:
            return _receipt(order)
        if not os.getenv("NESSIE_API_KEY"):
            raise HTTPException(503, "payments are not configured on this server")
        for p in todo:
            p["retried_at"] = _now()
            _pay(user_id, p)
        store.put("orders", order_id, order)
        return _receipt(order)
