"""
Complete-the-look outfit builder for dresstoimpress.

Given an `anchor` product that the user swiped right on, builds one cohesive
outfit by filling required slots (`top` + `bottom` + `shoes`, or `dress` + `shoes`)
and optional extras (`outerwear`, `accessory` if score >= 0.6) using
`app.ai.outfit_rules.score_product`.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.ai.outfit_rules import score_product

VALID_CATEGORIES: frozenset[str] = frozenset(
    {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}
)

OPTIONAL_SLOTS: tuple[str, ...] = ("outerwear", "accessory")

CLOSET_THRESHOLD: float = 0.5
OPTIONAL_THRESHOLD: float = 0.6

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
}


def _is_valid_number(val: Any) -> bool:
    """Return True if val is a finite int or float (excluding bool)."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return math.isfinite(float(val))


def _safe_price(item: dict[str, Any]) -> float:
    """Extract non-negative finite price_usd from a product dict, defaulting to 0.0."""
    raw = item.get("price_usd")
    if _is_valid_number(raw):
        return max(0.0, float(raw))  # type: ignore[arg-type]
    return 0.0


def _truncate_reason(reason: Any, fallback: str = "completes your look") -> str:
    """Ensure reason is a non-empty string with at most 8 words."""
    text = str(reason or "").strip()
    if not text:
        text = fallback
    words = text.split()
    if len(words) > 8:
        return " ".join(words[:8])
    return " ".join(words)


def _closet_label(item: dict[str, Any]) -> str:
    """Return closet item's label, or '{color} {category}' if label is missing/empty."""
    raw_label = item.get("label")
    if isinstance(raw_label, str) and raw_label.strip():
        return " ".join(raw_label.strip().split())

    color = str(item.get("color") or "").strip()
    category = str(item.get("category") or "item").strip()
    fallback = f"{color} {category}".strip()
    return fallback if fallback else "closet item"


def _catalog_label(item: dict[str, Any]) -> str:
    """Return catalog item's name, or '{first_color} {category}' if name is missing/empty."""
    raw_name = item.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        return " ".join(raw_name.strip().split())

    raw_label = item.get("label")
    if isinstance(raw_label, str) and raw_label.strip():
        return " ".join(raw_label.strip().split())

    colors = item.get("colors")
    first_color = ""
    if isinstance(colors, list) and colors:
        first_color = str(colors[0] or "").strip()
    category = str(item.get("category") or "item").strip()
    fallback = f"{first_color} {category}".strip()
    return fallback if fallback else "catalog item"


def _infer_pattern(item: dict[str, Any]) -> str:
    """Infer pattern string from explicit 'pattern' field or item name/label."""
    raw_pat = item.get("pattern")
    if isinstance(raw_pat, str) and raw_pat.strip():
        p = raw_pat.strip().lower()
        if p in {"solid", "striped", "plaid", "graphic", "floral", "other"}:
            return p

    text = f"{item.get('name') or ''} {item.get('label') or ''}".lower()
    for tok in re.findall(r"[a-z0-9]+", text):
        if tok in PATTERN_KEYWORDS:
            return PATTERN_KEYWORDS[tok]
    return "solid"


def _as_closet_shape(item: dict[str, Any], source: str) -> dict[str, Any]:
    """
    Normalize a chosen product or closet item into the Closet Item schema
    expected by `score_product(candidate, [already_chosen_items])`.
    """
    item_id = str(item.get("id") or "")
    category = str(item.get("category") or "").strip().lower()

    if source == "closet":
        label = _closet_label(item)
    else:
        label = _catalog_label(item)

    raw_color = item.get("color")
    if isinstance(raw_color, str) and raw_color.strip():
        color = raw_color.strip().lower()
    else:
        raw_colors = item.get("colors")
        if isinstance(raw_colors, list) and raw_colors:
            color = str(raw_colors[0] or "").strip().lower()
        else:
            color = ""

    pattern = _infer_pattern(item)

    raw_tags = item.get("style_tags")
    style_tags = (
        [str(t).strip().lower() for t in raw_tags if isinstance(t, (str, int, float)) and str(t).strip()]
        if isinstance(raw_tags, list)
        else []
    )

    raw_formality = item.get("formality")
    formality = (
        int(max(1, min(5, round(float(raw_formality)))))
        if _is_valid_number(raw_formality)
        else 3
    )

    return {
        "id": item_id,
        "label": label,
        "category": category,
        "color": color,
        "pattern": pattern,
        "style_tags": style_tags,
        "formality": formality,
    }


