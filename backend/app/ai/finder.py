"""Find a buyable product for an item seen in a Fit Check post.

1. Strict match against the products we already have (category must match, the item's
   type word -- "hoodie", "jeans" -- must appear in the product name, color helps).
2. If nothing passes, search H&M live through Apify (Nabil's H&M actor and normalizer from
   app.commerce.ingest, so live results have the same ids and shape as the catalog), save new
   ones to `products`, and match again.

Live search runs only with APIFY_TOKEN set, is capped per item (LIVE_SEARCH_MAX, ~5 s, a few
cents) and cached per query.
"""
from __future__ import annotations

import logging
import os
import re

from .colors import is_neutral, same_color
from .compat import get_product, list_products
from ..store import store

log = logging.getLogger(__name__)

LIVE_SEARCH_MAX = int(os.getenv("LIVE_SEARCH_MAX", "6"))  # H&M results per Fit Check item
MIN_SCORE = 2.5  # type match (2.0) plus at least one more signal: descriptor, color or retailer

# Type words: an item only matches products of the same kind.
TYPE_GROUPS = [
    {"tee", "t-shirt", "tshirt", "tank", "top", "cami", "shirt", "blouse", "polo"},
    {"hoodie", "sweatshirt", "pullover", "crewneck"},
    {"sweater", "cardigan", "knit", "jumper"},
    {"jeans", "denim"},
    {"pants", "trousers", "cargos", "cargo", "chinos", "slacks"},
    {"sweatpants", "joggers", "jogger", "trackpants"},
    {"shorts"},
    {"skirt", "miniskirt"},
    {"dress"},
    {"jacket", "bomber", "puffer", "windbreaker", "blazer"},
    {"coat", "trench", "overcoat"},
    {"sneakers", "trainers", "sneaker"},
    {"boots", "boot"},
    {"heels", "pumps", "sandals", "loafers", "flats", "shoes"},
    {"bag", "tote", "purse", "handbag", "backpack"},
    {"cap", "hat", "beanie", "bucket"},
    {"sunglasses", "glasses"},
    {"belt"},
    {"earrings", "necklace", "bracelet", "ring", "jewelry"},
]
_WORD = re.compile(r"[a-z0-9-]+")
NEUTRALS = {"black", "white", "grey", "gray", "beige", "cream", "navy", "denim", "ecru", "khaki"}


def _words(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


def item_type(label: str) -> int | None:
    """Type group of an item label, preferring its last word ("cropped pullover hoodie" -> hoodie)."""
    ws = _WORD.findall(label.lower())
    for w in reversed(ws):
        for i, g in enumerate(TYPE_GROUPS):
            if w in g:
                return i
    return None


def match_score(tag: dict, product: dict) -> float:
    """0 = no match. Category must match (if known) and the type word must agree."""
    cat = tag.get("category")
    if cat and product.get("category") and cat != product["category"]:
        return 0.0
    want_type = item_type(tag.get("label") or "")
    have = _words(" ".join([product.get("name", ""), *product.get("colors", [])]))
    if want_type is not None and not (have & TYPE_GROUPS[want_type]):
        return 0.0
    score = 2.0 if want_type is not None else 0.0
    # descriptors = label words other than the item's own type ("denim" in "denim jacket" counts)
    want_words = _words(tag.get("label") or "") - (TYPE_GROUPS[want_type] if want_type is not None else set())
    score += 0.5 * len(want_words & have)
    color_text = tag.get("color") or ""
    color = _words(color_text)
    prod_colors = product.get("colors") or []
    # normalized too, so "ivory" matches "off white" and "navy blue" matches "dark navy"
    if color & have or any(same_color(color_text, c) for c in prod_colors):
        score += 1.0
    elif (color & NEUTRALS and have & NEUTRALS) or (
            is_neutral(color_text) and any(is_neutral(c) for c in prod_colors)):
        score += 0.3
    if tag.get("retailer") and tag["retailer"] == product.get("retailer"):
        score += 1.0
    return score


def best_matches(tag: dict, products: list[dict], n: int = 3) -> list[dict]:
    scored = [(match_score(tag, p), p) for p in products]
    scored = [(s, p) for s, p in scored if s >= MIN_SCORE]
    scored.sort(key=lambda t: (t[0], -t[1].get("price_usd", 0)), reverse=True)
    return [p for _, p in scored[:n]]


# ---------- live search via Apify (H&M) ----------

def _query(tag: dict) -> str:
    """Search text: color + label, without repeating the color ("black hoodie", not "black black hoodie")."""
    label = " ".join(str(tag.get("label") or "").split())
    color = " ".join(str(tag.get("color") or "").split())
    if color and color.lower() not in label.lower():
        label = f"{color} {label}"
    return label.strip()


def live_search(tag: dict) -> list[dict]:
    """Search H&M for one item; saves new products and returns them. [] on any failure."""
    token = os.getenv("APIFY_TOKEN")
    if not token or not tag.get("label"):
        return []
    query = _query(tag)
    key = "hm-" + re.sub(r"[^a-z0-9]+", "-", query.lower())[:80]
    cached = store.get("live_search_cache", key)
    if cached is not None:
        return [p for pid in cached["ids"] if (p := get_product(pid))]
    from ..commerce.ingest import fetch_hm, normalize_hm  # Nabil's actor + normalizer

    try:
        found = normalize_hm(fetch_hm([query], LIVE_SEARCH_MAX, token))
    except Exception as e:  # noqa: BLE001  (log no message: the request URL carries the token)
        status = getattr(getattr(e, "response", None), "status_code", "")
        log.warning("live search failed for %r: %s %s", query, type(e).__name__, status)
        return []
    out = []
    for p in found:
        existing = store.get("products", p["id"])
        if existing:  # already in the catalog, maybe tagged: keep that copy
            out.append(existing)
            continue
        p["source"] = "live_search"
        store.put("products", p["id"], p)
        out.append(p)
    store.put("live_search_cache", key, {"ids": [p["id"] for p in out]})
    return out


def find_products(tag: dict, products: list[dict], n: int = 3) -> list[dict]:
    """Best buyable matches for one Fit Check item: catalog first, then live search."""
    if tag.get("product_id"):
        p = get_product(tag["product_id"])
        if p:
            return [p]
    hits = best_matches(tag, products, n)
    if hits:
        return hits
    return best_matches(tag, live_search(tag), n)
