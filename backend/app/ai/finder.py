"""Find a buyable product for an item seen in a Fit Check post.

1. Strict match against the products we already have (category must match, the item's
   type word -- "hoodie", "jeans" -- must appear in the product name, color helps).
2. If nothing passes, search the retailers live through Apify (store search pages fed to
   the same fashion scraper Nabil uses), normalize, save to `products`, and match again.

Live search runs only with APIFY_TOKEN set and is capped per item (cost: a few results).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from urllib.parse import quote_plus

import httpx

from .compat import get_product, list_products
from ..store import store

log = logging.getLogger(__name__)

APIFY_ACTOR = os.getenv("APIFY_SEARCH_ACTOR", "jordan-byte~fashion-multi-scraper-us")
LIVE_SITES = [s for s in os.getenv("LIVE_SEARCH_SITES", "asos,hm,zara").split(",") if s]
LIVE_PER_SITE = int(os.getenv("LIVE_SEARCH_PER_SITE", "4"))
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
    color = _words(tag.get("color") or "")
    if color & have:
        score += 1.0
    elif color & NEUTRALS and have & NEUTRALS:
        score += 0.3
    if tag.get("retailer") and tag["retailer"] == product.get("retailer"):
        score += 1.0
    return score


def best_matches(tag: dict, products: list[dict], n: int = 3) -> list[dict]:
    scored = [(match_score(tag, p), p) for p in products]
    scored = [(s, p) for s, p in scored if s >= MIN_SCORE]
    scored.sort(key=lambda t: (t[0], -t[1].get("price_usd", 0)), reverse=True)
    return [p for _, p in scored[:n]]


# ---------- live search via Apify ----------

def search_urls(query: str) -> dict[str, str]:
    q = quote_plus(query)
    return {
        "asosCategoryUrl": f"https://www.asos.com/us/search/?q={q}",
        "hmCategoryUrl": f"https://www2.hm.com/en_us/search-results.html?q={q}",
        "zaraCategoryUrl": query,  # Zara field accepts a plain name
        "uniqloCategoryUrl": f"https://www.uniqlo.com/us/en/search?q={q}",
        "mangoCategoryUrl": f"https://shop.mango.com/us/en/search?q={q}",
    }


def _normalize(raw: dict, tag: dict) -> dict | None:
    site = (raw.get("site") or raw.get("retailer") or "").lower()
    price = raw.get("price") or raw.get("price_usd")
    if isinstance(price, dict):
        price = price.get("current")
    img = raw.get("image") or raw.get("imageUrl") or raw.get("image_url") or (raw.get("images") or [None])[0]
    url = raw.get("url") or raw.get("productUrl") or raw.get("product_url")
    name = raw.get("name") or raw.get("title")
    try:
        price = float(str(price).replace("$", "").replace(",", "")) if price is not None else None
    except ValueError:
        price = None
    if site not in {"zara", "hm", "asos", "uniqlo", "mango"} or not (name and price and img and url):
        return None
    sale = raw.get("salePrice") or raw.get("sale_price")
    try:
        sale = float(str(sale).replace("$", "")) if sale else None
    except ValueError:
        sale = None
    pid = f"{site}-" + hashlib.sha256(str(url).encode()).hexdigest()[:12]
    colors = raw.get("colors") or ([raw["color"]] if raw.get("color") else [])
    sizes = [s if isinstance(s, dict) else {"name": str(s), "in_stock": True} for s in (raw.get("sizes") or [])]
    return {
        "id": pid, "retailer": site, "name": str(name), "brand": raw.get("brand") or {
            "hm": "H&M", "zara": "Zara", "asos": "ASOS", "uniqlo": "Uniqlo", "mango": "Mango"}[site],
        "category": tag.get("category") or "top", "price_usd": price, "sale_price_usd": sale,
        "colors": [str(c) for c in colors][:5], "sizes": sizes[:12], "currency": "USD",
        "in_stock": True, "image_url": str(img), "product_url": str(url),
        "style_tags": list(tag.get("style_tags", []))[:3], "source": "live_search",
    }


def live_search(tag: dict) -> list[dict]:
    """Search stores for one item; saves and returns normalized Products. [] on any failure."""
    token = os.getenv("APIFY_TOKEN")
    if not token or not tag.get("label"):
        return []
    query = f"{tag.get('color') or ''} {tag['label']}".strip()
    key = "q-" + re.sub(r"[^a-z0-9]+", "-", query.lower())[:80]
    cached = store.get("live_search_cache", key)
    if cached is not None:
        return [p for pid in cached["ids"] if (p := get_product(pid))]
    sites = [tag["retailer"]] if tag.get("retailer") in LIVE_SITES else LIVE_SITES
    urls = search_urls(query)
    body = {"sites": sites, "maxItemsPerSite": LIVE_PER_SITE,
            **{k: v for k, v in urls.items() if k.split("CategoryUrl")[0] in sites}}
    try:
        r = httpx.post(f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items",
                       params={"token": token}, json=body, timeout=120)
        r.raise_for_status()
        items = r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("live search failed for %r: %s", query, e)
        return []
    found = [p for raw in items if isinstance(raw, dict) and (p := _normalize(raw, tag))]
    for p in found:
        store.put("products", p["id"], p)
    store.put("live_search_cache", key, {"ids": [p["id"] for p in found]})
    return found


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
