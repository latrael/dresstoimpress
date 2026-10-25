"""Discover tab: /search (text), /search/styles (chips + trending), /search/photo (camera) (Nabil).

Results come in two sections (council D10): `similar` (look-alikes of the query or photo) and `goes_with`
(complete the look around the top similar item, the user's closet first; same engine as POST /complete-look).
Catalog items are Product fields as stored (sizes [{name, in_stock}], like /products and /feed) plus
`reason` where the engine gives one. `similar` and trending cards also carry your_size/in_your_size (as on
/feed), and `similar` lists in-your-size items first (otherwise relevance order; nothing hidden).
Nothing here writes to the store except the uploaded photo file.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import get_args

from fastapi import APIRouter, File, Form, UploadFile

from ..ai import service
from ..ai.llm import BadModelOutput
from ..ai.router import _ai_down, _save_upload, complete_look_route
from ..ai.vibe import vibe
from ..models import CompleteLookRequest, StyleTag
from ..store import store
from .router import _buyable, _dedupe, _dept_ok, _hits, _size_fields, _size_first, feed, search_products

log = logging.getLogger(__name__)
router = APIRouter(tags=["search"])

SIMILAR_LIMIT = 24
STYLE_TAGS = set(get_args(StyleTag))


def _shop_for(user_id: str):
    return (store.get("users", user_id) or {}).get("shop_for")


def _body_profile(user_id: str) -> dict:
    return (store.get("users", user_id) or {}).get("body_profile") or {}


def _goes_with(user_id: str, anchor_id: str) -> list[dict]:
    """Complete the look around one product. Closet pieces come back as the closet item (`from_closet: true`),
    catalog pieces as the stored product (`from_closet: false`); both carry the engine's `reason`.
    [] on any failure: search results never fail because pairing did."""
    try:
        look = complete_look_route(CompleteLookRequest(user_id=user_id, product_id=anchor_id))
    except Exception as e:  # noqa: BLE001
        log.warning("complete-look failed for %s: %s", anchor_id, e)
        return []
    out, shop_for = [], _shop_for(user_id)
    for it in look.get("items") or []:
        if it.get("source") == "closet":
            c = store.get("closet_items", it["id"])
            if c and c.get("user_id") == user_id:
                out.append({**c, "from_closet": True, "reason": it.get("reason", "")})
        elif (p := store.get("products", it["id"])) and _buyable(p) and _dept_ok(p, shop_for):
            out.append({**p, "from_closet": False, "reason": it.get("reason", "")})
    return out


# ---------- text search ----------

@router.get("/search")
def search(user_id: str, q: str = ""):
    """Keyword search (same matching as /products, in stock, one card per style; the top results by relevance,
    in your size first) + complete the look around the #1 card. A sentence (3+ words) or a query with no
    keyword hits goes through Adam's vibe() instead; `vibe` echoes the filters it used (null otherwise).
    A blank query returns empty sections (the app shows chips + trending instead)."""
    if not q.strip():
        return {"query": q, "similar": [], "goes_with": [], "vibe": None}
    shop_for = _shop_for(user_id)
    hits = search_products(q=q, limit=100, department=shop_for)["items"]
    filters = None
    if len(q.split()) >= 3 or not hits:  # a sentence ("fit for a rooftop party") or no direct hits: ask vibe()
        filters = vibe(q)
        seen = {h["id"] for h in hits}  # exact keyword matches stay first ("black cargo pants")
        hits += [p for p in _vibe_hits(filters, shop_for) if p["id"] not in seen]
    top = _dedupe(hits)[:SIMILAR_LIMIT]
    similar = _size_first(top, _body_profile(user_id))  # same 24 results, in your size first
    return {"query": q, "similar": similar, "vibe": filters,
            "goes_with": _goes_with(user_id, similar[0]["id"]) if similar else []}


def _vibe_hits(f: dict, shop_for) -> list[dict]:
    """In-stock products scored against vibe() filters: style 3, category 2, keyword phrase 2, colour 1 each.
    Best first (ties by name); nothing that scores 0."""
    styles, cats = set(f.get("styles") or []), set(f.get("categories") or [])
    colors = [c.lower() for c in f.get("colors") or []]
    keywords = [k.lower().split() for k in f.get("keywords") or [] if k.strip()]
    scored = []
    for p in store.list("products"):
        if not _buyable(p) or not _dept_ok(p, shop_for):
            continue
        score = (3 * len(styles & set(p.get("style_tags") or [])) + 2 * (p.get("category") in cats)
                 + 2 * sum(_hits(p, kw) is not None for kw in keywords)
                 + sum(any(c in col.lower() for col in p.get("colors") or []) for c in colors))
        if score:
            scored.append((-score, p.get("name") or "", p))
    return [p for *_, p in sorted(scored, key=lambda t: t[:2])]


# ---------- before a search: style chips + trending ----------

def _trend_counts() -> Counter:
    """Per product: users who saved it + users with it in their cart + users who ordered it (each signal
    counts a user once, so one user who saved and carted an item adds 2)."""
    signals: dict[str, dict[str, set]] = {s: defaultdict(set) for s in ("saved", "carted", "ordered")}
    for w in store.list("wishlist"):
        signals["saved"][w["product_id"]].add(w["user_id"])
    for s in store.list("swipes", action="wishlist"):  # legacy saves (see router._saved)
        if not s.get("unsaved"):
            signals["saved"][s["product_id"]].add(s["user_id"])
    for cart in store.list("carts"):
        for i in cart.get("items") or []:
            signals["carted"][i["product_id"]].add(cart.get("user_id"))
    for order in store.list("orders"):
        for purchase in order.get("purchases") or []:
            for i in purchase.get("items") or []:
                signals["ordered"][i["product_id"]].add(order.get("user_id"))
    counts: Counter = Counter()
    for by_product in signals.values():
        for pid, users in by_product.items():
            counts[pid] += len(users)
    return counts


@router.get("/search/styles")
def styles(user_id: str, limit: int = 8):
    """Style chips (catalog style tags with in-stock counts, most common first) + trending products
    (most saved/carted/ordered across users, `trend_count`), topped up from this user's /feed (`trend_count` 0).
    Both only count/show the user's shop_for department (+ unisex/unknown)."""
    limit = max(1, min(limit, 50))
    shop_for = _shop_for(user_id)
    buyable = [p for p in store.list("products") if _buyable(p) and _dept_ok(p, shop_for)]
    tags = Counter(t for p in buyable for t in set(p.get("style_tags") or []) if t in STYLE_TAGS)
    chips = [{"tag": t, "count": n} for t, n in sorted(tags.items(), key=lambda r: (-r[1], r[0]))]

    counts = _trend_counts()
    hot = sorted((p for p in buyable if counts[p["id"]]),
                 key=lambda p: (-counts[p["id"]], (p.get("name") or "").lower(), p["id"]))
    seen: set = set()  # styles, shared with the top-up so it never repeats a trending item
    bp = _body_profile(user_id)  # trending cards carry your_size/in_your_size like the feed top-ups below
    trending = [{**p, "trend_count": counts[p["id"]], **_size_fields(p, bp)} for p in _dedupe(hot, seen)[:limit]]
    if len(trending) < limit:
        try:
            cards = feed(user_id=user_id, limit=limit * 2)
        except Exception as e:  # noqa: BLE001
            log.warning("trending top-up from /feed failed: %s", e)
            cards = []
        have = {p["id"] for p in trending}
        trending += [{**p, "trend_count": 0} for p in _dedupe([c for c in cards if c["id"] not in have], seen)]
    return {"styles": chips, "trending": trending[:limit]}