def _as_product_shape(item: dict[str, Any], source: str) -> dict[str, Any]:
    """
    Normalize a candidate (from either closet or catalog) into the Product schema
    expected as the first argument of `score_product(candidate, chosen_closet_list)`.
    """
    item_id = str(item.get("id") or "")
    category = str(item.get("category") or "").strip().lower()
    name = _closet_label(item) if source == "closet" else _catalog_label(item)

    raw_colors = item.get("colors")
    if isinstance(raw_colors, list) and raw_colors:
        colors = [
            str(c).strip().lower()
            for c in raw_colors
            if isinstance(c, (str, int, float)) and str(c).strip()
        ]
    elif isinstance(item.get("color"), str) and item["color"].strip():
        colors = [item["color"].strip().lower()]
    else:
        colors = []

    raw_tags = item.get("style_tags")
    style_tags = (
        [str(t).strip().lower() for t in raw_tags if isinstance(t, (str, int, float)) and str(t).strip()]
        if isinstance(raw_tags, list)
        else []
    )

    prod: dict[str, Any] = {
        "id": item_id,
        "name": name,
        "category": category,
        "price_usd": _safe_price(item),
        "colors": colors,
        "style_tags": style_tags,
    }
    if "pattern" in item:
        prod["pattern"] = item["pattern"]
    if "formality" in item:
        prod["formality"] = item["formality"]
    return prod


def _evaluate_candidate(
    candidate: dict[str, Any],
    source: str,
    chosen_context: list[dict[str, Any]],
    style_text: str,
) -> tuple[float, str]:
    """Score a candidate against the already-chosen outfit items using score_product."""
    prod_view = _as_product_shape(candidate, source)
    try:
        res = score_product(prod_view, chosen_context, style_text=style_text)
        raw_score = float(res.get("score", 0.0))
        score = max(0.0, min(1.0, raw_score)) if math.isfinite(raw_score) else 0.0
        reason = _truncate_reason(res.get("reason", "completes your look"))
        return score, reason
    except Exception:
        return 0.0, "completes your look"


def _determine_required_slots(
    anchor_cat: str,
    anchor_as_closet: dict[str, Any],
    valid_closet: list[dict[str, Any]],
    valid_catalog: list[dict[str, Any]],
    remaining_budget: float | None,
    style_text: str,
) -> list[str]:
    """
    Determine the required slots to complete the outfit around `anchor`:
    - If anchor is 'dress': requires ['shoes'].
    - If anchor is 'top': requires ['bottom', 'shoes'].
    - If anchor is 'bottom': requires ['top', 'shoes'].
    - If anchor is 'shoes', 'outerwear', or 'accessory':
      supports either ('top', 'bottom', 'shoes') or ('dress', 'shoes')
      minus the anchor's own category. Picks the dress path if a valid dress
      in closet (>= 0.5) or affordable in-stock catalog outscores the best top+bottom
      when no top/bottom is available or when dress is strictly preferred and top/bottom
      cannot both be satisfied.
    """
    if anchor_cat == "dress":
        return ["shoes"]
    if anchor_cat == "top":
        return ["bottom", "shoes"]
    if anchor_cat == "bottom":
        return ["top", "shoes"]

    # Anchor is shoes, outerwear, or accessory
    base_sep = [s for s in ("top", "bottom", "shoes") if s != anchor_cat]
    base_dress = [s for s in ("dress", "shoes") if s != anchor_cat]

    has_closet_top_or_bottom = any(
        str(c.get("category") or "").strip().lower() in {"top", "bottom"}
        for c in valid_closet
    )
    has_closet_dress = any(
        str(c.get("category") or "").strip().lower() == "dress"
        for c in valid_closet
    )

    if has_closet_dress and not has_closet_top_or_bottom:
        # Check if any closet dress scores >= 0.5
        for c in valid_closet:
            if str(c.get("category") or "").strip().lower() == "dress":
                sc, _ = _evaluate_candidate(c, "closet", [anchor_as_closet], style_text)
                if sc >= CLOSET_THRESHOLD:
                    return base_dress

    if not has_closet_top_or_bottom:
        has_cat_top_or_bottom = any(
            str(p.get("category") or "").strip().lower() in {"top", "bottom"}
            and p.get("in_stock") is True
            and (remaining_budget is None or _safe_price(p) <= remaining_budget + 1e-9)
            for p in valid_catalog
        )
        has_cat_dress = any(
            str(p.get("category") or "").strip().lower() == "dress"
            and p.get("in_stock") is True
            and (remaining_budget is None or _safe_price(p) <= remaining_budget + 1e-9)
            for p in valid_catalog
        )
        if has_cat_dress and not has_cat_top_or_bottom:
            return base_dress

    return base_sep


