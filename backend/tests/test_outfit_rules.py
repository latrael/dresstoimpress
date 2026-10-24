"""Pytest test suite for outfit_rules.py covering all scoring and ranking rules."""

from __future__ import annotations

import pytest
from app.ai.outfit_rules import rank, score_product


def _word_count(text: str) -> int:
    return len(text.strip().split())


def test_empty_closet_scores_from_style_only() -> None:
    """Empty closet returns pairs_with=[], reason='matches your style', and scores on style."""
    product_match = {
        "id": "p1",
        "name": "Baggy Y2K Baby Tee",
        "category": "top",
        "price_usd": 24.99,
        "colors": ["white"],
        "style_tags": ["y2k", "streetwear"],
    }
    product_plain = {
        "id": "p2",
        "name": "Plain Crew Socks",
        "category": "accessory",
        "price_usd": 9.99,
        "colors": ["grey"],
        "style_tags": [],
    }

    res_match = score_product(product_match, closet=[], style_text="baggy y2k")
    res_plain = score_product(product_plain, closet=[], style_text="baggy y2k")

    assert res_match["pairs_with"] == []
    assert res_match["reason"] == "matches your style"
    assert 0.0 <= res_match["score"] <= 1.0
    assert res_match["score"] > res_plain["score"]


def test_complementary_category_and_reason_names_closet_label() -> None:
    """Tops pair with bottoms and the reason names the best closet item's label."""
    closet = [
        {
            "id": "c1",
            "label": "black cargo pants",
            "category": "bottom",
            "color": "black",
            "pattern": "solid",
            "style_tags": ["streetwear", "y2k"],
            "formality": 2,
        }
    ]
    top = {
        "id": "p1",
        "name": "Cropped Ribbed Tank",
        "category": "top",
        "price_usd": 19.90,
        "colors": ["white"],
        "style_tags": ["streetwear", "y2k"],
    }

    res = score_product(top, closet)
    assert res["pairs_with"] == ["c1"]
    assert "black cargo pants" in res["reason"]
    assert res["reason"] == "goes with your black cargo pants"
    assert _word_count(res["reason"]) <= 8
    assert res["score"] >= 0.8


def test_same_category_gets_no_pairing_credit() -> None:
    """A top does not pair with a closet containing only tops."""
    closet_only_tops = [
        {
            "id": "c_top",
            "label": "white linen shirt",
            "category": "top",
            "color": "white",
            "pattern": "solid",
            "style_tags": ["minimalist"],
            "formality": 3,
        }
    ]
    product_top = {
        "id": "p_top",
        "name": "Black Boxy Tee",
        "category": "top",
        "price_usd": 25.0,
        "colors": ["black"],
        "style_tags": ["minimalist"],
    }

    res = score_product(product_top, closet_only_tops)
    assert res["pairs_with"] == []
    assert res["score"] <= 0.35


def test_neutral_color_pairs_higher_than_warm_cool_clash() -> None:
    """Neutral colors (e.g. black, navy, light blue) score higher than warm + cool mixes."""
    closet_neutral = [
        {
            "id": "c_neutral",
            "label": "light blue denim jeans",
            "category": "bottom",
            "color": "light blue",
            "pattern": "solid",
            "style_tags": ["classic"],
            "formality": 2,
        }
    ]
    closet_cool = [
        {
            "id": "c_cool",
            "label": "cobalt blue trousers",
            "category": "bottom",
            "color": "cobalt blue",
            "pattern": "solid",
            "style_tags": ["classic"],
            "formality": 2,
        }
    ]
    warm_top = {
        "id": "p_warm",
        "name": "Mustard Knit Sweater",
        "category": "top",
        "price_usd": 45.0,
        "colors": ["mustard yellow"],
        "style_tags": ["classic"],
    }

    res_neutral = score_product(warm_top, closet_neutral)
    res_warm_cool = score_product(warm_top, closet_cool)

    assert res_neutral["score"] > res_warm_cool["score"]


