"""Find similar look (Adam, Oct 25): for each piece tagged in an Inspo post, the viewer's own similar closet
pieces first ("you already own"), then catalog products to buy (service.shop_fit_grouped).

Closet similarity is rules only (free, instant, deterministic): same category, then garment type, colour
and style overlap; ties by id.
"""
from __future__ import annotations

from ..store import store
from .colors import same_color
from .finder import item_type

CLOSET_PER_TAG = 4


def _score(tag: dict, item: dict) -> float:
    cat = tag.get("category")
    if cat and item.get("category") and cat != item["category"]:
        return 0.0
    want = item_type(tag.get("label") or "")
    have = item_type(item.get("label") or "")
    score = 0.0
    if want is not None and have is not None:
        if want != have:
            return 0.0
        score += 3
    elif cat and item.get("category") == cat:
        score += 1
    if tag.get("color") and same_color(tag.get("color"), item.get("color")):
        score += 2
    styles = set(tag.get("style_tags") or []) & set(item.get("style_tags") or [])
    score += min(len(styles), 2) * 0.5
    if (tag.get("pattern") or "solid") == (item.get("pattern") or "solid"):
        score += 0.25
    return score


def closet_similar(user_id: str, tag: dict, k: int = CLOSET_PER_TAG) -> list[dict]:
    """The viewer's closet pieces most like one tagged piece (full closet item docs), best first.
    A piece qualifies with a garment-type match, or the same category and colour."""
    rows = []
    for item in store.list("closet_items", user_id=user_id):
        s = _score(tag, item)
        if s >= 3:
            rows.append((s, str(item.get("id") or ""), item))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return [r[2] for r in rows[:k]]


def similar_look(viewer_id: str, tagged: list[dict], keep=None) -> list[dict]:
    """[{tag, closet: [closet item], products: [card]}] per tagged piece, in post order."""
    from . import service

    groups = service.shop_fit_grouped(viewer_id, tagged, keep=keep)
    out = []
    for t, g in zip(tagged, groups):
        out.append({"tag": g["tag"], "closet": closet_similar(viewer_id, t), "products": g["products"]})
    return out