def complete_look(
    anchor: dict,
    closet: list[dict],
    catalog: list[dict],
    budget_usd: float | None = None,
    style_text: str = "",
) -> dict:
    """
    Build one complete outfit around `anchor`.

    Returns:
        {
            "anchor_id": str,
            "items": [
                {
                    "source": "closet" | "catalog",
                    "id": str,
                    "category": str,
                    "label": str,
                    "reason": str (max 8 words),
                },
                ...
            ],
            "new_items_total_usd": float,
            "missing": list[str],
            "score": float (0.0 to 1.0),
        }
    """
    if not isinstance(anchor, dict):
        return {
            "anchor_id": "",
            "items": [],
            "new_items_total_usd": 0.0,
            "missing": ["top", "bottom", "shoes"],
            "score": 0.0,
        }

    anchor_id = str(anchor.get("id") if anchor.get("id") is not None else "")
    anchor_cat = str(anchor.get("category") or "").strip().lower()
    anchor_price = _safe_price(anchor)
    safe_style_text = style_text if isinstance(style_text, str) else ""

    valid_budget: float | None = None
    if budget_usd is not None and _is_valid_number(budget_usd):
        valid_budget = float(budget_usd)

    valid_closet: list[dict[str, Any]] = [
        c
        for c in (closet if isinstance(closet, list) else [])
        if isinstance(c, dict)
        and str(c.get("category") or "").strip().lower() in VALID_CATEGORIES
    ]

    valid_catalog: list[dict[str, Any]] = [
        p
        for p in (catalog if isinstance(catalog, list) else [])
        if isinstance(p, dict)
        and str(p.get("category") or "").strip().lower() in VALID_CATEGORIES
        and str(p.get("id") if p.get("id") is not None else "") != anchor_id
    ]

    new_items_total = anchor_price
    remaining_budget = (
        (valid_budget - new_items_total) if valid_budget is not None else None
    )

    anchor_closet_repr = _as_closet_shape(anchor, "catalog")
    chosen_context: list[dict[str, Any]] = (
        [anchor_closet_repr] if anchor_cat in VALID_CATEGORIES else []
    )

    used_categories: set[str] = {anchor_cat} if anchor_cat in VALID_CATEGORIES else set()
    used_ids: set[str] = {anchor_id} if anchor_id else set()

    required_slots = _determine_required_slots(
        anchor_cat,
        anchor_closet_repr,
        valid_closet,
        valid_catalog,
        remaining_budget,
        safe_style_text,
    )

    added_records: list[dict[str, Any]] = []
    missing_slots: list[str] = []

    def _pick_for_slot(slot: str, is_optional: bool) -> bool:
        nonlocal new_items_total, remaining_budget

        if slot in used_categories:
            return True

        min_closet_score = OPTIONAL_THRESHOLD if is_optional else CLOSET_THRESHOLD
        min_catalog_score = OPTIONAL_THRESHOLD if is_optional else 0.0

        # 1. Try CLOSET candidates first (free)
        closet_scored: list[tuple[float, int, dict[str, Any], str]] = []
        for idx, c_item in enumerate(valid_closet):
            c_cat = str(c_item.get("category") or "").strip().lower()
            c_id = str(c_item.get("id") if c_item.get("id") is not None else f"closet_{idx}")
            if c_cat != slot or c_id in used_ids:
                continue
            sc, rsn = _evaluate_candidate(c_item, "closet", chosen_context, safe_style_text)
            closet_scored.append((sc, -idx, c_item, rsn))

        closet_scored.sort(key=lambda x: (round(x[0], 6), x[1]), reverse=True)

        if closet_scored and closet_scored[0][0] >= min_closet_score:
            best_sc, _, best_item, best_rsn = closet_scored[0]
            item_id = str(best_item.get("id") if best_item.get("id") is not None else "")
            label = _closet_label(best_item)
            added_records.append(
                {
                    "entry": {
                        "source": "closet",
                        "id": item_id,
                        "category": slot,
                        "label": label,
                        "reason": best_rsn,
                    },
                    "raw": best_item,
                    "source": "closet",
                    "step_score": best_sc,
                }
            )
            used_categories.add(slot)
            if item_id:
                used_ids.add(item_id)
            chosen_context.append(_as_closet_shape(best_item, "closet"))
            return True

        # 2. Fall back to CATALOG (must be in_stock == True and within budget_usd)
        catalog_scored: list[tuple[float, float, int, dict[str, Any], str]] = []
        for idx, p_item in enumerate(valid_catalog):
            p_cat = str(p_item.get("category") or "").strip().lower()
            p_id = str(p_item.get("id") if p_item.get("id") is not None else f"catalog_{idx}")
            if p_cat != slot or p_id in used_ids:
                continue
            if p_item.get("in_stock") is not True:
                continue
            p_price = _safe_price(p_item)
            if valid_budget is not None and (new_items_total + p_price) > valid_budget + 1e-9:
                continue

            sc, rsn = _evaluate_candidate(p_item, "catalog", chosen_context, safe_style_text)
            if sc >= min_catalog_score:
                # Tie-break by higher score, lower price, then original catalog order
                catalog_scored.append((sc, -p_price, -idx, p_item, rsn))

        catalog_scored.sort(key=lambda x: (round(x[0], 6), round(x[1], 4), x[2]), reverse=True)

        if catalog_scored:
            best_sc, _, _, best_prod, best_rsn = catalog_scored[0]
            item_id = str(best_prod.get("id") if best_prod.get("id") is not None else "")
            label = _catalog_label(best_prod)
            p_price = _safe_price(best_prod)
            added_records.append(
                {
                    "entry": {
                        "source": "catalog",
                        "id": item_id,
                        "category": slot,
                        "label": label,
                        "reason": best_rsn,
                    },
                    "raw": best_prod,
                    "source": "catalog",
                    "step_score": best_sc,
                }
            )
            new_items_total = round(new_items_total + p_price, 2)
            if valid_budget is not None:
                remaining_budget = valid_budget - new_items_total
            used_categories.add(slot)
            if item_id:
                used_ids.add(item_id)
            chosen_context.append(_as_closet_shape(best_prod, "catalog"))
            return True

        return False

    # Fill required slots first
    for req_slot in required_slots:
        if not _pick_for_slot(req_slot, is_optional=False):
            missing_slots.append(req_slot)

    # Fill optional slots (outerwear and at most one accessory) only if score_product >= 0.6
    for opt_slot in OPTIONAL_SLOTS:
        if opt_slot not in used_categories:
            _pick_for_slot(opt_slot, is_optional=True)

    # Calculate final outfit score:
    # Average score_product of each added item against the rest of the outfit (1.0 if nothing to add)
    if not added_records:
        final_score = 1.0 if not missing_slots else 0.0
    else:
        full_outfit_reprs: list[tuple[int, dict[str, Any]]] = []
        if anchor_cat in VALID_CATEGORIES:
            full_outfit_reprs.append((-1, anchor_closet_repr))
        for i, rec in enumerate(added_records):
            full_outfit_reprs.append((i, _as_closet_shape(rec["raw"], rec["source"])))

        per_item_scores: list[float] = []
        for i, rec in enumerate(added_records):
            rest_of_outfit = [repr_d for idx, repr_d in full_outfit_reprs if idx != i]
            if rest_of_outfit:
                sc, _ = _evaluate_candidate(rec["raw"], rec["source"], rest_of_outfit, safe_style_text)
            else:
                sc = float(rec["step_score"])
            per_item_scores.append(sc)

        final_score = round(
            max(0.0, min(1.0, sum(per_item_scores) / len(per_item_scores))),
            4,
        )

    return {
        "anchor_id": anchor_id,
        "items": [rec["entry"] for rec in added_records],
        "new_items_total_usd": round(new_items_total, 2),
        "missing": missing_slots,
        "score": final_score,
    }