def test_two_patterns_penalized_vs_solid_pairing() -> None:
    """Pairing two patterned items is penalized compared to one solid + one pattern."""
    closet = [
        {
            "id": "c_plaid",
            "label": "plaid pleated skirt",
            "category": "bottom",
            "color": "grey",
            "pattern": "plaid",
            "style_tags": ["preppy"],
            "formality": 3,
        }
    ]
    solid_top = {
        "id": "p_solid",
        "name": "Fitted Cardigan",
        "category": "top",
        "price_usd": 35.0,
        "colors": ["white"],
        "style_tags": ["preppy"],
    }
    striped_top = {
        "id": "p_striped",
        "name": "Striped Rugby Shirt",
        "category": "top",
        "price_usd": 35.0,
        "colors": ["white"],
        "style_tags": ["preppy"],
    }

    res_solid = score_product(solid_top, closet)
    res_two_patterns = score_product(striped_top, closet)

    assert res_solid["score"] > res_two_patterns["score"]
    assert res_solid["score"] - res_two_patterns["score"] >= 0.25


def test_style_text_boosts_matching_product() -> None:
    """Words in style_text matching product name or style_tags increase the product's score."""
    closet = [
        {
            "id": "c1",
            "label": "black wide leg jeans",
            "category": "bottom",
            "color": "black",
            "pattern": "solid",
            "style_tags": ["classic"],
            "formality": 2,
        }
    ]
    baggy_product = {
        "id": "p_baggy",
        "name": "Baggy Grunge Graphic Hoodie",
        "category": "outerwear",
        "price_usd": 59.0,
        "colors": ["grey"],
        "style_tags": ["grunge", "y2k"],
    }

    score_without_text = score_product(baggy_product, closet, style_text="")["score"]
    score_with_text = score_product(baggy_product, closet, style_text="baggy y2k grunge")["score"]

    assert score_with_text > score_without_text


def test_missing_closet_label_uses_color_and_category_fallback() -> None:
    """If closet item label is missing or empty, fallback '{color} {category}' is used."""
    closet = [
        {
            "id": "c_nolabel",
            "label": "",
            "category": "bottom",
            "color": "olive",
            "pattern": "solid",
            "style_tags": ["minimalist"],
            "formality": 3,
        }
    ]
    top = {
        "id": "p1",
        "name": "Cream Linen Tee",
        "category": "top",
        "price_usd": 29.0,
        "colors": ["cream"],
        "style_tags": ["minimalist"],
    }

    res = score_product(top, closet)
    assert res["pairs_with"] == ["c_nolabel"]
    assert res["reason"] == "goes with your olive bottom"
    assert _word_count(res["reason"]) <= 8


def test_dresses_pair_with_outerwear_and_shoes_not_bottoms() -> None:
    """Dresses pair with outerwear and shoes, but do not pair with bottoms or tops."""
    closet = [
        {
            "id": "c_jeans",
            "label": "blue jeans",
            "category": "bottom",
            "color": "denim",
            "pattern": "solid",
            "style_tags": ["classic"],
            "formality": 2,
        },
        {
            "id": "c_jacket",
            "label": "black leather jacket",
            "category": "outerwear",
            "color": "black",
            "pattern": "solid",
            "style_tags": ["vintage"],
            "formality": 3,
        },
        {
            "id": "c_boots",
            "label": "black ankle boots",
            "category": "shoes",
            "color": "black",
            "pattern": "solid",
            "style_tags": ["vintage"],
            "formality": 3,
        },
    ]
    dress = {
        "id": "p_dress",
        "name": "Slip Midi Dress",
        "category": "dress",
        "price_usd": 68.0,
        "colors": ["burgundy"],
        "style_tags": ["vintage"],
    }

    res = score_product(dress, closet)
    assert "c_jeans" not in res["pairs_with"]
    assert set(res["pairs_with"]) == {"c_jacket", "c_boots"}


