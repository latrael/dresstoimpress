"""Sprint 4 §10: what the reels Home needs per feed card.

- closet_picks(user_id, product, k=4): the user's own closet pieces that go with a product, one per slot,
  rule-based (Fit Score v2 rubric + the complete-the-look clash guard), so it's free and instant.
- tryon_status(user_id, product, picks=None): the slide-2 state read from the try-on cache.
- prefetch_tryons(user_id, items): start rendering try-ons in the background (2 workers, de-duplicated,
  capped per user per day). Reuses service.try_on, so a prefetched result is exactly what slide 2 shows.

Accessories are shown in the 2x2 grid but never go into the render (the in-place edit is for garments).
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

log = logging.getLogger(__name__)

PREFETCH_PER_USER_DAY = int(os.getenv("PREFETCH_PER_USER_DAY", "20"))
WEARABLE = {"top", "bottom", "outerwear", "shoes", "dress"}

# slot order per anchor category (§10.1); "bag" = an accessory whose label says bag
SLOT_ORDER: dict[str, list[str]] = {
    "bottom": ["top", "shoes", "outerwear", "accessory"],
    "top": ["bottom", "shoes", "outerwear", "accessory"],
    "shoes": ["top", "bottom", "outerwear", "accessory"],
    "dress": ["shoes", "outerwear", "bag", "accessory"],
    "outerwear": ["top", "bottom", "shoes", "accessory"],
    "accessory": ["top", "bottom", "shoes", "outerwear"],
}
_BAG_WORDS = ("bag", "tote", "purse", "clutch", "backpack", "crossbody")

_lock = threading.Lock()
_inflight: set[str] = set()
_futures: list[Future] = []
_pool: ThreadPoolExecutor | None = None


def _svc():
    from . import service

    return service


def _is_bag(item: dict) -> bool:
    text = f"{item.get('label') or ''} {item.get('name') or ''}".lower()
    return any(w in text for w in _BAG_WORDS)


def _slot_of(item: dict) -> str:
    cat = str(item.get("category") or "").lower()
    if cat == "accessory" and _is_bag(item):
        return "bag"
    return cat


def _as_product(product: Any) -> dict | None:
    if isinstance(product, dict):
        return product
    if hasattr(product, "model_dump"):
        return product.model_dump()
    if isinstance(product, str):
        return _svc().get_product(product)
    return None


def closet_picks(user_id: str, product: Any, k: int = 4) -> list[dict]:
    """[{id, label, category, image_url}] (0..k), one per slot in the §10.1 order for the product's category.
    [] for an empty closet or an unknown product. Deterministic: best rubric fit, ties by id."""
    from .complete_look import _as_closet_shape, _rubric_fit, anchor_primary_style, clashes_with

    p = _as_product(product)
    if not p:
        return []
    closet = [c for c in _svc().store.list("closet_items", user_id=user_id) if c.get("category")]
    if not closet:
        return []
    anchor = _as_closet_shape(p, "catalog")
    primary = anchor_primary_style(anchor)
    order = SLOT_ORDER.get(str(p.get("category") or "").lower(), ["top", "bottom", "shoes", "outerwear", "accessory"])
    best: dict[str, tuple[float, str, dict]] = {}
    for c in closet:
        slot = _slot_of(c)
        if slot not in order:
            # a bag can fill the plain accessory square when there's no bag slot, and vice versa
            slot = "accessory" if slot == "bag" and "accessory" in order else slot
            if slot not in order:
                continue
        rep = _as_closet_shape(c, "closet")
        if clashes_with(anchor, rep):
            continue
        fit = _rubric_fit(rep, [anchor], primary)
        cur = best.get(slot)
        cid = str(c.get("id") or "")
        if cur is None or (fit, -_rank(cid)) > (cur[0], -_rank(cur[1])):
            best[slot] = (fit, cid, c)
    out = []
    for slot in order:
        if slot in best and len(out) < k:
            c = best[slot][2]
            out.append({"id": c.get("id"), "label": c.get("label") or c.get("name") or c.get("category"),
                        "category": c.get("category"),
                        "image_url": c.get("display_image_url") or c.get("image_url")})
    return out


def _rank(cid: str) -> int:
    # stable tie-break: lower id wins (used as a negative key above)
    return int.from_bytes(cid.encode()[:8].ljust(8, b"\0"), "big")


def _wearable_ids(picks: list[dict]) -> list[str]:
    return [str(x["id"]) for x in picks if x.get("id") and str(x.get("category") or "") in WEARABLE]


def _render_args(user_id: str, p: dict, picks: list[dict] | None) -> tuple[list[str], list[str], str | None]:
    """(product_ids, closet_ids, source photo url) exactly as service.try_on will compute its cache key."""
    from .tryon_source import pick_source_photo

    # Product ONLY: slide 2 is the user's real outfit photo with this one garment swapped in (v5/v7 in-place
    # edit). Closet picks belong on slide 3; sending them here made Gemini restyle the whole outfit.
    s = _svc()
    src = pick_source_photo(user_id, [p], s.store.get("users", user_id) or {})
    return [str(p["id"])], [], (src["url"] if src else None)


def _ai_available() -> bool:
    from .llm import BudgetExceeded, check_budget, mock_mode

    if mock_mode("GEMINI_API_KEY"):
        return False
    try:
        check_budget("gemini")
    except BudgetExceeded:
        return False
    return True


def _day_key(user_id: str) -> str:
    return f"{user_id}:{_dt.date.today().isoformat()}"


def prefetch_used(user_id: str) -> int:
    return int((_svc().store.get("prefetch_usage", _day_key(user_id)) or {}).get("n", 0))


def _over_cap(user_id: str) -> bool:
    return bool(PREFETCH_PER_USER_DAY) and prefetch_used(user_id) >= PREFETCH_PER_USER_DAY


def tryon_status(user_id: str, product: Any, picks: list[dict] | None = None) -> dict:
    """§10.1 `tryon`: {status, image_url?, mode?}. status: ready | pending | none | needs_photo | unavailable."""
    s = _svc()
    p = _as_product(product)
    if not p:
        return {"status": "none"}
    pids, cids, body = _render_args(user_id, p, picks)
    if not body:
        return {"status": "needs_photo"}
    key = s._tryon_key(user_id, pids, cids, body)
    hit = s.store.get("tryon_cache", key)
    if hit and hit.get("mode", "ai") == "ai":
        return {"status": "ready", "image_url": hit["image_url"], "mode": "ai"}
    with _lock:
        if key in _inflight:
            return {"status": "pending"}
    if not _ai_available() or _over_cap(user_id):
        return {"status": "unavailable"}
    return {"status": "none"}


def _get_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tryon-prefetch")
    return _pool


def _run(key: str, user_id: str, pids: list[str], cids: list[str]) -> None:
    try:
        _svc().try_on(user_id, pids, cids)
    except Exception:  # a failed prefetch just leaves the post at "none" -> the app can retry
        log.exception("prefetch try-on failed")
    finally:
        with _lock:
            _inflight.discard(key)


def prefetch_tryons(user_id: str, items: list[Any]) -> dict[str, dict]:
    """Start background renders for up to 5 items (products, dicts or ids) that aren't cached or in flight.
    Returns {product_id: tryon} right away. Each new AI render counts toward PREFETCH_PER_USER_DAY; past the
    cap (or with the AI off / over budget) nothing is rendered: the card stays "unavailable" with no image and
    the app can retry later."""
    s = _svc()
    out: dict[str, dict] = {}
    for item in list(items)[:5]:
        p = _as_product(item)
        if not p or not p.get("id"):
            continue
        pid = str(p["id"])
        picks = closet_picks(user_id, p)
        st = tryon_status(user_id, p, picks)
        if st["status"] != "none":
            out[pid] = st
            continue
        pids, cids, body = _render_args(user_id, p, picks)
        key = s._tryon_key(user_id, pids, cids, body or "")
        with _lock:
            if key in _inflight:
                out[pid] = {"status": "pending"}
                continue
            _inflight.add(key)
        doc = s.store.get("prefetch_usage", _day_key(user_id)) or {"n": 0}
        s.store.put("prefetch_usage", _day_key(user_id), {"n": int(doc.get("n", 0)) + 1, "at": time.time()})
        _futures.append(_get_pool().submit(_run, key, user_id, pids, cids))
        out[pid] = {"status": "pending"}
    return out



def wait_prefetch(timeout: float = 10.0) -> None:
    """Block until queued prefetches finish (tests, scripts)."""
    for f in list(_futures):
        f.result(timeout=timeout)
    _futures.clear()
