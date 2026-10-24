"""
Deterministic rules-based outfit pairing and ranking engine for dresstoimpress.

Scoring Weights & Rules (Total clamped to [0.0, 1.0])
-----------------------------------------------------
1. Pairwise Item Score (when pairing a Product with a Closet item):
   - Category Compatibility (Gate + Base Weight = 0.35):
     * Same category (e.g. top + top) -> 0.0 pairing credit (disqualified from pairing).
     * Non-complementary category (e.g. dress + bottom) -> 0.0 pairing credit.
     * Complementary pairs:
       - top <-> bottom, outerwear <-> bottom, outerwear <-> top,
         outerwear <-> dress, shoes <-> any other category,
         accessory <-> any other category -> +0.35.
   - Color Harmony (Weight = 0.25):
     * Either color in NEUTRAL family (black, white, grey, beige, cream,
       navy, denim, light blue) -> +0.25.
     * Earth + (Earth, Warm, or Cool) or Same color family -> +0.20.
     * Warm + Cool -> +0.08 (lower score).
     * Unknown color fallback -> +0.15.
   - Pattern Harmony (Weight = 0.15):
     * At least one item is "solid" -> +0.15.
     * Both items are non-solid (two patterns clash) -> -0.15 penalty.
   - Shared Style & Formality Alignment (Weight = 0.15):
     * Shared style_tags between product and closet item:
       +0.10 for >=1 shared tag (+0.15 for >=2 shared tags).
     * Formality alignment (inferred from tags vs closet formality 1-5):
       up to +0.03 bonus when within 1 level, -0.05 if gap >= 3.

2. Style Text Match Boost (Weight = 0.10 with closet; up to 1.0 when closet is empty):
   - Matches tokens from `style_text` against product `name`, `style_tags`, and `colors`.
   - With non-empty closet: adds up to +0.12 bonus (+0.06 per matched keyword).
   - With empty closet: base 0.30 + 0.25 per matched keyword (clamped to [0.0, 1.0]),
     returning pairs_with=[] and reason="matches your style".
"""

from __future__ import annotations

import re
from typing import Any

STYLE_VOCAB: frozenset[str] = frozenset(
    {
        "y2k",
        "streetwear",
        "minimalist",
        "preppy",
        "athleisure",
        "vintage",
        "business",
        "boho",
        "grunge",
        "classic",
    }
)

COMPLEMENTARY_CATEGORIES: dict[str, frozenset[str]] = {
    "top": frozenset({"bottom", "outerwear", "shoes", "accessory"}),
    "bottom": frozenset({"top", "outerwear", "shoes", "accessory"}),
    "outerwear": frozenset({"bottom", "top", "dress", "shoes", "accessory"}),
    "shoes": frozenset({"top", "bottom", "outerwear", "dress", "accessory"}),
    "dress": frozenset({"outerwear", "shoes", "accessory"}),
    "accessory": frozenset({"top", "bottom", "outerwear", "shoes", "dress"}),
}

NEUTRAL_COLORS: tuple[str, ...] = (
    "light blue",
    "off white",
    "charcoal",
    "ivory",
    "silver",
    "black",
    "white",
    "grey",
    "gray",
    "beige",
    "cream",
    "navy",
    "denim",
)

EARTH_COLORS: tuple[str, ...] = (
    "olive",
    "brown",
    "khaki",
    "tan",
    "camel",
    "rust",
    "terracotta",
    "sage",
    "taupe",
    "burgundy",
    "maroon",
    "chocolate",
    "forest",
    "moss",
)

WARM_COLORS: tuple[str, ...] = (
    "red",
    "orange",
    "yellow",
    "pink",
    "coral",
    "peach",
    "gold",
    "mustard",
    "crimson",
    "magenta",
    "rose",
    "amber",
)

COOL_COLORS: tuple[str, ...] = (
    "blue",
    "green",
    "purple",
    "lavender",
    "teal",
    "mint",
    "cyan",
    "turquoise",
    "indigo",
    "violet",
    "cobalt",
    "emerald",
    "lilac",
)

