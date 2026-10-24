"""Pytest suite for sizing.py covering all rules, retailers, clamping, and edge cases."""

from __future__ import annotations

import pytest
from app.ai.sizing import recommend_size


def _word_count(text: str) -> int:
    return len(text.strip().split())


def test_regular_fit_hm_and_asos_zero_adjustment() -> None:
    """H&M and ASOS have 0 offset; standard BMI (22.2) -> M with high confidence."""
    hm_top = {
        "id": "top-1",
        "retailer": "hm",
        "category": "top",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
    }
    asos_dress = {
        "id": "dress-1",
        "retailer": "asos",
        "category": "dress",
        "sizes": ["XS", "S", "M", "L", "XL"],
    }

    res_hm = recommend_size(hm_top, height_cm=175.0, weight_kg=68.0, fit="regular")
    res_asos = recommend_size(asos_dress, height_cm=175.0, weight_kg=68.0, fit="regular")

    assert res_hm["size"] == "M"
    assert res_hm["confidence"] == "high"
    assert _word_count(res_hm["reason"]) <= 12

    assert res_asos["size"] == "M"
    assert res_asos["confidence"] == "high"
    assert _word_count(res_asos["reason"]) <= 12


def test_retailer_adjustments_zara_mango_uniqlo() -> None:
    """Zara and Mango adjust +1 size (M -> L); Uniqlo adjusts -1 size (M -> S)."""
    base_sizes = ["XS", "S", "M", "L", "XL", "XXL"]
    zara_top = {"id": "z1", "retailer": "zara", "category": "top", "sizes": base_sizes}
    mango_top = {"id": "m1", "retailer": "mango", "category": "outerwear", "sizes": base_sizes}
    uniqlo_top = {"id": "u1", "retailer": "uniqlo", "category": "top", "sizes": base_sizes}

    # 175cm, 68kg -> BMI 22.2 -> Base M
    r_zara = recommend_size(zara_top, 175.0, 68.0)
    r_mango = recommend_size(mango_top, 175.0, 68.0)
    r_uniqlo = recommend_size(uniqlo_top, 175.0, 68.0)

    assert r_zara["size"] == "L"
    assert r_mango["size"] == "L"
    assert r_uniqlo["size"] == "S"
    assert all(_word_count(r["reason"]) <= 12 for r in (r_zara, r_mango, r_uniqlo))


def test_fit_adjustments_slim_and_oversized() -> None:
    """Slim goes down 1 letter size; oversized goes up 1 letter size."""
    product = {
        "id": "hm-1",
        "retailer": "hm",
        "category": "top",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
    }
    slim_res = recommend_size(product, 175.0, 68.0, fit="slim")
    reg_res = recommend_size(product, 175.0, 68.0, fit="regular")
    over_res = recommend_size(product, 175.0, 68.0, fit="oversized")

    assert slim_res["size"] == "S"
    assert reg_res["size"] == "M"
    assert over_res["size"] == "L"


def test_clamping_at_xs_and_xxl_boundaries() -> None:
    """Going below XS clamps to XS; going above XXL clamps to XXL."""
    product = {
        "id": "u-clamp",
        "retailer": "uniqlo",  # -1 offset
        "category": "top",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
    }
    # Very low BMI (17.3) -> Base XS (0), Uniqlo (-1), slim (-1) -> clamped to XS
    res_low = recommend_size(product, height_cm=170.0, weight_kg=50.0, fit="slim")
    assert res_low["size"] == "XS"
    assert res_low["size"] in product["sizes"]

    zara_prod = {
        "id": "z-clamp",
        "retailer": "zara",  # +1 offset
        "category": "outerwear",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
    }
    # High BMI (35.4) -> Base XXL (5), Zara (+1), oversized (+1) -> clamped to XXL
    res_high = recommend_size(zara_prod, height_cm=180.0, weight_kg=115.0, fit="oversized")
    assert res_high["size"] == "XXL"
    assert res_high["size"] in zara_prod["sizes"]


