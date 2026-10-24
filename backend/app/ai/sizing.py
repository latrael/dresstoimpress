"""
Deterministic size recommendation engine for dresstoimpress.

Letter Size Estimation Table (Base Index: 0=XS, 1=S, 2=M, 3=L, 4=XL, 5=XXL)
---------------------------------------------------------------------------
1. Base size from BMI (weight_kg / (height_m ^ 2)):
   - BMI < 18.5             -> 0 (XS)
   - 18.5 <= BMI < 21.5     -> 1 (S)
   - 21.5 <= BMI < 25.0     -> 2 (M)
   - 25.0 <= BMI < 28.5     -> 3 (L)
   - 28.5 <= BMI < 32.0     -> 4 (XL)
   - BMI >= 32.0            -> 5 (XXL)

2. Height adjustment:
   - height_cm >= 188.0     -> +1 size (tall frame adjustment)
   - height_cm < 160.0      -> -1 size (petite frame adjustment)

3. Retailer adjustment:
   - zara, mango            -> +1 size (runs small)
   - uniqlo                 -> -1 size (runs large)
   - hm, asos (and others)  ->  0 size (true to size)

4. Fit preference adjustment:
   - slim                   -> -1 size
   - regular                ->  0 size
   - oversized              -> +1 size

Final index is clamped to [0, 5] and mapped to the nearest available letter
size present in `product["sizes"]`.
"""

from __future__ import annotations

import math
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]

LETTER_ORDER: tuple[str, ...] = ("XS", "S", "M", "L", "XL", "XXL")
LETTER_TO_IDX: dict[str, int] = {size: idx for idx, size in enumerate(LETTER_ORDER)}

RETAILER_OFFSET: dict[str, int] = {
    "zara": 1,
    "mango": 1,
    "uniqlo": -1,
    "hm": 0,
    "asos": 0,
}

FIT_OFFSET: dict[str, int] = {
    "slim": -1,
    "regular": 0,
    "oversized": 1,
}


def _result(size: str | None, confidence: Confidence, reason: str) -> dict[str, Any]:
    """Format output dictionary and enforce <= 12 word reason constraint."""
    words = reason.strip().split()
    if len(words) > 12:
        reason = " ".join(words[:12])
    return {
        "size": size,
        "confidence": confidence,
        "reason": reason,
    }