# ---------- photo search ----------

@router.post("/search/photo")
async def search_photo(user_id: str = Form(...), file: UploadFile = File(...)):
    """Camera search: save the photo (EXIF/GPS stripped), tag each piece, find catalog matches ranked
    against the user's closet, complete the look around the top match. Creates no post and no closet item."""
    photo_url = await _save_upload(file)
    shop_for = _shop_for(user_id)
    try:
        tags = service.tag_fit(photo_url)
        # filter the catalog before matching, so the top matches per piece are ones the user can buy
        matches = service.shop_fit(user_id, tags, keep=lambda p: _buyable(p) and _dept_ok(p, shop_for)) if tags else []
    except BadModelOutput as e:
        raise _ai_down("photo search", e)
    similar = []
    for m in matches:  # shop_fit returns the AI's product view; send the stored card like /search does
        p = store.get("products", m["id"])
        if p and _buyable(p) and _dept_ok(p, shop_for):
            similar.append({**p, "reason": m.get("reason", ""), "pairs_with": m.get("pairs_with", []),
                            "score": m.get("score", 0.0), "matched_tag": m.get("matched_tag", "")})
    similar = _size_first(similar, _body_profile(user_id))
    return {"photo_url": photo_url, "tags": tags, "similar": similar,
            "goes_with": _goes_with(user_id, similar[0]["id"]) if similar else []}

