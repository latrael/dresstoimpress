"""Sprint-3 0.1 sizing fixes: numeric tops from bust, combined XS/S sizes, One Size.

Profile throughout: the woman from NABIL_TO_ADAM.md 6:10 PM, 165 cm / 58 kg / 34-27-37 in.
"""

import json
import statistics
from collections import Counter
from pathlib import Path

import pytest



def recommend_size(*args, **kwargs):
    # imported lazily: a module-level `app` import at collection time would pin app.store's
    # DATA_DIR before test_ai.py's fixture sets its own (test_ai then 404s on its seed products)
    from app.ai.sizing import recommend_size as _rec
    return _rec(*args, **kwargs)

WOMAN = dict(height_cm=165, weight_kg=58, chest_in=34, waist_in=27, hip_in=37)
SEED = Path(__file__).resolve().parents[1] / "seed" / "products.json"


def _pp(category: str, sizes=("0", "2", "4", "6", "8", "10", "12")) -> dict:
    return {"retailer": "princesspolly", "department": "women", "category": category, "sizes": list(sizes)}


# 1. numeric-sized tops / dresses map from bust (and hip), never size number vs waist inches
def test_numeric_top_from_bust_not_waist():
    out = recommend_size(_pp("top"), **WOMAN)
    assert out["size"] in {"4", "6"}
    assert out["confidence"] == "high"
    assert "bust 34" in out["reason"]


def test_numeric_top_without_chest_uses_waist_chart():
    out = recommend_size(_pp("top"), 165, 58, waist_in=27)
    assert out["size"] == "6"  # WOMENS_US_WAIST 6 = 27.5 in, not size "12"


def test_numeric_top_no_measurements_estimates_low():
    out = recommend_size(_pp("top"), 165, 58)
    assert out["size"] in {"2", "4", "6"}
    assert out["confidence"] == "low"


def test_numeric_dress_uses_larger_of_bust_and_hip():
    out = recommend_size({**_pp("dress"), "retailer": "hm"}, **WOMAN)
    assert out["size"] == "6"  # bust 34 -> 4, hip 37 -> 6; the dress must fit the hips
    assert "hip 37" in out["reason"] and "bust 34" in out["reason"]


def test_numeric_top_nearest_in_stock():
    out = recommend_size(_pp("top", sizes=["8", "10", "12"]), **WOMAN)
    assert out["size"] == "8"
    assert out["confidence"] == "medium"


# 2. combined sizes
# a letter covered by two combined sizes (S: XS/S and S/M) takes the larger, like letter ties
@pytest.mark.parametrize("chest,expected", [(31, "XS/S"), (33, "S/M"), (36, "M/L"), (39, "L/XL"), (42, "L/XL")])
def test_combined_sizes_cover_computed_letter(chest, expected):
    product = {"retailer": "brandymelville", "department": "women", "category": "top",
               "sizes": ["XS/S", "S/M", "M/L", "L/XL"]}
    out = recommend_size(product, 165, 58, chest_in=chest)
    assert out["size"] == expected
    assert out["confidence"] == "high"


def test_single_combined_size_covering_letter_is_high():
    product = {"retailer": "brandymelville", "department": "women", "category": "top", "sizes": ["XS/S"]}
    out = recommend_size(product, **WOMAN)  # bust 34 -> S, covered by XS/S
    assert out == {"size": "XS/S", "confidence": "high", "reason": "chest 34 in → XS/S"}


def test_combined_size_bmi_path_and_spelling_variants():
    product = {"retailer": "brandymelville", "department": "women", "category": "top", "sizes": ["xs - s", "M/L"]}
    out = recommend_size(product, 165, 58)  # BMI 21.3 -> S
    assert out["size"] == "xs - s"
    assert "clamped" not in out["reason"]


def test_combined_size_far_from_letter_is_low():
    product = {"retailer": "brandymelville", "category": "top", "sizes": ["L/XL"]}
    out = recommend_size(product, 165, 58, chest_in=33)  # XS vs L/XL (3.5 away)
    assert out["size"] == "L/XL" and out["confidence"] == "low"


# 3. One Size
@pytest.mark.parametrize("label", ["One Size", "OS", "ONE SIZE", "one-size", "O/S"])
def test_one_size(label):
    product = {"retailer": "brandymelville", "category": "top", "sizes": [label]}
    assert recommend_size(product, **WOMAN) == {"size": label, "confidence": "high", "reason": "one size"}


def test_one_size_out_of_stock_still_no_size():
    product = {"retailer": "brandymelville", "category": "top", "sizes": []}
    assert recommend_size(product, **WOMAN)["size"] is None


# 4. regression over the snapshot catalog
@pytest.fixture(scope="module")
def catalog():
    if not SEED.exists():
        pytest.skip("seed/products.json missing")
    from app.ai.compat import as_product
    return [as_product(p) for p in json.loads(SEED.read_text())]


def test_catalog_princess_polly_tops_median(catalog):
    picks = [recommend_size(p, **WOMAN)["size"] for p in catalog
             if p["retailer"] == "princesspolly" and p["category"] == "top" and p["sizes"]
             and all(s.isdigit() for s in p["sizes"])]  # numeric-sized (a few PP tops are S/M)
    assert len(picks) >= 100
    assert all(s is not None for s in picks)
    assert statistics.median(int(s) for s in picks) in {2, 4, 6, 8}
    assert Counter(picks)["12"] <= len(picks) * 0.05


def test_catalog_brandy_melville_gets_a_size(catalog):
    stocked = [p for p in catalog if p["retailer"] == "brandymelville" and p["sizes"]]
    assert len(stocked) >= 100
    sized = [recommend_size(p, **WOMAN) for p in stocked]
    assert sum(r["size"] is not None for r in sized) >= 0.9 * len(stocked)
    assert any(r["size"] == "XS/S" for r in sized) and any(r["reason"] == "one size" for r in sized)
