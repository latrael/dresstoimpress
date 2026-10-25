"""Shopify stores (autofacts/shopify actor) -> Products. Pure, like the other normalizers in ingest.py.

    python -m scripts.ingest --from-file "seed/raw/shopify_*.json.gz" --retailer shopify

One raw item per Shopify product; we emit one Product per colour (in-stock colours first, capped like
Uniqlo). The store is read from the product's canonical URL, so one raw file can mix stores. Prices
come back in cents. `department` is fixed per store, except Kith, which sells both (its women's line
says so in the title, tags or collection).
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

from .ingest import HM_STEMS, MAX_COLORS, _now, _valid, gallery, guess_category, plain_text, slug

SHOPIFY_ACTOR = "autofacts/shopify"

# host -> (retailer id, display name, department; None = per product)
STORES = {
    "us.princesspolly.com": ("princesspolly", "Princess Polly", "women"),
    "edikted.com": ("edikted", "Edikted", "women"),
    "us.brandymelville.com": ("brandymelville", "Brandy Melville", "women"),
    "trueclassictees.com": ("trueclassic", "True Classic", "men"),
    "kith.com": ("kith", "Kith", None),
    "www.stussy.com": ("stussy", "Stüssy", "unisex"),
    "stussy.com": ("stussy", "Stüssy", "unisex"),
}
NOT_APPAREL = re.compile(r"gift ?card|e-?gift|beauty|fragrance|perfume|candle|skincare|makeup|lip ?gloss|"
                         r"phone case|sticker|poster|home goods|homeware|mug|towel|insurance|shipping", re.I)
IN_STOCK = {"instock", "limitedavailability", "preorder", "backorder"}
_US = re.compile(r"^US\s+", re.I)
# Store words guess_category doesn't know (singular, glued or store-specific: "SHORT", "FLEECE PANT",
# "Short Sleeve Crew", "BOTTOMS"); matched as stems like H&M's codes, the extra stems first.
STEMS = [("bottom", ("bottom", "bib")), ("top", ("crew", "henley", "tee", "polo", "fleece")), *HM_STEMS]


def _category(title: str, cats: list[str]) -> str | None:
    if cat := guess_category(title, *cats):
        return cat
    words = re.findall(r"[a-z]+", " ".join([title, *cats]).lower())
    for cat, stems in STEMS:
        if any(stem in w for w in words for stem in stems):
            return cat
    return None


def store_for(item: dict) -> tuple[str, str, str | None] | None:
    host = urlparse(((item.get("source") or {}).get("canonicalUrl")) or "").netloc.lower()
    return STORES.get(host)


def _option_index(item: dict, *names: str) -> int | None:
    """First option whose type is one of `names` or mentions one ("Black Crew (Size)")."""
    for i, o in enumerate(item.get("options") or []):
        kind = str(o.get("type") or "").lower()
        if kind in names or any(re.search(rf"\b{n}\b", kind) for n in names):
            return i
    return None


def _size_name(opts: list, size_i: int | None, length_i: int | None) -> str:
    """"US 4" -> "4"; waist + length -> "32x30" (how jeans are sized); no size option -> "One Size"."""
    if size_i is None or size_i >= len(opts):
        return "One Size"
    name = _US.sub("", str(opts[size_i]).strip())
    if length_i is not None and length_i < len(opts):
        name = f"{name}x{str(opts[length_i]).strip()}"
    return name


def _kith_department(item: dict) -> str:
    text = " ".join([item.get("title") or "", *(item.get("tags") or []), *(item.get("categories") or [])]).lower()
    return "women" if re.search(r"\bwomen'?s?\b|\bkith women\b", text) else "men"


def normalize_shopify(raw: list[dict], drops: Counter | None = None, max_colors: int = MAX_COLORS) -> list[dict]:
    """Shopify products -> one Product per colour. Non-apparel, unknown stores and non-USD prices are dropped."""
    drops = drops if drops is not None else Counter()
    out, now = [], _now()
    for it in raw:
        src = it.get("source") or {}
        store = store_for(it)
        if store is None:
            drops["shopify_unknown_store"] += 1
            continue
        retailer, brand, dept = store
        if (src.get("currency") or "USD") != "USD":
            drops["shopify_not_usd"] += 1
            continue
        title = it.get("title") or ""
        cats = [str(c) for c in it.get("categories") or []]
        if NOT_APPAREL.search(" ".join([title, *cats])):
            drops["shopify_not_apparel"] += 1
            continue
        cat = _category(title, cats)
        size_i = _option_index(it, "size", "waist")
        length_i = _option_index(it, "length", "inseam") if size_i is not None else None
        color_i = _option_index(it, "color", "colour")
        variants = it.get("variants") or []
        if not (src.get("id") and variants):
            drops["shopify_missing_fields"] += 1
            continue

        by_color: dict[str, list[dict]] = {}
        for v in variants:
            opts = v.get("options") or []
            color = str(opts[color_i]).strip() if color_i is not None and color_i < len(opts) else ""
            by_color.setdefault(color, []).append(v)
        colors = []
        for color, vs in by_color.items():
            sizes: dict[str, bool] = {}
            for v in vs:
                name = _size_name(v.get("options") or [], size_i, length_i)
                ok = str((v.get("price") or {}).get("stockStatus") or "").replace("_", "").lower() in IN_STOCK
                sizes[name] = sizes.get(name, False) or ok
            colors.append((color, vs, [{"name": k, "in_stock": s} for k, s in sizes.items()]))
        colors.sort(key=lambda c: not any(s["in_stock"] for s in c[2]))  # stable: keeps store order
        if len(colors) > max_colors:
            drops["shopify_extra_colors"] += len(colors) - max_colors

        medias = [m for m in it.get("medias") or [] if m.get("url") and (m.get("type") or "Image") == "Image"]
        for color, vs, sizes in colors[:max_colors]:
            ids = {str(v.get("id")) for v in vs}
            mine = [m for m in medias if ids & {str(i) for i in m.get("variantIds") or []}]
            imgs = mine or [m for m in medias if not m.get("variantIds")] or medias
            price = vs[0].get("price") or {}
            current, previous = price.get("current"), price.get("previous")
            if not (imgs and current):
                drops["shopify_missing_fields"] += 1
                continue
            current = float(current) / 100
            previous = float(previous) / 100 if previous else None
            p = _valid({
                "id": f"{retailer}:{src['id']}:{slug(color or 'default')}",
                "retailer": retailer,
                "name": title,
                "brand": it.get("brand") or brand,
                "category": cat or "top",
                "price_usd": previous if previous and previous > current else current,
                "sale_price_usd": current if previous and previous > current else None,
                "colors": [color.title()] if color else [],
                "sizes": sizes,
                "in_stock": any(s["in_stock"] for s in sizes),
                "image_url": imgs[0]["url"],
                "product_url": src.get("canonicalUrl") or "",
                # Shopify doesn't mark garment-only shots; most of these stores shoot on a model
                "images": gallery(*((m["url"], "retailer_model") for m in imgs[:6])),
                "description": plain_text(it.get("description")),
                "scraped_at": now,
                "source": "ingest",
                "department": dept or _kith_department(it),
            })
            if p is None:
                drops["shopify_invalid"] += 1
                continue
            if cat is None:
                p["category"] = None  # the tagger fills it or it's dropped, as for H&M
            out.append(p)
    return out
