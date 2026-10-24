"""Fit Score (outfit_score.py) and POST /ai/fit-score."""
import pytest

from app.ai.outfit_score import score_outfit

TEE = {"category": "top", "color": "black", "pattern": "solid", "formality": 2, "style_tags": ["streetwear"],
       "label": "black tee"}
JEANS = {"category": "bottom", "color": "light wash blue", "formality": 2, "style_tags": ["streetwear"],
         "label": "baggy jeans"}
SNEAKERS = {"category": "shoes", "color": "white", "formality": 2, "label": "white sneakers"}


def check_shape(r):
    assert set(r) == {"score", "verdict", "notes", "breakdown"}
    b = r["breakdown"]
    assert 0 <= b["color"] <= 40 and all(0 <= b[k] <= 20 for k in ("pattern", "formality", "completeness"))
    assert 0 <= r["score"] <= 100 and len(r["verdict"].split()) <= 6
    assert 2 <= len(r["notes"]) <= 4 and all(len(n.split()) <= 12 for n in r["notes"])


def test_clean_neutral_outfit_is_certified():
    r = score_outfit([TEE, JEANS, SNEAKERS])
    check_shape(r)
    assert r["score"] == 96 and r["verdict"] == "Certified fit check"
    assert r["breakdown"] == {"color": 36, "pattern": 20, "formality": 20, "completeness": 20}
    assert "Both pieces lean streetwear." in r["notes"]


def test_one_pop_of_color_names_the_piece():
    hoodie = {**TEE, "color": "mustard yellow", "label": "mustard hoodie"}
    r = score_outfit([hoodie, JEANS, SNEAKERS])
    assert r["breakdown"]["color"] == 40
    assert "Your mustard hoodie is the one pop of color." in r["notes"]


def test_clashing_patterns_and_colors():
    dress = {"category": "dress", "color": "red", "pattern": "floral", "formality": 3, "label": "red floral dress"}
    jacket = {"category": "outerwear", "color": "green", "pattern": "plaid", "formality": 2, "label": "plaid jacket"}
    r = score_outfit([dress, jacket])
    check_shape(r)
    assert r["breakdown"]["pattern"] == 10 and r["breakdown"]["color"] == 26
    assert r["verdict"] == "Patterns are fighting" and "Add shoes to finish it." in r["notes"]


def test_stripes_plus_one_print_is_classic():
    r = score_outfit([{**TEE, "pattern": "striped"}, {**JEANS, "pattern": "floral"}, SNEAKERS])
    assert r["breakdown"]["pattern"] == 14


def test_formality_spread_names_both_pieces():
    blazer = {"category": "outerwear", "color": "navy", "formality": 5, "label": "navy blazer"}
    r = score_outfit([TEE, JEANS, SNEAKERS, {**blazer}])
    assert r["breakdown"]["formality"] == 4 and r["verdict"] == "Mixed dress codes"
    assert any("navy blazer" in n and "black tee" in n for n in r["notes"])


def test_single_item_is_capped():
    r = score_outfit([{"category": "top", "color": "mustard", "pattern": "graphic", "label": "graphic hoodie"}])
    check_shape(r)
    assert r["score"] <= 60 and r["verdict"] == "Great start, finish the look"
    assert "You need a bottom with that top." in r["notes"]


def test_two_multicolor_pieces():
    r = score_outfit([{**TEE, "color": "tie-dye"}, {**JEANS, "color": "rainbow"}, SNEAKERS])
    assert r["breakdown"]["color"] == 12


@pytest.mark.parametrize("bad", [[], None, "x", [None, 3, {}], [{"category": 5, "formality": True}]])
def test_garbage_never_raises(bad):
    r = score_outfit(bad)
    assert set(r) == {"score", "verdict", "notes", "breakdown"} and 0 <= r["score"] <= 100


def test_fit_score_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("closet_items", "ci1", {"id": "ci1", "user_id": "u", "category": "bottom", "color": "light blue",
                                      "label": "baggy jeans", "formality": 2})
    store.put("products", "p1", {"id": "p1", "retailer": "hm", "name": "Loose Fit Hoodie", "brand": "H&M",
                                 "category": "top", "price_usd": 25.0, "colors": ["Mustard yellow"],
                                 "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p",
                                 "label": "mustard hoodie", "formality": 1})
    c = TestClient(app)
    r = c.post("/ai/fit-score", json={"product_ids": ["p1"], "closet_item_ids": ["ci1"], "items": [SNEAKERS]})
    assert r.status_code == 200, r.text
    assert r.json()["breakdown"]["completeness"] == 20
    assert "Your mustard hoodie is the one pop of color." in r.json()["notes"]
    assert c.post("/ai/fit-score", json={"product_ids": ["nope"]}).status_code == 404
    assert c.post("/ai/fit-score", json={}).json()["verdict"] == "Nothing to score yet"
