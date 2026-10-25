"""Tests for complete_look.py (module drafted in Gemini; tests written against its spec)."""
from app.ai.complete_look import complete_look


def closet_item(id_, cat, color="black", label=None, tags=("streetwear",), pattern="solid"):
    return {"id": id_, "label": label or f"{color} {cat}", "category": cat, "color": color,
            "pattern": pattern, "style_tags": list(tags), "formality": 2}


def product(id_, cat, price=30.0, colors=("white",), tags=("streetwear",), in_stock=True, name=None):
    return {"id": id_, "name": name or f"{colors[0]} {cat}", "category": cat, "price_usd": price,
            "colors": list(colors), "style_tags": list(tags), "in_stock": in_stock}


TEE = product("p-tee", "top", 20.0)
JEANS_CLOSET = closet_item("c-jeans", "bottom", "light blue", "baggy jeans")
SNEAKERS_CLOSET = closet_item("c-sneakers", "shoes", "white", "white sneakers")


def cats(result):
    return [i["category"] for i in result["items"]]


def test_closet_preferred_over_catalog():
    catalog = [product("p-jeans", "bottom", 40.0, ("blue",)), product("p-shoes", "shoes", 60.0)]
    r = complete_look(TEE, [JEANS_CLOSET, SNEAKERS_CLOSET], catalog)
    by_cat = {i["category"]: i for i in r["items"]}
    assert by_cat["bottom"]["source"] == "closet" and by_cat["bottom"]["id"] == "c-jeans"
    assert by_cat["shoes"]["source"] == "closet"
    assert r["missing"] == [] and r["anchor_id"] == "p-tee"


def test_new_items_total_includes_anchor_and_catalog_only():
    r = complete_look(TEE, [JEANS_CLOSET], [product("p-shoes", "shoes", 50.0)])
    assert r["new_items_total_usd"] == 70.0  # 20 tee + 50 shoes; closet jeans are free


def test_budget_respected():
    catalog = [product("p-shoes-exp", "shoes", 200.0), product("p-shoes-cheap", "shoes", 25.0)]
    r = complete_look(TEE, [JEANS_CLOSET], catalog, budget_usd=60.0)
    shoe_ids = [i["id"] for i in r["items"] if i["category"] == "shoes"]
    assert shoe_ids == ["p-shoes-cheap"] and r["new_items_total_usd"] <= 60.0


def test_missing_slot_reported_when_nothing_fits_budget():
    r = complete_look(TEE, [JEANS_CLOSET], [product("p-shoes", "shoes", 500.0)], budget_usd=50.0)
    assert "shoes" in r["missing"]


def test_dress_path_needs_only_shoes():
    dress = product("p-dress", "dress", 45.0, ("black",))
    r = complete_look(dress, [SNEAKERS_CLOSET, JEANS_CLOSET], [])
    assert "shoes" in cats(r) and "bottom" not in cats(r) and "top" not in cats(r)
    assert r["missing"] == []


def test_no_duplicate_categories_and_anchor_slot_not_refilled():
    closet = [JEANS_CLOSET, closet_item("c-tee", "top", "grey"), SNEAKERS_CLOSET,
              closet_item("c-jeans2", "bottom", "black", "black cargos")]
    r = complete_look(TEE, closet, [])
    c = cats(r)
    assert len(c) == len(set(c)) and "top" not in c


def test_out_of_stock_catalog_skipped():
    catalog = [product("p-shoes-oos", "shoes", 20.0, in_stock=False), product("p-shoes-ok", "shoes", 30.0)]
    r = complete_look(TEE, [JEANS_CLOSET], catalog)
    assert [i["id"] for i in r["items"] if i["category"] == "shoes"] == ["p-shoes-ok"]


def test_empty_closet_uses_catalog():
    catalog = [product("p-jeans", "bottom", 40.0, ("blue",)), product("p-shoes", "shoes", 50.0)]
    r = complete_look(TEE, [], catalog)
    assert {i["source"] for i in r["items"]} == {"catalog"} and r["missing"] == []


def test_labels_and_reasons():
    r = complete_look(TEE, [JEANS_CLOSET], [product("p-shoes", "shoes", 30.0, name="Retro court sneakers")])
    labels = {i["category"]: i["label"] for i in r["items"]}
    assert labels["bottom"] == "baggy jeans" and labels["shoes"] == "Retro court sneakers"
    assert all(len(i["reason"].split()) <= 8 for i in r["items"])
    assert 0.0 <= r["score"] <= 1.0


def test_deterministic():
    catalog = [product("p-jeans", "bottom", 40.0), product("p-shoes", "shoes", 50.0),
               product("p-jacket", "outerwear", 70.0, ("black",))]
    a = complete_look(TEE, [SNEAKERS_CLOSET], catalog, budget_usd=200, style_text="streetwear")
    b = complete_look(TEE, [SNEAKERS_CLOSET], catalog, budget_usd=200, style_text="streetwear")
    assert a == b


