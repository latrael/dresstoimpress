"""Digitize v3 post-checks: label/category agree, no brand without visible evidence, occluded layers kept."""
def test_category_follows_the_label_noun():
    from app.ai.digitize import validate_detection

    d = validate_detection({"label": "grey crewneck sweater", "category": "outerwear", "color": "grey"})
    assert d["category"] == "top"
    d = validate_detection({"label": "black over-ear headphones", "category": "top", "color": "black"})
    assert d["category"] == "accessory"
    d = validate_detection({"label": "navy cardigan", "category": "top", "color": "navy"})
    assert d["category"] == "top"  # a layer: either is fine


def test_brand_needs_evidence():
    from app.ai.digitize import validate_detection

    d = validate_detection({"label": "white tee", "category": "top", "color": "white", "brand": "uniqlo",
                            "brand_evidence": None})
    assert d["brand"] is None and d["brand_evidence"] is None
    d = validate_detection({"label": "black hoodie", "category": "top", "color": "black", "brand": "nike",
                            "brand_evidence": "swoosh on chest"})
    assert d["brand"] == "nike"
    assert validate_detection({"label": "tee", "category": "top", "color": "x", "brand": "unknown",
                               "brand_evidence": "none"})["brand"] is None


def test_occluded_kept_and_empty_rejected():
    from app.ai.digitize import validate_detection

    d = validate_detection({"label": "white shirt", "category": "top", "color": "white", "occluded": True})
    assert d["occluded"] is True
    assert validate_detection({"label": "", "category": "top"}) is None
    assert validate_detection("nope") is None
    assert validate_detection({"label": "keys on belt loop", "category": "accessory", "color": "silver"}) is None


def test_prompt_and_schema_ask_for_layers_accessories_and_evidence():
    from app.ai import prompts

    assert prompts.DIGITIZE_VERSION == "v3"
    assert "occluded" in prompts.DIGITIZE and "headphones" in prompts.DIGITIZE and "brand_evidence" in prompts.DIGITIZE
    props = prompts.SCHEMAS["digitize"]["items"]["properties"]
    assert "occluded" in props and "brand_evidence" in props


def test_catalog_match_never_sets_brand(monkeypatch):
    from app.ai import closet
    from app.models import ClosetItem

    item = ClosetItem(id="ci_1", user_id="u", image_url="x", category="top", color="black", label="black tee")
    monkeypatch.setattr(closet, "catalog_match", lambda d: ({"id": "p1", "brand": "H&M", "image_url": "y"}, 0.9))
    closet._apply_match(item)
    assert item.product_id == "p1" and item.brand is None


def test_closet_brand_dropped_without_evidence():
    from app.ai import closet

    assert closet._brand({"brand": "zara", "brand_evidence": ""}) is None
    assert closet._brand({"brand": "zara", "brand_evidence": "tag text"}) == "zara"
    assert closet._brand({"brand": "zara"}) == "zara"  # single-piece tagger has no evidence field