def test_clamping_to_limited_available_stock() -> None:
    """When target letter size is out of stock, clamp to nearest available size in product['sizes']."""
    product = {
        "id": "asos-limited",
        "retailer": "asos",
        "category": "top",
        "sizes": ["S", "M", "L"],  # No XS, XL, XXL
    }
    res_xs = recommend_size(product, height_cm=165.0, weight_kg=46.0, fit="slim")
    res_xxl = recommend_size(product, height_cm=185.0, weight_kg=115.0, fit="oversized")

    assert res_xs["size"] == "S"
    assert res_xxl["size"] == "L"
    assert res_xs["confidence"] in ("medium", "low")
    assert res_xxl["confidence"] in ("medium", "low")


def test_bottoms_numeric_with_explicit_waist() -> None:
    """Bottoms with numeric waist sizes pick nearest available size when waist_in is provided."""
    jeans = {
        "id": "jeans-1",
        "retailer": "hm",
        "category": "bottom",
        "sizes": ["28", "30", "32", "34", "36"],
    }
    exact = recommend_size(jeans, height_cm=175.0, weight_kg=70.0, waist_in=32.0)
    near = recommend_size(jeans, height_cm=175.0, weight_kg=70.0, waist_in=31.2)

    assert exact["size"] == "32"
    assert exact["confidence"] == "high"
    assert near["size"] == "32"
    assert near["confidence"] == "high"
    assert _word_count(near["reason"]) <= 12


def test_bottoms_numeric_without_waist_estimates_low_confidence() -> None:
    """Bottoms with numeric sizes estimate waist from height/weight with confidence 'low' when waist_in is None."""
    chinos = {
        "id": "chinos-1",
        "retailer": "uniqlo",
        "category": "bottom",
        "sizes": ["28", "30", "32", "34", "36"],
    }
    res = recommend_size(chinos, height_cm=178.0, weight_kg=75.0, waist_in=None)

    assert res["size"] in chinos["sizes"]
    assert res["confidence"] == "low"
    assert _word_count(res["reason"]) <= 12


def test_shoes_with_and_without_shoe_us() -> None:
    """Shoes match nearest half size when shoe_us is given, or return None/'low' when omitted."""
    sneakers = {
        "id": "shoe-1",
        "retailer": "asos",
        "category": "shoes",
        "sizes": ["8", "8.5", "9", "9.5", "10", "11"],
    }
    exact = recommend_size(sneakers, 175.0, 70.0, shoe_us=9.5)
    nearest = recommend_size(sneakers, 175.0, 70.0, shoe_us=10.4)
    missing = recommend_size(sneakers, 175.0, 70.0, shoe_us=None)

    assert exact["size"] == "9.5"
    assert exact["confidence"] == "high"
    assert nearest["size"] == "10"
    assert nearest["confidence"] == "medium"
    assert missing == {"size": None, "confidence": "low", "reason": "shoe size required"}


def test_accessories_single_vs_multiple_or_empty_sizes() -> None:
    """Accessories return the single size if len==1, else None with reason 'one size'."""
    belt_one = {
        "id": "acc-1",
        "retailer": "zara",
        "category": "accessory",
        "sizes": ["OS"],
    }
    belt_multi = {
        "id": "acc-2",
        "retailer": "zara",
        "category": "accessory",
        "sizes": ["S", "M", "L"],
    }
    belt_empty = {
        "id": "acc-3",
        "retailer": "zara",
        "category": "accessory",
        "sizes": [],
    }

    r1 = recommend_size(belt_one, 170.0, 65.0)
    r2 = recommend_size(belt_multi, 170.0, 65.0)
    r3 = recommend_size(belt_empty, 170.0, 65.0)

    assert r1["size"] == "OS"
    assert r1["reason"] == "one size"
    assert r2["size"] is None
    assert r2["reason"] == "one size"
    assert r3["size"] is None
    assert r3["reason"] == "one size"