def test_shoes_pair_with_anything_and_cap_pairs_with_at_two() -> None:
    """Shoes pair with tops, bottoms, dresses, and outerwear, returning at most 2 closet IDs."""
    closet = [
        {
            "id": "c1",
            "label": "beige trench coat",
            "category": "outerwear",
            "color": "beige",
            "pattern": "solid",
            "style_tags": ["classic", "minimalist"],
            "formality": 4,
        },
        {
            "id": "c2",
            "label": "black tailored trousers",
            "category": "bottom",
            "color": "black",
            "pattern": "solid",
            "style_tags": ["classic", "business"],
            "formality": 4,
        },
        {
            "id": "c3",
            "label": "white button down",
            "category": "top",
            "color": "white",
            "pattern": "solid",
            "style_tags": ["classic"],
            "formality": 4,
        },
    ]
    loafers = {
        "id": "p_shoes",
        "name": "Leather Penny Loafers",
        "category": "shoes",
        "price_usd": 89.0,
        "colors": ["black"],
        "style_tags": ["classic", "business"],
    }

    res = score_product(loafers, closet)
    assert len(res["pairs_with"]) == 2
    assert res["pairs_with"][0] == "c2"  # Shares both classic & business tags


def test_rank_orders_best_first_and_includes_product_id() -> None:
    """rank() returns products sorted by descending score with 'product_id' attached and respects k."""
    closet = [
        {
            "id": "c_cargo",
            "label": "black cargo pants",
            "category": "bottom",
            "color": "black",
            "pattern": "solid",
            "style_tags": ["streetwear", "y2k"],
            "formality": 2,
        }
    ]
    products = [
        {
            "id": "prod_bad_cat",
            "name": "Blue Mom Jeans",
            "category": "bottom",  # Same category -> low score
            "price_usd": 49.90,
            "colors": ["denim"],
            "style_tags": ["streetwear"],
        },
        {
            "id": "prod_best",
            "name": "White Streetwear Baby Tee",
            "category": "top",  # Complementary + neutral + shared tags + style_text hit
            "price_usd": 19.90,
            "colors": ["white"],
            "style_tags": ["streetwear", "y2k"],
        },
        {
            "id": "prod_mid",
            "name": "Floral Boho Blouse",
            "category": "top",  # Complementary, pattern + no shared tags
            "price_usd": 39.90,
            "colors": ["orange"],
            "style_tags": ["boho"],
        },
    ]

    ranked = rank(products, closet, style_text="y2k baby tee", k=2)
    assert len(ranked) == 2
    assert [item["product_id"] for item in ranked] == ["prod_best", "prod_mid"]
    assert ranked[0]["score"] > ranked[1]["score"]
    assert set(ranked[0].keys()) == {"product_id", "score", "pairs_with", "reason"}


def test_reason_always_respects_eight_word_limit() -> None:
    """Even if a closet item has a very long label, reason never exceeds 8 words."""
    closet = [
        {
            "id": "c_long",
            "label": "vintage faded distressed high waisted wide leg blue denim jeans",
            "category": "bottom",
            "color": "denim",
            "pattern": "solid",
            "style_tags": ["vintage"],
            "formality": 2,
        }
    ]
    top = {
        "id": "p1",
        "name": "Vintage White Tee",
        "category": "top",
        "price_usd": 20.0,
        "colors": ["white"],
        "style_tags": ["vintage"],
    }

    res = score_product(top, closet)
    assert _word_count(res["reason"]) <= 8
    assert res["reason"].startswith("goes with your")


@pytest.mark.parametrize(
    "odd_product,odd_closet,odd_text,odd_k",
    [
        ({}, [], "", 5),
        (None, None, None, 10),  # type: ignore[arg-type]
        ({"id": 123, "name": None, "category": "unknown", "colors": None, "style_tags": "not-a-list"}, [None, {}], "y2k", 0),  # type: ignore[list-item]
        ({"id": "p", "category": "top"}, [{"id": "c", "category": "bottom", "formality": "high"}], "   ", -3),
    ],
)
def test_never_crashes_on_malformed_inputs(
    odd_product: dict,
    odd_closet: list[dict],
    odd_text: str,
    odd_k: int,
) -> None:
    """score_product and rank never raise exceptions on malformed or unexpected inputs."""
    res = score_product(odd_product, odd_closet, style_text=odd_text)
    assert isinstance(res, dict)
    assert set(res.keys()) == {"score", "pairs_with", "reason"}
    assert 0.0 <= res["score"] <= 1.0
    assert isinstance(res["pairs_with"], list)
    assert len(res["pairs_with"]) <= 2
    assert _word_count(res["reason"]) <= 8

    ranked = rank([odd_product] if isinstance(odd_product, dict) else [], odd_closet, style_text=odd_text, k=odd_k)
    assert isinstance(ranked, list)
