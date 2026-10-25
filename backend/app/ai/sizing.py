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
import re
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]

LETTER_ORDER: tuple[str, ...] = ("XS", "S", "M", "L", "XL", "XXL")
LETTER_TO_IDX: dict[str, int] = {size: idx for idx, size in enumerate(LETTER_ORDER)}
# real catalog sizes outside the estimate range (H&M has XXS and 3XL); only picked when nearest
LETTER_TO_IDX.update({"XXS": -1, "2XS": -1, "2XL": 5, "3XL": 6, "XXXL": 6})

# Bottoms: "28/32" or "W28 L32" (waist/inseam), "28inch", or US women's 0-24 (not inches).
_WAIST_INSEAM = re.compile(r"^W?\s*(\d{2})\s*(?:/|x|\s)\s*L?\s*(\d{2})$", re.I)
_WAIST_INCH = re.compile(r'^(\d{2})\s*(?:in|inch|inches|")$', re.I)
WOMENS_US_WAIST: dict[int, float] = {0: 24.5, 2: 25.5, 4: 26.5, 6: 27.5, 8: 28.5, 10: 29.5, 12: 31.0,
                                     14: 32.5, 16: 34.5, 18: 36.5, 20: 38.5, 22: 40.5, 24: 42.5}

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

# Measurement charts: upper bounds (inches, exclusive) for XS, S, M, L, XL; anything above is XXL.
# Chart gaps (men's chest 36 -> 38) are split at the midpoint.
MENS_CHEST_BOUNDS = (34.0, 37.0, 41.0, 45.0, 49.0)       # XS<34, S 34-36, M 38-40, L 42-44, XL 46-48, XXL 50+
WOMENS_BUST_BOUNDS = (32.0, 34.5, 37.5, 40.5, 43.5)      # XS<32, S 32-34, M 35-37, L 38-40, XL 41-43, XXL 44+
WOMENS_HIP_BOUNDS = (34.0, 36.5, 39.5, 42.5, 45.5)       # XS<34, S 34-36, M 37-39, L 40-42, XL 43-45, XXL 46+
MENS_WAIST_BOUNDS = (29.0, 31.5, 34.5, 37.5, 40.5)       # XS<29, S 29-31, M 32-34, L 35-37, XL 38-40, XXL 41+
WOMENS_WAIST_BOUNDS = (25.0, 27.5, 30.5, 33.5, 36.5)     # XS<25, S 25-27, M 28-30, L 31-33, XL 34-36, XXL 37+
# US women's numeric size -> hip inches (0 and 2 share 34)
WOMENS_US_HIP: dict[int, float] = {0: 34.0, 2: 34.0, 4: 35.0, 6: 36.5, 8: 38.0, 10: 39.5, 12: 41.0,
                                   14: 43.0, 16: 45.0, 18: 47.0, 20: 49.0, 22: 51.0, 24: 53.0}
MEASURE_RANGES = {"chest_in": (26.0, 60.0), "waist_in": (20.0, 60.0), "hip_in": (28.0, 62.0), "inseam_in": (24.0, 38.0)}


def _given(val: Any, field: str) -> float | None:
    """The measurement as a float if it is a plausible number for that field, else None."""
    lo, hi = MEASURE_RANGES[field]
    if _is_valid_number(val) and lo <= float(val) <= hi:
        return float(val)
    return None


def _chart_index(value: float, bounds: tuple[float, ...]) -> int:
    for idx, bound in enumerate(bounds):
        if value < bound:
            return idx
    return len(bounds)


def _is_womens(product: dict, category: str) -> bool:
    """Women's charts for the retailer's women's section and for dresses; men's otherwise (incl. unknown)."""
    dept = str(product.get("department") or "").strip().lower()
    return dept == "women" or (category == "dress" and dept != "men")


def _size_rank(label: str, sizes: list[str]) -> int | None:
    """Position of `label` in the product's sizes sorted small -> large (letters, numbers, waist/inseam)."""
    def key(s: str):
        t = s.strip()
        if t.upper() in LETTER_TO_IDX:
            return (0, LETTER_TO_IDX[t.upper()], 0.0)
        if m := _WAIST_INSEAM.match(t):
            return (1, float(m[1]), float(m[2]))
        if m := _WAIST_INCH.match(t):
            return (1, float(m[1]), 0.0)
        try:
            return (1, float(t), 0.0)
        except ValueError:
            return (2, 0.0, 0.0)
    ordered = sorted({s.strip() for s in sizes}, key=key)
    norm = label.strip().lower()
    for i, s in enumerate(ordered):
        if s.lower() == norm:
            return i
    return None


