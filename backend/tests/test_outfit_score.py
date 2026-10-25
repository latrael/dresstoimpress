"""Fit Score v2 (outfit_score.py) and POST /ai/fit-score."""
import pytest

from app.ai import outfit_score
from app.ai.outfit_score import CRITERIA, STYLES, calibrate, score_outfit

TEE = {"category": "top", "color": "black", "pattern": "solid", "formality": 2, "style_tags": ["streetwear"],
       "label": "black tee"}
JEANS = {"category": "bottom", "color": "light wash blue", "formality": 2, "style_tags": ["streetwear"],
         "label": "baggy jeans"}
SNEAKERS = {"category": "shoes", "color": "white", "formality": 2, "label": "white sneakers"}
HOODIE = {"category": "top", "color": "mustard yellow", "formality": 2, "style_tags": ["streetwear"],
          "label": "oversized mustard hoodie"}
SLIM_CARGO = {"category": "bottom", "color": "black", "formality": 2, "style_tags": ["streetwear"],
              "label": "slim black cargo pants"}
CAP = {"category": "accessory", "color": "black", "formality": 2, "style_tags": ["streetwear"], "label": "black cap"}
V1_KEYS = {"score", "verdict", "notes", "breakdown"}
V2_KEYS = V1_KEYS | {"criteria", "style_scores", "primary_style", "raw_score", "source"}


def check_shape(r):
    assert set(r) == V2_KEYS
    b = r["breakdown"]
    assert 0 <= b["color"] <= 40 and all(0 <= b[k] <= 20 for k in ("pattern", "formality", "completeness"))
    assert 0 <= r["score"] <= 100 and 2 <= len(r["notes"]) <= 4
    assert all(len(n.split()) <= 12 for n in r["notes"])
    for c in r["criteria"]:
        assert c["name"] in CRITERIA and 0 <= c["score_10"] <= 10 and (c["note"] is None or isinstance(c["note"], str))
    assert set(r["style_scores"]) == set(STYLES) and all(0 <= v <= 100 for v in r["style_scores"].values())
    assert r["primary_style"] in STYLES
    assert r["verdict"].startswith(f"{r['score']} as {r['primary_style']}:")


def crit(r):
    return {c["name"]: c["score_10"] for c in r["criteria"]}


def test_plain_everyday_outfit_is_solid_not_certified():
    r = score_outfit([TEE, JEANS, SNEAKERS])
    check_shape(r)
    assert 80 <= r["score"] <= 89, r  # v1 gave this 96
    assert r["primary_style"] == "streetwear" and r["source"] == "rules"
    assert crit(r)["completeness"] == 9 and crit(r)["style"] == 9 and crit(r)["color"] == 7
    assert "Your pieces all lean streetwear." in r["notes"]
    # v1 keys still scale the same way for the app: color/40, others /20
    assert r["breakdown"] == {"color": 28, "pattern": 14, "formality": 18, "completeness": 18}


def test_considered_streetwear_outfit_scores_high_but_90_needs_every_criterion():
    r = score_outfit([HOODIE, SLIM_CARGO, {**SNEAKERS, "style_tags": ["streetwear"]}, CAP])
    check_shape(r)
    assert 84 <= r["score"] <= 89 and r["raw_score"] >= 90  # pattern 7/10 (all solid) keeps it under 90
    c = crit(r)
    assert c["color"] == 10 and c["silhouette"] == 9 and c["layering"] == 8
    assert "Your oversized mustard hoodie is the one pop of color." in r["notes"]
    assert r["style_scores"]["streetwear"] > r["style_scores"]["business"] + 40


def test_certified_only_when_every_criterion_is_8_plus():
    graphic = {**HOODIE, "pattern": "graphic", "label": "oversized graphic hoodie"}
    r = score_outfit([graphic, SLIM_CARGO, {**SNEAKERS, "style_tags": ["streetwear"]}, CAP])
    assert all(v >= 8 for v in crit(r).values()), crit(r)
    assert r["score"] >= 90 and r["verdict"].endswith("certified fit check")


def test_target_style_changes_the_headline():
    street = score_outfit([TEE, JEANS, SNEAKERS])
    minimal = score_outfit([TEE, JEANS, SNEAKERS], target_style="minimalist")
    assert minimal["primary_style"] == "minimalist" and minimal["score"] < street["score"]
    assert minimal["verdict"].startswith(f"{minimal['score']} as minimalist:")
    assert score_outfit([TEE, JEANS, SNEAKERS], target_style="not-a-style")["primary_style"] == "streetwear"


