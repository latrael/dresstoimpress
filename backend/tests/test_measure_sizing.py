"""Sizing from real measurements (chest / hip / waist / inseam / usual size) instead of just height+weight,
and that /feed's your_size reflects them."""
import os
from pathlib import Path

import pytest

from app.ai.sizing import recommend_size

os.environ["MOCK_AI"] = "1"

LETTERS = ["XS", "S", "M", "L", "XL", "XXL"]
HW = dict(height_cm=178.0, weight_kg=70.0)   # BMI 22.1 -> M on the estimate path


def _p(category="top", sizes=LETTERS, department=None, retailer="hm"):
    p = {"id": "p", "category": category, "retailer": retailer, "sizes": list(sizes)}
    if department:
        p["department"] = department
    return p


# ---- chest -> letter ----

@pytest.mark.parametrize("chest,size", [(33, "XS"), (35, "S"), (36, "S"), (39, "M"), (43, "L"), (47, "XL"), (52, "XXL")])
def test_mens_chest_chart(chest, size):
    out = recommend_size(_p(department="men"), **HW, chest_in=chest)
    assert out["size"] == size and out["confidence"] == "high"
    assert out["reason"] == f"chest {chest} in → {size}"


@pytest.mark.parametrize("bust,size", [(31, "XS"), (33, "S"), (36, "M"), (39, "L"), (42, "XL"), (45, "XXL")])
def test_womens_bust_chart(bust, size):
    assert recommend_size(_p(department="women"), **HW, chest_in=bust)["size"] == size


def test_unknown_department_uses_mens_chart_and_outerwear_too():
    assert recommend_size(_p(), **HW, chest_in=36)["size"] == "S"             # men's: 36 is S; women's would be M
    assert recommend_size(_p("outerwear"), **HW, chest_in=43)["size"] == "L"


def test_fit_shifts_one_size_clamped():
    assert recommend_size(_p(), **HW, chest_in=39, fit="slim")["size"] == "S"
    out = recommend_size(_p(), **HW, chest_in=39, fit="oversized")
    assert out["size"] == "L" and out["reason"] == "chest 39 in, oversized fit → L"
    assert recommend_size(_p(), **HW, chest_in=52, fit="oversized")["size"] == "XXL"
    assert recommend_size(_p(), **HW, chest_in=30, fit="slim")["size"] == "XS"


def test_nearest_in_stock_letter_lowers_confidence():
    out = recommend_size(_p(sizes=["M", "L"]), **HW, chest_in=36)   # S out of stock -> M, one size off
    assert out["size"] == "M" and out["confidence"] == "medium"
    assert recommend_size(_p(sizes=["XL", "XXL"]), **HW, chest_in=33)["confidence"] == "low"


# ---- hip / waist -> letter (dresses, letter-sized bottoms) ----

def test_dress_uses_hip_then_chest_then_waist():
    dress = _p("dress", department="women")
    out = recommend_size(dress, **HW, hip_in=38, chest_in=33)
    assert out["size"] == "M" and out["reason"] == "hip 38 in → M" and out["confidence"] == "high"
    assert recommend_size(dress, **HW, chest_in=33)["size"] == "S"
    out = recommend_size(dress, **HW, waist_in=29)
    assert out["size"] == "M" and out["confidence"] == "medium"   # waist is an inference for letter sizes


def test_letter_bottoms_hip_for_women_waist_for_men():
    assert recommend_size(_p("bottom", department="women"), **HW, hip_in=41, waist_in=29)["size"] == "L"
    out = recommend_size(_p("bottom", department="men"), **HW, waist_in=33, hip_in=41)
    assert out["size"] == "M" and out["reason"] == "waist 33 in → M"


# ---- waist / inseam bottoms ----

def test_waist_and_inseam_exact():
    jeans = _p("bottom", sizes=["28/30", "28/32", "30/30", "30/32", "32/30", "32/32"])
    out = recommend_size(jeans, **HW, waist_in=30.5, inseam_in=30.5)
    assert out == {"size": "30/30", "confidence": "high", "reason": "waist 30.5 in, inseam 30.5 in → 30/30"}
    # inseam given beats the height estimate (178 cm would estimate ~31.5 -> /32)
    assert recommend_size(jeans, height_cm=178, weight_kg=70, waist_in=32, inseam_in=29)["size"] == "32/30"
    assert recommend_size(jeans, height_cm=160, weight_kg=70, waist_in=32, inseam_in=33)["size"] == "32/32"
    assert recommend_size(jeans, **HW, waist_in=32)["size"] == "32/32"   # no inseam: height estimate as before
    w = recommend_size(_p("bottom", sizes=["30", "32", "34"]), **HW, waist_in=31.8)
    assert w["size"] == "32" and w["reason"] == "waist 31.8 in → 32" and w["confidence"] == "high"


# ---- hip -> women's numeric ----