def _is_valid_number(val: Any) -> bool:
    """Return True if val is a finite int or float (excluding bool)."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    return math.isfinite(float(val))


def _parse_numeric_sizes(sizes: list[str]) -> list[tuple[str, float]]:
    """Extract (original_label, numeric_value) pairs for all numeric size strings."""
    parsed: list[tuple[str, float]] = []
    for s in sizes:
        try:
            val = float(s.strip())
            if math.isfinite(val):
                parsed.append((s, val))
        except (ValueError, AttributeError):
            continue
    return parsed


def _nearest_numeric_size(
    target: float, candidates: list[tuple[str, float]]
) -> tuple[str, float]:
    """Return (size_label, abs_diff) closest to target; ties prefer the larger size."""
    best_label, best_val = min(
        candidates,
        key=lambda item: (round(abs(item[1] - target), 6), -item[1]),
    )
    return best_label, abs(best_val - target)


def _bmi_base_index(bmi: float, height_cm: float) -> int:
    """Calculate base letter index (0=XS .. 5=XXL) from BMI and height."""
    if bmi < 18.5:
        idx = 0
    elif bmi < 21.5:
        idx = 1
    elif bmi < 25.0:
        idx = 2
    elif bmi < 28.5:
        idx = 3
    elif bmi < 32.0:
        idx = 4
    else:
        idx = 5

    if height_cm >= 188.0:
        idx += 1
    elif height_cm < 160.0:
        idx -= 1

    return max(0, min(len(LETTER_ORDER) - 1, idx))


def _estimate_waist_inches(height_cm: float, weight_kg: float) -> float:
    """Estimate waist circumference in inches from BMI and height."""
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m * height_m)
    height_adj = (height_cm - 170.0) * 0.08
    estimated = 14.5 + (0.78 * bmi) + height_adj
    return max(24.0, min(46.0, estimated))


def recommend_size(
    product: dict,
    height_cm: float,
    weight_kg: float,
    fit: str = "regular",
    shoe_us: float | None = None,
    waist_in: float | None = None,
) -> dict:
    """Recommend the best available size for a product without ever crashing."""
    if not isinstance(product, dict):
        return _result(None, "low", "invalid product data")

    raw_sizes = product.get("sizes")
    if not isinstance(raw_sizes, list):
        return _result(None, "low", "no available sizes")

    sizes: list[str] = [
        str(s).strip()
        for s in raw_sizes
        if isinstance(s, (str, int, float))
        and not isinstance(s, bool)
        and str(s).strip()
    ]

    category = str(product.get("category") or "").strip().lower()
    retailer = str(product.get("retailer") or "").strip().lower()
    fit_norm = str(fit or "regular").strip().lower()

    # 1. Accessories rule: return the only size if there is one, else None with "one size"
    if category == "accessory":
        if len(sizes) == 1:
            return _result(sizes[0], "high", "one size")
        return _result(None, "low", "one size")

    # 2. Empty sizes guard for all other categories
    if not sizes:
        return _result(None, "low", "no sizes in stock")

    # 3. Shoes rule: use shoe_us nearest available half size; None + "low" if missing
    if category == "shoes":
        if not _is_valid_number(shoe_us) or float(shoe_us) <= 0:  # type: ignore[arg-type]
            return _result(None, "low", "shoe size required")
        shoe_target = round(float(shoe_us) * 2.0) / 2.0  # type: ignore[arg-type]
        numeric_shoes = _parse_numeric_sizes(sizes)
        if not numeric_shoes:
            return _result(None, "low", "no valid shoe sizes available")
        # match against the real size: rounding first (10.4 -> 10.5) can tip a tie the wrong way
        chosen, diff = _nearest_numeric_size(float(shoe_us), numeric_shoes)  # type: ignore[arg-type]
        if diff == 0:
            return _result(chosen, "high", f"exact US {shoe_target:g} shoe match")
        if diff <= 0.5:
            return _result(chosen, "medium", f"nearest half size to US {shoe_target:g}")
        return _result(chosen, "low", f"closest available shoe size to {shoe_target:g}")

    # Validate body metrics for apparel
    valid_metrics = (
        _is_valid_number(height_cm)
        and _is_valid_number(weight_kg)
        and 100.0 <= float(height_cm) <= 250.0
        and 25.0 <= float(weight_kg) <= 300.0
    )

    # Identify available letter sizes vs numeric sizes in product["sizes"]
    available_letters: list[tuple[str, int]] = []
    for s in sizes:
        upper = s.upper()
        if upper in LETTER_TO_IDX:
            available_letters.append((s, LETTER_TO_IDX[upper]))
    numeric_candidates = _parse_numeric_sizes(sizes)

    # 4. Bottoms with numeric waist sizes
    if category == "bottom" and numeric_candidates and not available_letters:
        if _is_valid_number(waist_in) and 20.0 <= float(waist_in) <= 60.0:  # type: ignore[arg-type]
            target_waist = float(waist_in)  # type: ignore[arg-type]
            chosen, diff = _nearest_numeric_size(target_waist, numeric_candidates)
            if diff <= 1.0:
                conf: Confidence = "high"
            elif diff <= 2.0:
                conf = "medium"
            else:
                conf = "low"
            return _result(chosen, conf, f"nearest waist size to {target_waist:g} in")

        if not valid_metrics:
            return _result(None, "low", "missing waist and valid body metrics")

        est_waist = _estimate_waist_inches(float(height_cm), float(weight_kg))
        chosen, _ = _nearest_numeric_size(est_waist, numeric_candidates)
        return _result(chosen, "low", "waist estimated from height and weight")

    # 5. Letter-sized apparel (tops, outerwear, dresses, letter-sized bottoms, etc.)
    if available_letters:
        if not valid_metrics:
            return _result(None, "low", "invalid height or weight measurements")

        h_cm = float(height_cm)
        w_kg = float(weight_kg)
        bmi = w_kg / ((h_cm / 100.0) ** 2)

        base_idx = _bmi_base_index(bmi, h_cm)
        ret_offset = RETAILER_OFFSET.get(retailer, 0)
        fit_offset = FIT_OFFSET.get(fit_norm, 0)

        target_idx = max(
            0, min(len(LETTER_ORDER) - 1, base_idx + ret_offset + fit_offset)
        )

        # Find nearest available letter size in product["sizes"]
        best_size, best_idx = min(
            available_letters,
            key=lambda item: (abs(item[1] - target_idx), -item[1]),
        )
        idx_diff = abs(best_idx - target_idx)

        if idx_diff == 0:
            conf = "high" if retailer in RETAILER_OFFSET else "medium"
        elif idx_diff == 1:
            conf = "medium"
        else:
            conf = "low"

        notes: list[str] = ["BMI/height estimate"]
        if ret_offset > 0:
            notes.append(f"{retailer} runs small")
        elif ret_offset < 0:
            notes.append(f"{retailer} runs large")
        if fit_offset != 0:
            notes.append(f"{fit_norm} fit")
        if idx_diff > 0:
            notes.append("clamped to stock")

        return _result(best_size, conf, ", ".join(notes))

    # 6. Fallback if non-bottom item only has numeric sizes
    if numeric_candidates and _is_valid_number(waist_in):
        chosen, _ = _nearest_numeric_size(float(waist_in), numeric_candidates)  # type: ignore[arg-type]
        return _result(chosen, "medium", "matched to nearest numeric size")

    return _result(None, "low", "unsupported size format")