def test_occasion_criterion():
    r = score_outfit([TEE, JEANS, SNEAKERS], occasion="job interview")
    c = crit(r)
    assert c["occasion"] == 3 and "Too casual for job interview." in r["notes"]
    assert r["score"] < score_outfit([TEE, JEANS, SNEAKERS])["score"]
    assert crit(score_outfit([TEE, JEANS, SNEAKERS], occasion="class"))["occasion"] == 9
    assert "occasion" not in crit(score_outfit([TEE, JEANS, SNEAKERS]))


def test_clashing_patterns_and_colors():
    dress = {"category": "dress", "color": "red", "pattern": "floral", "formality": 3, "label": "red floral dress"}
    jacket = {"category": "outerwear", "color": "green", "pattern": "plaid", "formality": 2, "label": "plaid jacket"}
    r = score_outfit([dress, jacket])
    check_shape(r)
    c = crit(r)
    assert c["pattern"] == 4 and c["color"] == 5 and c["completeness"] == 5
    assert r["score"] < 60 and "add shoes" in r["verdict"] and "Add shoes to finish it." in r["notes"]


def test_stripes_plus_one_print_is_classic():
    r = score_outfit([{**TEE, "pattern": "striped"}, {**JEANS, "pattern": "floral"}, SNEAKERS])
    assert crit(r)["pattern"] == 7


def test_formality_clash_names_both_pieces_and_tanks_the_score():
    blazer = {"category": "outerwear", "color": "navy", "formality": 5, "label": "navy blazer"}
    r = score_outfit([TEE, JEANS, SNEAKERS, blazer])
    assert crit(r)["formality"] == 2 and "mixed dress codes" in r["verdict"] and r["score"] < 65
    assert r["score"] + 20 <= score_outfit([TEE, JEANS, SNEAKERS])["score"]
    assert any("navy blazer" in n and "black tee" in n for n in r["notes"])


def test_single_item_is_capped():
    r = score_outfit([{"category": "top", "color": "mustard", "pattern": "graphic", "label": "graphic hoodie"}])
    check_shape(r)
    assert r["score"] <= outfit_score.NO_BASE_SCORE_CAP and "not a full outfit" in r["verdict"]
    assert "You need a bottom with that top." in r["notes"]


def test_mixing_three_style_families_is_a_costume():
    items = [{**TEE, "style_tags": ["streetwear"]}, {**JEANS, "style_tags": ["business"]},
             {**SNEAKERS, "style_tags": ["boho"]}]
    assert crit(score_outfit(items))["style"] <= 3


def test_two_multicolor_pieces():
    r = score_outfit([{**TEE, "color": "tie-dye"}, {**JEANS, "color": "rainbow"}, SNEAKERS])
    assert crit(r)["color"] == 1 and r["breakdown"]["color"] == 4


def test_style_scores_follow_the_profiles():
    minimal = [{"category": "top", "color": "white", "formality": 3, "style_tags": ["minimalist"], "label": "plain white tee"},
               {"category": "bottom", "color": "black", "formality": 3, "style_tags": ["minimalist"], "label": "slim black trousers"},
               {"category": "shoes", "color": "white", "formality": 3, "style_tags": ["minimalist"], "label": "white leather sneakers"}]
    r = score_outfit(minimal)
    assert r["primary_style"] == "minimalist" and r["style_scores"]["minimalist"] >= 85
    assert r["style_scores"]["y2k"] < 40 and r["style_scores"]["streetwear"] < r["style_scores"]["minimalist"]


def test_calibration_curve_is_monotone_and_anchored():
    xs = list(range(0, 101))
    ys = [calibrate(x) for x in xs]
    assert ys == sorted(ys) and ys[0] == 0 and ys[-1] == 100
    assert 65 <= calibrate(68) <= 70 and calibrate(80) >= 75


@pytest.mark.parametrize("bad", [[], None, "x", [None, 3, {}], [{"category": 5, "formality": True}]])
def test_garbage_never_raises(bad):
    r = score_outfit(bad)
    assert set(r) == V2_KEYS and 0 <= r["score"] <= 100