def test_empty_sizes_returns_none_and_low() -> None:
    """Empty sizes list on any product returns size=None and confidence='low'."""
    product = {
        "id": "empty-1",
        "retailer": "mango",
        "category": "top",
        "sizes": [],
    }
    res = recommend_size(product, 172.0, 65.0)
    assert res["size"] is None
    assert res["confidence"] == "low"
    assert _word_count(res["reason"]) <= 12


def test_height_adjustment_tall_and_petite() -> None:
    """Tall height (>=188cm) bumps letter size up; petite (<160cm) bumps down."""
    product = {
        "id": "hm-tall",
        "retailer": "hm",
        "category": "top",
        "sizes": ["XS", "S", "M", "L", "XL", "XXL"],
    }
    # Both have BMI ~20.5 (base S = index 1)
    tall = recommend_size(product, height_cm=192.0, weight_kg=75.5, fit="regular")
    petite = recommend_size(product, height_cm=155.0, weight_kg=49.2, fit="regular")

    assert tall["size"] == "M"
    assert petite["size"] == "XS"


@pytest.mark.parametrize(
    "bad_product,h,w,fit,shoe,waist",
    [
        ({}, -10.0, 0.0, "unknown_fit", -5.0, -20.0),
        ({"id": "x", "retailer": None, "category": "top", "sizes": None}, 170.0, 70.0, "", None, None),
        ({"id": "x", "retailer": "zara", "category": "top", "sizes": ["XS", "M"]}, float("nan"), 70.0, "regular", None, None),
        ({"id": "x", "retailer": "hm", "category": "shoes", "sizes": ["not-a-number"]}, 170.0, 70.0, "regular", 9.0, None),
        (None, 175.0, 70.0, "regular", None, None),  # type: ignore[arg-type]
    ],
)
def test_never_crashes_on_odd_input(
    bad_product: dict,
    h: float,
    w: float,
    fit: str,
    shoe: float | None,
    waist: float | None,
) -> None:
    """Ensure odd/malformed inputs never raise exceptions and always obey output contract."""
    res = recommend_size(bad_product, h, w, fit=fit, shoe_us=shoe, waist_in=waist)
    assert isinstance(res, dict)
    assert set(res.keys()) == {"size", "confidence", "reason"}
    assert res["confidence"] in ("high", "medium", "low")
    assert _word_count(res["reason"]) <= 12
    if isinstance(bad_product, dict) and isinstance(bad_product.get("sizes"), list) and res["size"] is not None:
        assert res["size"] in bad_product["sizes"]


# ---- real H&M size formats (Oct 23 catalog) ----

def _bottom(sizes, retailer="hm"):
    return {"category": "bottom", "retailer": retailer, "sizes": sizes}


def test_waist_inseam_sizes_pick_waist_then_length() -> None:
    jeans = _bottom(["28/30", "28/32", "30/30", "30/32", "32/30", "32/32", "34/32"])
    tall = recommend_size(jeans, 185.0, 75.0, waist_in=32)
    short = recommend_size(jeans, 165.0, 75.0, waist_in=32)
    assert tall == {"size": "32/32", "confidence": "high", "reason": "nearest waist size to 32 in"}
    assert short["size"] == "32/30"
    est = recommend_size(jeans, 175.0, 70.0)
    assert est["size"] in {"30/32", "32/32"} and est["confidence"] == "low"


def test_inch_and_womens_numeric_sizes() -> None:
    assert recommend_size(_bottom(["26inch", "28inch", "30inch"]), 165.0, 60.0, waist_in=28)["size"] == "28inch"
    womens = _bottom(["0", "2", "4", "6", "8", "10", "12", "14"])
    assert recommend_size(womens, 165.0, 60.0, waist_in=27.5)["size"] == "6"     # not "14" as if inches
    assert recommend_size(womens, 165.0, 60.0)["size"] in {"4", "6", "8", "10", "12"}


def test_xxs_and_3xl_are_understood() -> None:
    top = {"category": "top", "retailer": "hm", "sizes": ["XXS", "XS", "3XL"]}
    assert recommend_size(top, 160.0, 45.0, fit="slim")["size"] == "XS"
    assert recommend_size(top, 190.0, 130.0)["size"] == "3XL"
