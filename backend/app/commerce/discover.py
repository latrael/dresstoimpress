"""Discover as a Pinterest-style board (Nabil, Oct 25): a two-column feed mixing Pinterest outfit pins (the look),
catalog products (things to buy, in your size first) and Inspo posts (real outfits from users).

Pins come from silentflow/pinterest-scraper-ppr keyword searches ("<style> outfit women|men"), one per style chip, saved
to seed/raw/pinterest_*.json.gz and normalized + AI-tagged by scripts.ingest_pins into seed/pins.json (collection
`pins`). Each pin's `tagged` pieces (service.tag_fit, the Inspo tagger) power its "Similar" button, the same
similar-look groups as an Inspo post: things to buy per piece + the viewer's own similar closet pieces.

    GET /discover/board?user_id=&style=&limit=20&offset=0
      -> {"style", "styles", "items": [{"kind": "pin"|"product"|"post", ...}], "next_offset"}
    GET /discover/pins/{pin_id}/similar?user_id=  -> [{tag, closet, products}] (like /fitcheck/{id}/similar)
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional, get_args

from fastapi import APIRouter, HTTPException

from ..models import StyleTag
from ..store import store
from .router import _buyable, _dept_ok, _size_first

router = APIRouter(tags=["discover"])
STYLE_TAGS = list(get_args(StyleTag))  # the 10 style chips, in vocabulary order
COL = "pins"
PATTERN = ("pin", "pin", "product", "pin", "post", "pin", "product")  # ~4 pins : 2 products : 1 post, repeating
_AD = re.compile(r"(^|\s)#ad\b|sponsored|promoted|affiliate|#commission", re.I)
_HASHTAGS = re.compile(r"#\S+")


# ---------- pins: raw actor item -> stored pin ----------

def normalize_pin(raw: dict, style: str, department: str) -> Optional[dict]:
    """One Pinterest search result -> a pin, or None for ads, videos and pins without a usable image. Reads both
    silentflow/pinterest-scraper-ppr items (imageUrls{736x}, width/height) and epctex items (images{736x:{url,...}})."""
    if raw.get("demo") or raw.get("type") not in (None, "pin"):
        return None  # "demo": a placeholder an actor returns when the plan's quota is used up
    if str(raw.get("isVideo") or raw.get("is_video") or "").lower() == "true" or raw.get("videos"):
        return None
    text = " ".join(str(raw.get(k) or "") for k in ("gridTitle", "grid_title", "title", "description"))
    if _AD.search(text):
        return None
    img = (raw.get("images") or {}).get("736x") or {}
    url = img.get("url") or (raw.get("imageUrls") or {}).get("736x") or raw.get("imageUrl")
    w, h = img.get("width") or raw.get("width"), img.get("height") or raw.get("height")  # same aspect at any size
    if not url or not w or not h or not raw.get("id"):
        return None
    title = (raw.get("gridTitle") or raw.get("grid_title") or raw.get("title")
             or _HASHTAGS.sub("", raw.get("description") or "")).strip()
    return {
        "id": f"pin:{raw['id']}", "source": "pinterest", "style": style, "department": department,
        "image_url": url, "w": int(w), "h": int(h),
        "title": " ".join(title.split())[:90], "pin_url": raw.get("url") or "",
        "dominant_color": raw.get("dominantColor") or raw.get("dominant_color") or None, "tagged": [],
    }


# ---------- the board ----------

def _user_styles(user: dict) -> list[str]:
    """The viewer's styles: tags from their onboarding photos + style words they typed; empty = all styles."""
    words = set(re.findall(r"[a-z0-9]+", (user.get("style_text") or "").lower()))
    mine = [t for t in user.get("style_tags") or [] if t in STYLE_TAGS]
    mine += [t for t in STYLE_TAGS if t in words and t not in mine]
    return mine


def _order(items: list[dict], seed: str) -> list[dict]:
    """Stable per-viewer shuffle, so paging with offset never repeats or skips (same input, same order)."""
    return sorted(items, key=lambda d: hashlib.sha256(f"{seed}|{d['id']}".encode()).hexdigest())


def _dept_pin(p: dict, shop_for: Optional[str]) -> bool:
    return shop_for not in ("men", "women") or p.get("department") == shop_for


def _board_sources(user_id: str, styles: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    from .fitcheck import _view

    user = store.get("users", user_id) or {}
    shop_for = user.get("shop_for")
    want = set(styles) or set(STYLE_TAGS)
    seed = f"{user_id}|{','.join(sorted(want))}"
    pins = _order([p for p in store.list(COL) if p.get("style") in want and _dept_pin(p, shop_for)
                   and p.get("tagged")], seed)
    products = [p for p in store.list("products")
                if _buyable(p) and _dept_ok(p, shop_for) and want & set(p.get("style_tags") or [])]
    products = _size_first(_order(products, seed), user.get("body_profile") or {})
    circle = {user_id, *(user.get("friends") or [])}  # same rule as /fitcheck/feed: friends-only posts stay in circle
    posts = sorted((p for p in store.list("fitcheck_posts")
                    if p.get("visibility", "public") != "friends" or p.get("user_id") in circle),
                   key=lambda p: p.get("created_at") or "", reverse=True)
    styled = [p for p in posts if want & {s for t in p.get("tagged") or [] for s in t.get("style_tags") or []}]
    return pins, products, [_view(p, user_id) for p in (styled or posts)]


def _weave(pins: list[dict], products: list[dict], posts: list[dict]) -> list[dict]:
    """PATTERN repeated; a kind that runs out is skipped, so the board never has holes."""
    queues = {"pin": iter(pins), "product": iter(products), "post": iter(posts)}
    out, live = [], set(queues)
    while live:
        for kind in PATTERN:
            if kind not in live:
                continue
            item = next(queues[kind], None)
            if item is None:
                live.discard(kind)
                continue
            out.append({"kind": kind, kind: item})
    return out


@router.get("/discover/board")
def board(user_id: str, style: Optional[str] = None, limit: int = 20, offset: int = 0):
    """The Discover board, two columns in the app. `style` = a tapped style chip; none = the viewer's own styles
    (all styles if they have none). Pins, products and posts are woven ~4:2:1; paging is stable per viewer."""
    if style is not None and style not in STYLE_TAGS:
        raise HTTPException(422, f"style must be one of {sorted(STYLE_TAGS)}")
    user = store.get("users", user_id) or {}
    styles = [style] if style else _user_styles(user)
    limit, offset = max(1, min(limit, 60)), max(0, offset)
    items = _weave(*_board_sources(user_id, styles))
    page = items[offset:offset + limit]
    return {"style": style, "styles": styles, "items": page,
            "next_offset": offset + limit if offset + limit < len(items) else None}


@router.get("/discover/pins/{pin_id}/similar")
def pin_similar(pin_id: str, user_id: str):
    """"Similar" on a pin: per tagged piece, things to buy (viewer's department) + their own similar closet pieces."""
    from ..ai.similar_look import similar_look

    pin = store.get(COL, pin_id)
    if not pin:
        raise HTTPException(404, "unknown pin")
    shop_for = (store.get("users", user_id) or {}).get("shop_for")
    return similar_look(user_id, pin.get("tagged") or [], keep=lambda p: _dept_ok(p, shop_for))
