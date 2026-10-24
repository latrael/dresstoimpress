"""Style DNA: a profile of what someone wears, from swipes and closet. Pure rules, no AI, free.

First draft by Gemini, reviewed by Adam. Used by GET /users/{id}/style ("Your Style DNA" card) and
POST /users/{id}/style/apply (saves the learned price ranges on the user, which pairing uses).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from .colors import normalize_color

LIKED_WEIGHT = 1.0
CLOSET_WEIGHT = 0.5
DISCARDED_PENALTY = 0.5

TOP_STYLES_LIMIT = 3
TOP_PALETTE_LIMIT = 5
TOP_RETAILERS_LIMIT = 3
AVOID_LIMIT = 3
AVOID_MIN_DISCARDED = 2

SECOND_STYLE_SHARE_MIN = 0.25
ACCENT_STREAK_SHARE_MIN = 0.15
NEUTRAL_PALETTE_SHARE_MIN = 0.70

PRICE_MIN_ITEMS = 2
PRICE_LOW_PERCENTILE = 0.20
PRICE_HIGH_PERCENTILE = 0.80
PRICE_STEP = 5

CONFIDENCE_MEDIUM_MIN = 5
CONFIDENCE_HIGH_MIN = 15
DEFAULT_HEADLINE = "Swipe more to find your style"
DISPLAY = {"y2k": "Y2K"}  # style tags that don't title-case well

VALID_CATEGORIES = frozenset({"top", "bottom", "outerwear", "shoes", "dress", "accessory"})
VALID_PATTERNS = frozenset({"solid", "striped", "plaid", "graphic", "floral", "other"})


def _valid_items(raw: Any) -> list[dict[str, Any]]:
    return [it for it in raw if isinstance(it, dict) and it] if isinstance(raw, list) else []


def _main_color(item: dict[str, Any]) -> dict[str, str] | None:
    """Normalized main color (colors[0] for products, color for closet items); None if unknown."""
    colors = item.get("colors")
    raw = colors[0] if isinstance(colors, list) and colors else item.get("color")
    if not isinstance(raw, str) or not raw.strip():
        return None
    c = normalize_color(raw)
    if c["family"] == "unknown":  # also drops multicolor
        return None
    return {"name": c["name"], "family": c["family"], "hex": c["hex"]}


def _tags(item: dict[str, Any]) -> list[str]:
    raw = item.get("style_tags")
    return sorted({t.strip().lower() for t in raw if isinstance(t, str) and t.strip()}) if isinstance(raw, list) else []


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def _effective_price(item: dict[str, Any]) -> float | None:
    """Sale price when it's set and lower, else the list price."""
    price, sale = _num(item.get("price_usd")), _num(item.get("sale_price_usd"))
    if price is not None and sale is not None:
        return min(price, sale)
    return price if price is not None else sale