@pytest.mark.parametrize("hip,size", [(34, "0"), (35, "4"), (37, "6"), (38, "8"), (39.5, "10"), (41, "12"),
                                      (43, "14"), (45, "16"), (49, "20"), (53, "24")])
def test_hip_to_womens_numeric(hip, size):
    womens = _p("bottom", sizes=[str(n) for n in range(0, 26, 2)])
    out = recommend_size(womens, **HW, hip_in=hip, waist_in=40)   # hip wins over waist
    assert out["size"] == size and out["reason"] == f"hip {hip:g} in → size {size}"


def test_womens_numeric_falls_back_to_waist_then_estimate():
    womens = _p("bottom", sizes=["0", "2", "4", "6", "8", "10", "12"])
    out = recommend_size(womens, **HW, waist_in=27.5)
    assert out["size"] == "6" and out["confidence"] == "medium" and out["reason"] == "waist 27.5 in → size 6"
    assert recommend_size(womens, height_cm=165, weight_kg=60)["confidence"] == "low"


# ---- usual size ----

def test_usual_size_within_one_wins():
    out = recommend_size(_p(), **HW, chest_in=39, usual_size="M")
    assert out["size"] == "M" and out["reason"] == "your usual M matches your measurements"
    out = recommend_size(_p(), **HW, chest_in=39, usual_size="L")                 # one size off: usual wins
    assert out["size"] == "L" and out["reason"] == "your usual L matches your measurements"
    jeans = _p("bottom", sizes=["30/30", "30/32", "32/30", "32/32"])
    assert recommend_size(jeans, **HW, waist_in=30.5, inseam_in=30.5, usual_size="30/32")["size"] == "30/32"


def test_usual_size_two_off_keeps_measurement():
    out = recommend_size(_p(), **HW, chest_in=43, usual_size="S")
    assert out["size"] == "L" and out["confidence"] == "high"
    assert out["reason"] == "chest 43 in → L (usual S)"
    out = recommend_size(_p(sizes=["XS", "S", "L"]), **HW, chest_in=39, usual_size="M")   # usual sold out
    assert out["size"] == "L" and "usual M" in out["reason"]


# ---- BMI fallback untouched ----

def test_bmi_fallback_when_no_measurement():
    out = recommend_size(_p(), **HW)
    assert out["size"] == "M" and out["confidence"] == "high" and out["reason"].startswith("BMI/height estimate")
    assert recommend_size(_p(retailer="zara"), **HW)["size"] == "L"
    assert recommend_size(_p(), **HW, chest_in=0)["size"] == "M"              # junk measurement -> estimate
    assert recommend_size(_p("shoes", sizes=["9", "9.5", "10"]), **HW, shoe_us=9.5, chest_in=40)["size"] == "9.5"


# ---- /size and /feed ----

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        monkeypatch.setattr(store, "root", Path(tmp_path))
    return TestClient(app)


PROFILE = {"height_cm": 178, "weight_kg": 70, "chest_in": 36, "waist_in": 30.5, "hip_in": 37, "inseam_in": 30.5}


def _mk(pid, category="top", sizes=("M", "L"), department=None):
    p = {"id": pid, "retailer": "hm", "name": pid, "brand": "hm", "category": category, "price_usd": 20.0,
         "colors": [], "style_tags": [], "sizes": [{"name": s, "in_stock": True} for s in sizes],
         "in_stock": True, "image_url": "https://x/y.jpg", "product_url": "https://x", "source": "seed"}
    if department:
        p["department"] = department
    return p


def test_feed_your_size_from_measurements(client, monkeypatch):
    from app.commerce import router
    from app.models import PairResult
    from app.store import store
    store.put("users", "u", {"id": "u", "display_name": "u", "body_profile": PROFILE})
    store.put("products", "t", _mk("t"))
    store.put("products", "j", _mk("j", "bottom", ("30/30", "30/32", "32/32")))
    monkeypatch.setattr(router, "pair", lambda uid, cands, k: [
        PairResult(product_id=pid, score=0.9, reason="why") for pid in ("t", "j") if pid in cands])
    by = {c["id"]: c for c in client.get("/feed", params={"user_id": "u"}).json()}
    assert by["t"]["your_size"] == "M" and by["t"]["in_your_size"] is True
    assert by["j"]["your_size"] == "30/30"


def test_size_route_uses_profile_and_request_overrides(client):
    from app.store import store
    store.put("users", "u", {"id": "u", "display_name": "u",
                             "body_profile": {**PROFILE, "usual_sizes": {"top": "M"}}})
    store.put("products", "t", _mk("t", sizes=LETTERS))
    out = client.post("/size", json={"product_id": "t", "user_id": "u"}).json()
    assert out["size"] == "M" and out["reason"] == "your usual M matches your measurements"
    out = client.post("/size", json={"product_id": "t", "user_id": "u", "chest_in": 47}).json()
    assert out["size"] == "XL" and out["reason"] == "chest 47 in → XL (usual M)"