PATTERN_KEYWORDS: dict[str, str] = {
    "striped": "striped",
    "stripe": "striped",
    "pinstripe": "striped",
    "plaid": "plaid",
    "checkered": "plaid",
    "gingham": "plaid",
    "tartan": "plaid",
    "flannel": "plaid",
    "graphic": "graphic",
    "printed": "graphic",
    "logo": "graphic",
    "floral": "floral",
    "flower": "floral",
    "botanical": "floral",
    "polka": "other",
    "leopard": "other",
    "zebra": "other",
    "camo": "other",
    "camouflage": "other",
    "tie-dye": "other",
    "paisley": "other",
    "houndstooth": "other",
    "argyle": "other",
}

TAG_FORMALITY: dict[str, float] = {
    "athleisure": 1.5,
    "grunge": 1.5,
    "streetwear": 2.0,
    "y2k": 2.0,
    "boho": 2.5,
    "vintage": 2.5,
    "minimalist": 3.0,
    "classic": 3.5,
    "preppy": 3.5,
    "business": 4.5,
}

STOPWORDS: frozenset[str] = frozenset(
    {"a", "an", "the", "and", "or", "for", "with", "in", "on", "to", "of", "my", "i", "want", "like"}
)


def _tokenize(text: str) -> set[str]:
    """Extract lowercase alphanumeric tokens from a string."""
    if not isinstance(text, str):
        return set()
    return {
        tok
        for tok in re.findall(r"[a-z0-9]+", text.lower())
        if tok and tok not in STOPWORDS
    }


def _color_family(color_str: Any) -> str:
    """Map a plain color description to 'neutral', 'earth', 'warm', 'cool', or 'unknown'."""
    if not isinstance(color_str, str) or not color_str.strip():
        return "unknown"
    c = " ".join(color_str.lower().strip().split())

    for kw in NEUTRAL_COLORS:
        if kw in c:
            return "neutral"
    for kw in EARTH_COLORS:
        if kw in c:
            return "earth"
    for kw in WARM_COLORS:
        if kw in c:
            return "warm"
    for kw in COOL_COLORS:
        if kw in c:
            return "cool"
    return "unknown"


def _color_harmony_score(prod_colors: list[str], closet_color: str) -> float:
    """Compute best color harmony score (max 0.25) between product colors and a closet color."""
    c_fam = _color_family(closet_color)
    if not prod_colors:
        return 0.25 if c_fam == "neutral" else 0.15

    best = 0.0
    for pc in prod_colors:
        p_fam = _color_family(pc)
        if p_fam == "neutral" or c_fam == "neutral":
            score = 0.25
        elif p_fam == "unknown" or c_fam == "unknown":
            score = 0.15
        elif p_fam == c_fam:
            score = 0.20
        elif p_fam == "earth" or c_fam == "earth":
            score = 0.20
        else:
            # warm + cool combination scores lower
            score = 0.08
        if score > best:
            best = score
    return best


def _infer_product_pattern(product: dict[str, Any]) -> str:
    """Infer pattern of a product from explicit 'pattern' key or its name/tags."""
    raw_pat = product.get("pattern")
    if isinstance(raw_pat, str) and raw_pat.strip():
        p = raw_pat.strip().lower()
        if p in {"solid", "striped", "plaid", "graphic", "floral", "other"}:
            return p

    text_parts: list[str] = []
    if isinstance(product.get("name"), str):
        text_parts.append(product["name"].lower())
    if isinstance(product.get("style_tags"), list):
        text_parts.extend(str(t).lower() for t in product["style_tags"] if isinstance(t, str))

    tokens = _tokenize(" ".join(text_parts))
    for tok in tokens:
        if tok in PATTERN_KEYWORDS:
            return PATTERN_KEYWORDS[tok]
    return "solid"


def _normalize_closet_pattern(item: dict[str, Any]) -> str:
    """Extract normalized pattern from a closet item, defaulting to 'solid'."""
    raw = item.get("pattern")
    if isinstance(raw, str) and raw.strip():
        p = raw.strip().lower()
        if p in {"solid", "striped", "plaid", "graphic", "floral", "other"}:
            return p
    label = item.get("label")
    if isinstance(label, str):
        for tok in _tokenize(label):
            if tok in PATTERN_KEYWORDS:
                return PATTERN_KEYWORDS[tok]
    return "solid"


def _infer_product_formality(tags: set[str], name_tokens: set[str]) -> float:
    """Estimate product formality on 1-5 scale from style tags and name keywords."""
    vals = [TAG_FORMALITY[t] for t in tags if t in TAG_FORMALITY]
    if "blazer" in name_tokens or "trousers" in name_tokens or "oxford" in name_tokens:
        vals.append(4.0)
    if "hoodie" in name_tokens or "sweatpants" in name_tokens or "cargo" in name_tokens:
        vals.append(1.8)
    if not vals:
        return 3.0
    return sum(vals) / len(vals)