def test_photo_critic_blends_and_caches(tmp_path, monkeypatch):
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr("app.ai.llm.text_mock", lambda: False)
    calls = []

    def fake_ai_json(prompt, image_url=None, max_tokens=0, **_):
        calls.append(image_url)
        assert "strict fashion stylist" in prompt and image_url == "https://x/p.jpg"
        return {"criteria": {"color": {"score": 3, "note": "Your jeans fight the tee."}, "silhouette": {"score": 9},
                             "pattern": 7, "formality": {"score": 9}, "style": {"score": 9, "note": "x"},
                             "completeness": {"score": 9}, "layering": {"score": 5}}, "style": "grunge"}

    monkeypatch.setattr("app.ai.llm.ai_json", fake_ai_json)
    rules = score_outfit([TEE, JEANS, SNEAKERS])
    r = score_outfit([TEE, JEANS, SNEAKERS], photo_url="https://x/p.jpg")
    assert r["source"] == "rules+ai" and len(calls) == 1
    c = crit(r)
    assert c["color"] == 5 and c["silhouette"] == 8  # (7+3)/2, (6+9)/2 rounded
    assert "Your jeans fight the tee." in r["notes"]
    assert r["style_scores"]["grunge"] == rules["style_scores"]["grunge"] + 10
    r2 = score_outfit([TEE, JEANS, SNEAKERS], photo_url="https://x/p.jpg")
    assert r2 == r and len(calls) == 1  # cached by photo url + FIT_CRITIC_VERSION
    assert score_outfit([TEE, JEANS, SNEAKERS], photo_url="https://x/p.jpg", use_ai=False)["source"] == "rules"


def test_photo_critic_failure_falls_back_to_rules(tmp_path, monkeypatch):
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr("app.ai.llm.text_mock", lambda: False)
    monkeypatch.setattr("app.ai.llm.ai_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    r = score_outfit([TEE, JEANS, SNEAKERS], photo_url="https://x/p.jpg")
    assert r["source"] == "rules" and r == score_outfit([TEE, JEANS, SNEAKERS])
    monkeypatch.setattr("app.ai.llm.ai_json", lambda *a, **k: {"criteria": {"color": 9}})  # too little to trust
    assert score_outfit([TEE, JEANS, SNEAKERS], photo_url="https://x/q.jpg")["source"] == "rules"


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
                                 "label": "mustard hoodie", "formality": 1, "style_tags": ["streetwear"]})
    c = TestClient(app)
    r = c.post("/ai/fit-score", json={"product_ids": ["p1"], "closet_item_ids": ["ci1"], "items": [SNEAKERS]})
    assert r.status_code == 200, r.text
    body = r.json()
    check_shape(body)
    assert body["breakdown"]["completeness"] == 18 and body["source"] == "rules"
    assert "Your mustard hoodie is the one pop of color." in body["notes"]
    r2 = c.post("/ai/fit-score", json={"product_ids": ["p1"], "closet_item_ids": ["ci1"], "items": [SNEAKERS],
                                       "target_style": "y2k", "occasion": "class", "photo_url": "https://x/p.jpg"})
    assert r2.status_code == 200 and r2.json()["primary_style"] == "y2k"
    assert any(cr["name"] == "occasion" for cr in r2.json()["criteria"]) and r2.json()["source"] == "rules"  # MOCK_AI
    assert c.post("/ai/fit-score", json={"product_ids": ["nope"]}).status_code == 404
    assert c.post("/ai/fit-score", json={}).json()["verdict"] == "Nothing to score yet"


def test_missing_metadata_is_not_a_style_mismatch():
    items = [
        {"category": "top", "label": "white tee", "color": "white"},
        {"category": "bottom", "label": "jeans", "color": "blue"},
        {"category": "shoes", "label": "sneakers", "color": "white"},
    ]
    r = score_outfit(items, use_ai=False)
    assert 70 <= r["score"] <= 89, r
    c = crit(r)
    assert c["style"] >= 7 and c["formality"] >= 7 and c["silhouette"] >= 7
    assert c["layering"] == 7
    assert "shapeless" not in r["verdict"] and "finishing piece" not in r["verdict"]


def test_matching_volumes_are_valid_style_choices():
    for volume in ("slim", "oversized"):
        items = [{**TEE, "label": f"{volume} tee"},
                 {**JEANS, "label": f"{volume} jeans"}, SNEAKERS]
        r = score_outfit(items, use_ai=False)
        assert crit(r)["silhouette"] >= 7
        assert r["score"] >= 80


def test_photo_critic_does_not_require_layers_or_volume_contrast():
    from app.ai import prompts
    assert "A jacket or accessories are optional" in prompts.FIT_CRITIC
    assert "can both work" in prompts.FIT_CRITIC
    assert prompts.FIT_CRITIC_VERSION != "v1"