def test_odd_input_does_not_crash():
    for anchor, closet, catalog in [({}, [], []), (None, None, None), (TEE, [None, {}], [None, {"id": 1}])]:
        r = complete_look(anchor, closet, catalog)  # type: ignore[arg-type]
        assert set(r) >= {"anchor_id", "items", "new_items_total_usd", "missing", "score"}



# ---- Fit Score v2 rubric in complete-the-look (Adam, Oct 24: "it paired an athletic shirt with a leather belt")

from app.ai.complete_look import anchor_primary_style, clashes_with  # noqa: E402

ATHLETIC_TEE = {**product("p-ath-tee", "top", 25.0, ("black",), ("athleisure",), name="Dri-fit athletic training shirt"),
                "formality": 1, "label": "black athletic training shirt"}
LEATHER_BELT = {**product("p-belt", "accessory", 45.0, ("brown",), ("classic", "business"), name="Leather belt"),
                "formality": 4, "label": "brown leather belt"}
CAP = {**product("p-cap", "accessory", 20.0, ("black",), ("athleisure", "streetwear"), name="Black cap"),
       "formality": 1, "label": "black cap"}
JOGGERS = {**product("p-joggers", "bottom", 40.0, ("grey",), ("athleisure",), name="Fleece joggers"), "formality": 1}
TRAINERS = {**product("p-trainers", "shoes", 80.0, ("white",), ("athleisure",), name="Running trainers"), "formality": 1}
DRESS_SHIRT = {**product("p-dress-shirt", "top", 60.0, ("white",), ("business", "classic"), name="White dress shirt"),
               "formality": 4}
TROUSERS = {**product("p-trousers", "bottom", 70.0, ("navy",), ("business", "classic"), name="Navy tailored trousers"),
            "formality": 4}
LOAFERS = {**product("p-loafers", "shoes", 120.0, ("brown",), ("business", "classic"), name="Leather loafers"),
           "formality": 4}


def test_athletic_tee_anchor_never_gets_a_leather_belt():
    catalog = [LEATHER_BELT, CAP, JOGGERS, TRAINERS, TROUSERS, LOAFERS, DRESS_SHIRT]
    r = complete_look(ATHLETIC_TEE, [], catalog)
    ids = [i["id"] for i in r["items"]]
    assert "p-belt" not in ids and "p-loafers" not in ids and "p-trousers" not in ids
    assert set(cats(r)) >= {"bottom", "shoes"} and r["missing"] == []
    assert r["primary_style"] == "athleisure"
    fs = r["fit_score"]
    assert fs and set(fs) >= {"score", "verdict", "criteria", "style_scores", "primary_style"}
    assert fs["primary_style"] == "athleisure" and fs["verdict"].startswith(f"{fs['score']} as athleisure")


def test_leather_belt_anchor_never_gets_an_athletic_shirt():
    catalog = [ATHLETIC_TEE, DRESS_SHIRT, JOGGERS, TROUSERS, TRAINERS, LOAFERS]
    r = complete_look(LEATHER_BELT, [], catalog)
    ids = [i["id"] for i in r["items"]]
    assert "p-ath-tee" not in ids and "p-joggers" not in ids and "p-trainers" not in ids
    assert {"top", "bottom", "shoes"} <= set(cats(r))
    assert r["primary_style"] in ("business", "classic")


def test_clash_guard_words_and_tags():
    assert clashes_with(ATHLETIC_TEE, LEATHER_BELT) and clashes_with(LEATHER_BELT, ATHLETIC_TEE)
    assert clashes_with({"label": "grey joggers", "style_tags": [], "formality": 3},
                        {"label": "navy blazer", "style_tags": [], "formality": 3})
    assert clashes_with({"label": "white tee", "style_tags": [], "formality": 1},
                        {"label": "black heels", "style_tags": [], "formality": 5})  # three steps apart
    assert not clashes_with(ATHLETIC_TEE, CAP) and not clashes_with(ATHLETIC_TEE, JOGGERS)
    assert not clashes_with({"label": "tie-dye hoodie", "style_tags": ["streetwear"], "formality": 1}, JOGGERS)
    assert not clashes_with(TEE, JEANS_CLOSET)


def test_candidates_prefer_the_anchor_primary_style():
    assert anchor_primary_style({**ATHLETIC_TEE, "color": "black"}) == "athleisure"
    assert anchor_primary_style({"label": "x", "category": "top", "style_tags": []}) is None
    street_jeans = product("p-street", "bottom", 40.0, ("black",), ("streetwear",), name="Baggy black jeans")
    preppy_chinos = product("p-chinos", "bottom", 40.0, ("black",), ("preppy", "classic"), name="Black chinos")
    anchor = {**product("p-hoodie", "top", 50.0, ("grey",), ("streetwear",), name="Oversized grey hoodie"), "formality": 1}
    r = complete_look(anchor, [], [preppy_chinos, street_jeans, product("p-snk", "shoes", 60.0)])
    assert [i["id"] for i in r["items"] if i["category"] == "bottom"] == ["p-street"]
    assert r["primary_style"] == "streetwear" and 0 <= r["fit_score"]["score"] <= 100
