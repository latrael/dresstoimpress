"""Fit Score v2 calibration: a small, deterministic version of scripts/score_calibration.py.

Targets: everyday-friendly scores, curated above random, no automatic 90+ badges.
"""
import pytest

from scripts import score_calibration as cal


@pytest.fixture(scope="module")
def catalog():
    if not cal.SEED_PRODUCTS.exists():
        pytest.skip("seed/products.json missing")
    return cal.load_catalog()


def test_random_vs_curated_distribution(catalog):
    res = cal.run(n_random=120, n_curated=20, seed=7, catalog=catalog)
    r, c = res["random"], res["curated"]
    assert 60 <= r["p50"] <= 75, r
    assert r["pct_80"] < 35 and r["pct_90"] < 3, r
    assert 78 <= c["p50"] <= 89, c
    assert c["p50"] >= r["p50"] + 10 and c["mean"] > r["mean"] + 10


def test_other_seed_still_meets_targets(catalog):
    res = cal.run(n_random=120, n_curated=20, seed=2026, catalog=catalog)
    assert cal.meets_targets(res) == []
    assert res["random"]["pct_90"] < 3 and res["random"]["pct_80"] < 35
    assert 78 <= res["curated"]["p50"] <= 89


def test_builders_are_deterministic(catalog):
    a = cal.run(n_random=20, n_curated=5, seed=1, catalog=catalog)
    b = cal.run(n_random=20, n_curated=5, seed=1, catalog=catalog)
    assert a["random"] == b["random"] and a["curated"] == b["curated"]
    import random

    outfit = cal.curated_outfit(random.Random(3), catalog, "streetwear")
    assert {it["category"] for it in outfit} >= {"top", "bottom", "shoes"}
    assert cal._accents(outfit) <= 1
