"""Free-text occasion → season, and season-coherent fits (no shorts under coats)."""
import pytest

from pathlib import Path


def _w():
    from app.ai import warmth  # imported lazily: an import at collection time would pin the store's DATA_DIR
    return warmth


def _season_fix(pieces, season):
    from app.ai.fit_creator import _season_fix as fix
    return fix(pieces, season)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    monkeypatch.setattr(store, "root", Path(tmp_path))
    return TestClient(app)


def _closet(cid, category, color="white", label=None):
    return {"id": cid, "user_id": "u", "image_url": "https://x/c.jpg", "category": category, "color": color,
            "pattern": "solid", "style_tags": ["streetwear"], "formality": 2, "source": "photo",
            "label": label or f"{color} {category}"}


def _put(products=(), closet=()):
    from app.store import store
    store.put("users", "u", {"id": "u", "display_name": "u", "shop_for": "men"})
    for c in closet:
        store.put("closet_items", c["id"], c)


def _ids(fit):
    return {(p["closet_item"] or p["product"])["id"] for p in fit["pieces"]}


# ---- occasion parsing ----

def test_occasion_temperature_wins_over_words():
    assert _w().occasion_season("date night in SF, 55°F, walking a lot") == _w().MID
    assert _w().occasion_season("sunny picnic but 40F") == _w().HEAVY
    assert _w().occasion_season("12°C in the morning") == _w().HEAVY
    assert _w().occasion_season("beach, 85 degrees") == _w().LIGHT


def test_occasion_words():
    assert _w().occasion_season("cold rainy night out") == _w().HEAVY
    assert _w().occasion_season("hot summer bbq") == _w().LIGHT
    assert _w().occasion_season("class") == _w().MID
    assert _w().occasion_season(None) == _w().MID


# ---- coherence rules ----

def _p(cid, cat, label):
    return {"slot": cat, "source": "closet", "closet_item": _closet(cid, cat, label=label), "product": None,
            "label": label, "category": cat}


def test_shorts_under_coat_rejected_in_mid_season():
    pieces = [_p("c1", "outerwear", "camel wool overcoat"), _p("c2", "top", "white tee"),
              _p("c3", "bottom", "denim shorts"), _p("c4", "shoes", "white sneakers")]
    assert not _w().coherent(pieces)
    fixed = _season_fix(pieces, _w().MID)
    assert {p["slot"] for p in fixed} == {"outerwear", "top", "shoes"}  # shorts dropped, coat kept


def test_tee_under_coat_is_fine():
    pieces = [_p("c1", "outerwear", "black trench coat"), _p("c2", "top", "white tee"),
              _p("c3", "bottom", "black trousers")]
    assert _w().coherent(pieces)
    assert _season_fix(pieces, _w().MID) == pieces


def test_cold_occasion_excludes_shorts_and_flags_missing_layer(client):
    _put(products=[], closet=[_closet("c_tee", "top", label="white tee"), _closet("c_shorts", "bottom", label="denim shorts"),
                              _closet("c_pants", "bottom", "black", label="black wool trousers"),
                              _closet("c_shoe", "shoes", label="white sneakers")])
    r = client.post("/fits/create", json={"user_id": "u", "count": 3, "occasion": "freezing walk, 30°F"})
    assert r.status_code == 200, r.text
    for fit in r.json()["fits"]:
        assert "c_shorts" not in _ids(fit)
        assert fit["season"] == "heavy"
        assert "no warm layer in your closet" in fit["missing"]


def test_hot_occasion_excludes_coats(client):
    _put(products=[], closet=[_closet("c_tee", "top", label="white tee"), _closet("c_shorts", "bottom", label="denim shorts"),
                              _closet("c_coat", "outerwear", "camel", label="camel wool overcoat"),
                              _closet("c_shoe", "shoes", label="white sneakers")])
    r = client.post("/fits/create", json={"user_id": "u", "count": 3, "occasion": "hot summer bbq"})
    assert r.status_code == 200, r.text
    fits = r.json()["fits"]
    assert fits
    for fit in fits:
        assert "c_coat" not in _ids(fit)
        assert fit["season"] == "light"


def test_old_enum_occasion_still_accepted(client):
    _put(products=[], closet=[_closet("c_tee", "top", label="white tee"), _closet("c_pants", "bottom", label="black trousers")])
    r = client.post("/fits/create", json={"user_id": "u", "count": 1, "occasion": "class"})
    assert r.status_code == 200, r.text
    assert r.json()["fits"][0]["season"] == "mid"