def _closet_label(item: dict[str, Any]) -> str:
    """Get closet item label, falling back to '{color} {category}' if missing/blank."""
    raw_label = item.get("label")
    if isinstance(raw_label, str) and raw_label.strip():
        return " ".join(raw_label.strip().split())

    color = str(item.get("color") or "").strip()
    category = str(item.get("category") or "item").strip()
    fallback = f"{color} {category}".strip()
    return fallback if fallback else "closet item"


def _format_pairing_reason(label: str) -> str:
    """Build casual second-person reason <= 8 words that includes the closet item's label."""
    clean_label = " ".join(label.strip().split())
    label_words = clean_label.split()

    prefix = ["goes", "with", "your"]
    max_label_words = 8 - len(prefix)
    if len(label_words) > max_label_words:
        label_words = label_words[:max_label_words]
    return " ".join(prefix + label_words)


def _style_text_matches(product: dict[str, Any], style_text: str) -> int:
    """Count how many distinct style_text tokens/phrases match the product."""
    if not isinstance(style_text, str) or not style_text.strip():
        return 0

    query_tokens = _tokenize(style_text)
    if not query_tokens:
        return 0

    name_str = str(product.get("name") or "").lower()
    raw_tags = product.get("style_tags")
    tag_strs = [str(t).lower().strip() for t in raw_tags] if isinstance(raw_tags, list) else []
    raw_colors = product.get("colors")
    color_strs = [str(c).lower().strip() for c in raw_colors] if isinstance(raw_colors, list) else []
    cat_str = str(product.get("category") or "").lower().strip()

    prod_tokens = _tokenize(" ".join([name_str, cat_str] + tag_strs + color_strs))
    direct_hits = len(query_tokens & prod_tokens)

    # Also check substring matches for compound terms (e.g. "y2k", "baggy", "cargo")
    haystack = " ".join([name_str, cat_str] + tag_strs + color_strs)
    substr_hits = sum(
        1 for tok in query_tokens if tok not in prod_tokens and len(tok) >= 3 and tok in haystack
    )
    return direct_hits + substr_hits


