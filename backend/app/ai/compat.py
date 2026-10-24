"""Read products in either schema so the AI code doesn't depend on which one the team locks.

Contract shape (models.Product):  price_usd, product_url, category "top", colors[], sizes ["S"],
                                  style_tags[], brand
Nabil's proposal (NABIL.md):      price + currency, url, category "tops", color, sizes [{name, inStock}],
                                  tags {category, color, pattern, style[], formality: "casual"}

`as_product` returns a new dict in the contract shape (original keys kept too); the AI code reads
products only through `get_product` / `list_products`. `to_nabil_tags` turns tagger output into
his `tags` object.
"""
from __future__ import annotations

from ..store import store

SINGULAR = {
    "top": "top", "tops": "top", "shirts": "top", "t-shirts": "top", "knitwear": "top", "sweaters": "top",
    "hoodies": "top", "bottom": "bottom", "bottoms": "bottom", "pants": "bottom", "jeans": "bottom",
    "trousers": "bottom", "shorts": "bottom", "skirts": "bottom", "outerwear": "outerwear",
    "jackets": "outerwear", "coats": "outerwear", "shoes": "shoes", "sneakers": "shoes", "boots": "shoes",
    "dress": "dress", "dresses": "dress", "accessory": "accessory", "accessories": "accessory",
    "bags": "accessory", "hats": "accessory", "jewelry": "accessory",
}
PLURAL = {"top": "tops", "bottom": "bottoms", "outerwear": "outerwear", "shoes": "shoes",
          "dress": "dresses", "accessory": "accessories"}
FORMALITY_WORD_TO_INT = {"athletic": 1, "loungewear": 1, "casual": 2, "smart casual": 3,
                         "smart-casual": 3, "business": 4, "formal": 5}
BRANDS = {"zara": "Zara", "hm": "H&M", "asos": "ASOS", "uniqlo": "Uniqlo", "mango": "Mango"}


def _f(x) -> float | None:
    try:
        return float(str(x).replace("$", "").replace(",", "")) if x not in (None, "") else None
    except ValueError:
        return None


def as_product(p: dict | None) -> dict | None:
    if not p:
        return p
    tags = p.get("tags") if isinstance(p.get("tags"), dict) else {}
    raw_cat = str(p.get("category") or tags.get("category") or "").lower()
    sizes_raw = p.get("sizes") or []
    if sizes_raw and isinstance(sizes_raw[0], dict):
        in_stock = [s for s in sizes_raw if s.get("inStock", s.get("in_stock", True))]
        sizes = [str(s.get("name")) for s in in_stock if s.get("name")]
        any_stock = bool(in_stock)
    else:
        sizes = [str(s) for s in sizes_raw]
        any_stock = p.get("in_stock", True)
    color = p.get("color") or tags.get("color")
    formality = p.get("formality", tags.get("formality"))
    if isinstance(formality, str):
        formality = FORMALITY_WORD_TO_INT.get(formality.lower(), 3)
    out = dict(p)
    out.update({
        "price_usd": _f(p.get("price_usd", p.get("price"))) or 0.0,
        "sale_price_usd": _f(p.get("sale_price_usd", p.get("sale_price"))),
        "product_url": p.get("product_url") or p.get("url") or "",
        "category": SINGULAR.get(raw_cat, raw_cat),
        "colors": p.get("colors") or ([color] if color else []),
        "sizes": sizes,
        "in_stock": any_stock,
        "style_tags": p.get("style_tags") or list(tags.get("style") or []),
        "pattern": p.get("pattern") or tags.get("pattern"),
        "formality": formality,
        "brand": p.get("brand") or BRANDS.get(str(p.get("retailer", "")).lower(), ""),
        "name": p.get("name") or p.get("title") or "",
    })
    return out


def get_product(pid: str) -> dict | None:
    return as_product(store.get("products", pid))


def list_products(**where) -> list[dict]:
    return [as_product(p) for p in store.list("products", **where)]


def to_nabil_tags(item: dict) -> dict:
    """Tagger output (contract fields) -> NABIL.md `tags` object."""
    f = item.get("formality")
    word = "casual" if not isinstance(f, int) or f <= 2 else {3: "smart casual", 4: "business"}.get(f, "formal")
    return {
        "category": PLURAL.get(item.get("category", ""), item.get("category", "")),
        "color": item.get("color", ""),
        "pattern": item.get("pattern", "other"),
        "style": list(item.get("style_tags", [])),
        "formality": word,
    }


def to_canonical(p: dict) -> dict:
    """Any product shape -> the staging `Product` schema (sizes as [{name, in_stock}]).
    Use when writing products so everyone stores one shape."""
    from ..models import Product

    q = as_product(p) or {}
    raw_sizes = p.get("sizes") or []
    if raw_sizes and isinstance(raw_sizes[0], dict):
        sizes = [{"name": str(s.get("name")), "in_stock": bool(s.get("in_stock", s.get("inStock", True)))}
                 for s in raw_sizes if s.get("name")]
    else:
        sizes = [{"name": str(s), "in_stock": True} for s in raw_sizes]
    data = {k: q.get(k) for k in Product.model_fields if q.get(k) is not None}
    data["sizes"] = sizes
    data["in_stock"] = any(s["in_stock"] for s in sizes) if sizes else bool(q.get("in_stock", True))
    if data.get("category") not in PLURAL:
        data["category"] = "top"
    return Product.model_validate(data).model_dump()