def _reconcile_usual(out: dict, sizes: list[str], usual_size: str | None) -> dict:
    """Usual size within one size of the measured pick (and in stock) wins; 2+ apart keeps the measured
    pick and mentions the usual one."""
    if not usual_size or not out.get("size"):
        return out
    usual = str(usual_size).strip()
    stocked = next((s for s in sizes if s.lower() == usual.lower()), None)
    picked_rank = _size_rank(out["size"], sizes)
    usual_rank = _size_rank(usual, sizes) if stocked else None
    if picked_rank is None:
        return out
    if usual_rank is not None and abs(usual_rank - picked_rank) <= 1:
        return _result(stocked, out["confidence"], f"your usual {stocked} matches your measurements")
    if out["size"].lower() == usual.lower():
        return out
    return _result(out["size"], out["confidence"], f"{out['reason']} (usual {usual})")


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


def _estimate_womens_waist_inches(height_cm: float, weight_kg: float) -> float:
    """Waist for US women's numeric sizes. The general estimate above runs ~2-3 in high for these
    (a 158 cm / 50 kg person came out a US 10 instead of ~2-4)."""
    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    return max(23.0, min(46.0, 10.5 + 0.8 * bmi))


def _estimate_inseam_inches(height_cm: float) -> float:
    return height_cm * 0.45 / 2.54


def _is_womens_numeric(sizes: list[str]) -> bool:
    if any(_WAIST_INSEAM.match(s.strip()) or _WAIST_INCH.match(s.strip()) for s in sizes):
        return False
    nums = _parse_numeric_sizes(sizes)
    return bool(nums) and all(v == int(v) and int(v) in WOMENS_US_WAIST for _, v in nums)


def _bottom_candidates(sizes: list[str]) -> list[tuple[str, float, float | None]]:
    """(label, waist_in, inseam_in or None) for every size we can read as a waist."""
    out: list[tuple[str, float, float | None]] = []
    for s in sizes:
        t = s.strip()
        if m := _WAIST_INSEAM.match(t):
            out.append((s, float(m[1]), float(m[2])))
        elif m := _WAIST_INCH.match(t):
            out.append((s, float(m[1]), None))
    if out:
        return out
    nums = _parse_numeric_sizes(sizes)
    if _is_womens_numeric(sizes):
        return [(label, WOMENS_US_WAIST[int(v)], None) for label, v in nums]  # US women's 0-24
    return [(label, v, None) for label, v in nums]  # plain waist inches


def _measured_letter(
    product: dict,
    category: str,
    fit_norm: str,
    available_letters: list[tuple[str, int]],
    *,
    chest_in: Any,
    hip_in: Any,
    waist_in: Any,
) -> dict | None:
    """Letter size from a real measurement, or None when none applies (caller falls back to BMI).

    Tops / outerwear / dresses: chest (men's chest or women's bust chart). Dresses and letter-sized
    bottoms: hip (women's hip chart) when given, else waist; a dress with a chest but no hip uses the
    chest. Fit shifts one size (slim down, oversized up), clamped; the nearest in-stock letter wins."""
    womens = _is_womens(product, category)
    chest = _given(chest_in, "chest_in")
    hip = _given(hip_in, "hip_in")
    waist = _given(waist_in, "waist_in")

    if category in ("top", "outerwear") and chest is not None:
        idx, what, direct = _chart_index(chest, WOMENS_BUST_BOUNDS if womens else MENS_CHEST_BOUNDS), f"chest {chest:g} in", True
    elif category == "dress" and hip is not None and womens:
        idx, what, direct = _chart_index(hip, WOMENS_HIP_BOUNDS), f"hip {hip:g} in", True
    elif category == "dress" and chest is not None:
        idx, what, direct = _chart_index(chest, WOMENS_BUST_BOUNDS if womens else MENS_CHEST_BOUNDS), f"chest {chest:g} in", True
    elif category in ("dress", "bottom") and hip is not None and womens:
        idx, what, direct = _chart_index(hip, WOMENS_HIP_BOUNDS), f"hip {hip:g} in", True
    elif category in ("dress", "bottom") and waist is not None:
        idx, what, direct = _chart_index(waist, WOMENS_WAIST_BOUNDS if womens else MENS_WAIST_BOUNDS), f"waist {waist:g} in", False
    else:
        return None

    fit_offset = FIT_OFFSET.get(fit_norm, 0)
    target_idx = max(0, min(len(LETTER_ORDER) - 1, idx + fit_offset))
    best_size, best_idx = min(available_letters, key=lambda item: (abs(item[1] - target_idx), -item[1]))
    idx_diff = abs(best_idx - target_idx)
    if idx_diff == 0:
        conf: Confidence = "high" if direct else "medium"
    elif idx_diff == 1:
        conf = "medium"
    else:
        conf = "low"
    notes = [what]
    if fit_offset != 0:
        notes.append(f"{fit_norm} fit")
    reason = f"{', '.join(notes)} → {best_size}"
    if idx_diff > 0:
        reason += f" (nearest to {LETTER_ORDER[target_idx]})"
    return _result(best_size, conf, reason)