def _percentile(vals: list[float], q: float) -> float:
    """Linear interpolation on a sorted, non-empty list."""
    pos = q * (len(vals) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return vals[lo] + (pos - lo) * (vals[hi] - vals[lo])


def _formality(items: list[tuple[dict[str, Any], float]]) -> dict[str, Any]:
    total = weight = 0.0
    for item, w in items:
        f = item.get("formality")
        if isinstance(f, (int, float)) and not isinstance(f, bool) and f == int(f) and 1 <= f <= 5:
            total += f * w
            weight += w
    if weight <= 0:
        return {"avg": None, "label": "unknown"}
    avg = round(total / weight, 1)
    label = ("loungewear" if avg < 1.5 else "casual" if avg < 2.5 else "smart casual" if avg < 3.5
             else "dressy" if avg < 4.5 else "formal")
    return {"avg": avg, "label": label}


def _shares(weights: dict[str, float]) -> list[tuple[str, float, float]]:
    """(name, rounded share, raw share), floored at 0, biggest first, ties by name."""
    pos = {k: v for k, v in weights.items() if v > 0}
    total = sum(pos.values())
    if total <= 0:
        return []
    rows = [(k, round(v / total, 2), v / total) for k, v in sorted(pos.items(), key=lambda x: (-x[1], x[0]))]
    return [r for r in rows if r[1] > 0]


def _headline(styles: list[dict[str, Any]], palette: list[dict[str, Any]]) -> str:
    if not styles:
        return DEFAULT_HEADLINE
    first = DISPLAY.get(styles[0]["tag"], styles[0]["tag"].capitalize())
    if len(styles) >= 2 and styles[1]["share"] >= SECOND_STYLE_SHARE_MIN:
        first += " " + DISPLAY.get(styles[1]["tag"], styles[1]["tag"])
    accents = [c for c in palette if c["family"] != "neutral"]
    neutral_share = sum(c["raw"] for c in palette if c["family"] == "neutral")
    if accents and accents[0]["raw"] >= ACCENT_STREAK_SHARE_MIN:
        first += f" with a {accents[0]['name']} streak"
    elif palette and neutral_share >= NEUTRAL_PALETTE_SHARE_MIN:
        first += " in clean neutrals"
    return " ".join(first.split()[:8])


def style_profile(liked: list[dict[str, Any]], discarded: list[dict[str, Any]] | None = None,
                  closet: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Style DNA from liked / discarded products and closet items. Never raises."""
    liked_l, discarded_l, closet_l = _valid_items(liked), _valid_items(discarded), _valid_items(closet)
    n_liked = len(liked_l)
    positive = [(it, LIKED_WEIGHT) for it in liked_l] + [(it, CLOSET_WEIGHT) for it in closet_l]

    style_w: defaultdict[str, float] = defaultdict(float)
    color_w: defaultdict[str, float] = defaultdict(float)
    color_meta: dict[str, tuple[str, str]] = {}
    liked_counts: Counter[str] = Counter()
    discarded_counts: Counter[str] = Counter()

    for item, w in positive:
        is_liked = w == LIKED_WEIGHT
        for tag in _tags(item):
            style_w[tag] += w
            liked_counts[tag] += is_liked
        if c := _main_color(item):
            color_w[c["name"]] += w
            color_meta[c["name"]] = (c["family"], c["hex"])
            liked_counts[c["name"]] += is_liked
    for item in discarded_l:
        for tag in _tags(item):
            style_w[tag] -= DISCARDED_PENALTY
            discarded_counts[tag] += 1
        if c := _main_color(item):
            color_w[c["name"]] -= DISCARDED_PENALTY
            color_meta.setdefault(c["name"], (c["family"], c["hex"]))
            discarded_counts[c["name"]] += 1

    styles = [{"tag": k, "share": s} for k, s, _ in _shares(style_w)][:TOP_STYLES_LIMIT]
    full_palette = [{"name": k, "family": color_meta[k][0], "hex": color_meta[k][1], "share": s, "raw": raw}
                    for k, s, raw in _shares(color_w)]

    pattern_w: defaultdict[str, float] = defaultdict(float)
    for item, w in positive:
        pat = item.get("pattern")
        if isinstance(pat, str) and pat.strip().lower() in VALID_PATTERNS:
            pattern_w[pat.strip().lower()] += w

    cat_prices: defaultdict[str, list[float]] = defaultdict(list)
    retailers: Counter[str] = Counter()
    for item in liked_l:
        cat, price = item.get("category"), _effective_price(item)
        if isinstance(cat, str) and cat.strip().lower() in VALID_CATEGORIES and price is not None:
            cat_prices[cat.strip().lower()].append(price)
        if isinstance(item.get("retailer"), str) and item["retailer"].strip():
            retailers[item["retailer"].strip().lower()] += 1

    price_ranges: dict[str, list[int]] = {}
    for cat in sorted(cat_prices):
        prices = sorted(cat_prices[cat])
        if len(prices) < PRICE_MIN_ITEMS:
            continue
        low = int(math.floor(_percentile(prices, PRICE_LOW_PERCENTILE) / PRICE_STEP) * PRICE_STEP)
        high = int(math.ceil(_percentile(prices, PRICE_HIGH_PERCENTILE) / PRICE_STEP) * PRICE_STEP)
        if low == high:
            low, high = max(0, low - PRICE_STEP), high + PRICE_STEP
        price_ranges[cat] = [low, high]

    avoid = sorted(((k, n) for k, n in discarded_counts.items()
                    if n >= AVOID_MIN_DISCARDED and n > liked_counts[k]), key=lambda x: (-x[1], x[0]))

    return {
        "headline": _headline(styles, full_palette),
        "styles": styles,
        "palette": [{k: v for k, v in c.items() if k != "raw"} for c in full_palette[:TOP_PALETTE_LIMIT]],
        "patterns": {k: s for k, s, _ in _shares(pattern_w)},
        "formality": _formality(positive),
        "price_ranges": price_ranges,
        "favorite_retailers": [{"retailer": k, "share": s} for k, s, _ in _shares(retailers)][:TOP_RETAILERS_LIMIT],
        "avoid": [k for k, _ in avoid[:AVOID_LIMIT]],
        "sample_size": {"liked": n_liked, "discarded": len(discarded_l), "closet": len(closet_l)},
        "confidence": "low" if n_liked < CONFIDENCE_MEDIUM_MIN else "medium" if n_liked < CONFIDENCE_HIGH_MIN else "high",
    }


if __name__ == "__main__":
    def p(cat, price, color, tags, label, pattern="solid", formality=2, retailer="hm", sale=None):
        return {"category": cat, "price_usd": price, "sale_price_usd": sale, "colors": [color], "style_tags": tags,
                "pattern": pattern, "formality": formality, "retailer": retailer, "label": label}

    liked = [p("top", 18, "white", ["streetwear", "minimalist"], "white tee", retailer="uniqlo", sale=12),
             p("top", 45, "mustard", ["streetwear"], "mustard hoodie", pattern="graphic", formality=1),
             p("top", 28, "black", ["minimalist"], "black mock neck", retailer="uniqlo"),
             p("top", 35, "grey", ["streetwear", "minimalist"], "grey sweatshirt"),
             p("bottom", 50, "light blue", ["streetwear"], "light blue jeans"),
             p("bottom", 60, "charcoal", ["streetwear", "minimalist"], "charcoal wide jeans", retailer="uniqlo")]
    discarded = [p("dress", 55, "pink", ["boho"], "pink floral dress", pattern="floral", formality=3),
                 p("dress", 65, "yellow", ["boho"], "yellow floral dress", pattern="floral", formality=3),
                 p("top", 20, "neon green", ["y2k"], "neon tank", formality=1)]
    closet = [{"category": "bottom", "color": "black", "style_tags": ["streetwear"], "label": "black cargos"},
              {"category": "bottom", "color": "denim", "style_tags": ["streetwear"], "label": "baggy jeans"},
              {"category": "shoes", "color": "white", "style_tags": ["minimalist"], "label": "white sneakers"}]
    print(style_profile(liked, discarded, closet))