def score_product(product: dict, closet: list[dict], style_text: str = "") -> dict:
    """
    Score a single product against the user's closet and optional style_text.

    Returns:
        {
            "score": float (0.0 to 1.0),
            "pairs_with": list[str] (best closet IDs first, max 2),
            "reason": str (max 8 words, casual 2nd person),
        }
    """
    if not isinstance(product, dict):
        return {"score": 0.0, "pairs_with": [], "reason": "matches your style"}

    valid_closet: list[dict[str, Any]] = (
        [c for c in closet if isinstance(c, dict)] if isinstance(closet, list) else []
    )

    text_hits = _style_text_matches(product, style_text if isinstance(style_text, str) else "")

    # Empty closet rule: score from style match only, pairs_with [], reason "matches your style"
    if not valid_closet:
        raw_tags = product.get("style_tags")
        prod_tags = {
            str(t).strip().lower()
            for t in (raw_tags if isinstance(raw_tags, list) else [])
            if isinstance(t, (str, int, float)) and str(t).strip()
        }
        vocab_overlap = len(prod_tags & STYLE_VOCAB)

        if isinstance(style_text, str) and style_text.strip():
            style_score = 0.25 + (0.30 * text_hits) + (0.08 * min(2, vocab_overlap))
        else:
            style_score = 0.35 + (0.10 * min(3, vocab_overlap))

        clamped = round(max(0.0, min(1.0, style_score)), 4)
        return {
            "score": clamped,
            "pairs_with": [],
            "reason": "matches your style",
        }

    prod_cat = str(product.get("category") or "").strip().lower()
    allowed_cats = COMPLEMENTARY_CATEGORIES.get(prod_cat, frozenset())

    raw_colors = product.get("colors")
    prod_colors = [
        str(c).strip().lower()
        for c in (raw_colors if isinstance(raw_colors, list) else [])
        if isinstance(c, (str, int, float)) and str(c).strip()
    ]

    raw_prod_tags = product.get("style_tags")
    prod_tags = {
        str(t).strip().lower()
        for t in (raw_prod_tags if isinstance(raw_prod_tags, list) else [])
        if isinstance(t, (str, int, float)) and str(t).strip()
    }

    prod_pattern = _infer_product_pattern(product)
    prod_name_tokens = _tokenize(str(product.get("name") or ""))
    prod_formality = _infer_product_formality(prod_tags, prod_name_tokens)

    # Evaluate each closet item
    pair_candidates: list[tuple[float, int, str, str]] = []
    for idx, item in enumerate(valid_closet):
        c_cat = str(item.get("category") or "").strip().lower()

        # Same category or non-complementary category gets no pairing credit
        if not prod_cat or not c_cat or c_cat == prod_cat or c_cat not in allowed_cats:
            continue

        # 1. Base complementary category credit
        item_score = 0.35

        # 2. Color harmony credit (up to 0.25)
        c_color = str(item.get("color") or "").strip().lower()
        item_score += _color_harmony_score(prod_colors, c_color)

        # 3. Pattern compatibility (+0.15 if at least one solid; -0.15 penalty for two patterns)
        c_pattern = _normalize_closet_pattern(item)
        if prod_pattern == "solid" or c_pattern == "solid":
            item_score += 0.15
        else:
            item_score -= 0.15

        # 4. Style tags & formality alignment (up to 0.18)
        raw_c_tags = item.get("style_tags")
        c_tags = {
            str(t).strip().lower()
            for t in (raw_c_tags if isinstance(raw_c_tags, list) else [])
            if isinstance(t, (str, int, float)) and str(t).strip()
        }
        shared_tags = len(prod_tags & c_tags)
        if shared_tags >= 2:
            item_score += 0.15
        elif shared_tags == 1:
            item_score += 0.10

        raw_formality = item.get("formality")
        if isinstance(raw_formality, (int, float)) and not isinstance(raw_formality, bool):
            f_val = max(1.0, min(5.0, float(raw_formality)))
            f_diff = abs(prod_formality - f_val)
            if f_diff <= 1.0:
                item_score += 0.03
            elif f_diff >= 3.0:
                item_score -= 0.05

        c_id = str(item.get("id") or f"item_{idx}")
        c_label = _closet_label(item)
        pair_candidates.append((item_score, -idx, c_id, c_label))

    style_bonus = min(0.12, 0.06 * text_hits)

    if not pair_candidates:
        # No complementary items in closet (e.g. all same category)
        fallback_score = round(max(0.0, min(0.35, 0.08 * text_hits)), 4)
        return {
            "score": fallback_score,
            "pairs_with": [],
            "reason": "matches your style",
        }

    # Sort best pairing candidates first (deterministic tie-break by original closet order)
    pair_candidates.sort(key=lambda entry: (round(entry[0], 6), entry[1]), reverse=True)

    best_pair_score, _, _, best_label = pair_candidates[0]
    second_bonus = 0.03 if len(pair_candidates) > 1 and pair_candidates[1][0] >= 0.65 else 0.0

    final_score = round(
        max(0.0, min(1.0, best_pair_score + style_bonus + second_bonus)),
        4,
    )

    pairs_with: list[str] = []
    for _, _, cid, _ in pair_candidates:
        if cid not in pairs_with:
            pairs_with.append(cid)
        if len(pairs_with) == 2:
            break

    reason = _format_pairing_reason(best_label)
    return {
        "score": final_score,
        "pairs_with": pairs_with,
        "reason": reason,
    }


def rank(
    products: list[dict],
    closet: list[dict],
    style_text: str = "",
    k: int = 10,
) -> list[dict]:
    """
    Score and rank products best-first, returning at most `k` items.
    Each returned dict has `score_product` fields plus `"product_id"`.
    """
    if not isinstance(products, list) or not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        return []

    scored_items: list[tuple[float, int, dict[str, Any]]] = []
    for idx, prod in enumerate(products):
        if not isinstance(prod, dict):
            continue
        res = score_product(prod, closet, style_text=style_text)
        prod_id = str(prod.get("id") if prod.get("id") is not None else f"prod_{idx}")
        entry = {
            "product_id": prod_id,
            "score": res["score"],
            "pairs_with": res["pairs_with"],
            "reason": res["reason"],
        }
        scored_items.append((res["score"], -idx, entry))

    scored_items.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored_items[:k]]