def recommend_size(
    product: dict,
    height_cm: float,
    weight_kg: float,
    fit: str = "regular",
    shoe_us: float | None = None,
    waist_in: float | None = None,
    chest_in: float | None = None,
    hip_in: float | None = None,
    inseam_in: float | None = None,
    usual_size: str | None = None,
) -> dict:
    """Recommend the best available size for a product without ever crashing.

    Real measurements win over the height/weight (BMI) estimate: chest (bust) for letter-sized tops,
    outerwear and dresses; hip (women) or waist for letter-sized bottoms and dresses without a chest;
    waist + inseam for "30/32"-style bottoms; hip for US women's 0-24. `usual_size` (the user's usual
    size for this category) is preferred when it is within one size of the measured pick."""
    out = _recommend(product, height_cm, weight_kg, fit, shoe_us, waist_in, chest_in, hip_in, inseam_in)
    if usual_size and isinstance(product, dict) and isinstance(product.get("sizes"), list):
        sizes = [str(s).strip() for s in product["sizes"] if isinstance(s, (str, int, float)) and str(s).strip()]
        out = _reconcile_usual(out, sizes, str(usual_size))
    return out


def _recommend(
    product: dict,
    height_cm: float,
    weight_kg: float,
    fit: str,
    shoe_us: float | None,
    waist_in: float | None,
    chest_in: float | None,
    hip_in: float | None,
    inseam_in: float | None,
) -> dict:
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

    # 4. Bottoms sized by waist: "32", "28/32" (waist/inseam), "28inch", US women's "0"-"24"
    bottom_cands = _bottom_candidates(sizes) if category == "bottom" and not available_letters else []
    if bottom_cands:
        waist_given = _given(waist_in, "waist_in")
        hip_given = _given(hip_in, "hip_in")
        inseam_given = _given(inseam_in, "inseam_in")
        womens_numeric = _is_womens_numeric(sizes)
        # US women's 0-24: hip is the chart measurement
        if womens_numeric and hip_given is not None:
            hip_cands = [(label, WOMENS_US_HIP[int(v)]) for label, v in _parse_numeric_sizes(sizes)]
            label, hip = min(hip_cands, key=lambda c: (round(abs(c[1] - hip_given), 6), c[1]))
            conf: Confidence = "high" if abs(hip - hip_given) <= 1.0 else "medium"
            return _result(label, conf, f"hip {hip_given:g} in → size {label}")
        if waist_given is None and not valid_metrics:
            return _result(None, "low", "missing waist and valid body metrics")
        estimate = _estimate_womens_waist_inches if womens_numeric else _estimate_waist_inches
        target_waist = waist_given if waist_given is not None else estimate(float(height_cm), float(weight_kg))
        has_length = any(c[2] is not None for c in bottom_cands)
        inseam = inseam_given if inseam_given is not None else (
            _estimate_inseam_inches(float(height_cm)) if valid_metrics else None)
        # nearest waist first (ties -> larger), then the length closest to their inseam (or height)
        label, waist, _ = min(bottom_cands, key=lambda c: (
            round(abs(c[1] - target_waist), 6),
            abs(c[2] - inseam) if c[2] is not None and inseam is not None else 0.0,
            -c[1]))
        if waist_given is None:
            return _result(label, "low", "waist estimated from height and weight")
        diff = abs(waist - target_waist)
        conf = "high" if diff <= 1.0 else "medium" if diff <= 2.0 else "low"
        if womens_numeric:
            return _result(label, "medium" if conf == "high" else conf, f"waist {target_waist:g} in → size {label}")
        if has_length and inseam_given is not None:
            return _result(label, conf, f"waist {target_waist:g} in, inseam {inseam_given:g} in → {label}")
        return _result(label, conf, f"waist {target_waist:g} in → {label}")

    # 5. Letter-sized apparel (tops, outerwear, dresses, letter-sized bottoms, etc.)
    if available_letters:
        measured = _measured_letter(product, category, fit_norm, available_letters,
                                    chest_in=chest_in, hip_in=hip_in, waist_in=waist_in)
        if measured:
            return measured
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
