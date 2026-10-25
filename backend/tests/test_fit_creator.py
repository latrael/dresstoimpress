"""AI Fit Creator: POST /fits/create (AI + rules), GET /fits/{id}, POST /fits/{id}/try-on, POST /fits/{id}/cart."""
import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

ALL = {"S": True, "M": True, "L": True}
BP = {"height_cm": 178.0, "weight_kg": 70.0, "build": "slim", "waist_in": 30.5, "shoe_us": 10, "fit": "regular"}


def _mk(pid, category="top", name=None, sizes=ALL, colors=("black",), tags=("streetwear",), price=20.0, **extra):
    return {"id": pid, "retailer": "hm", "name": name or pid, "brand": "H&M", "category": category,
            "price_usd": price, "colors": list(colors), "style_tags": list(tags),
            "sizes": [{"name": s, "in_stock": ok} for s, ok in sizes.items()], "in_stock": True,
            "image_url": "https://x/y.jpg", "product_url": "https://x", "source": "seed", **extra}


def _closet(cid, category, color="white", label=None):
    return {"id": cid, "user_id": "u", "image_url": "https://x/c.jpg", "category": category, "color": color,
            "pattern": "solid", "style_tags": ["streetwear"], "formality": 2, "source": "photo",
            "label": label or f"{color} {category}"}


CATALOG = [_mk("p_top", "top", "Boxy Tee"), _mk("p_bot", "bottom", "Tapered Jeans", sizes={"30": True, "32": True}),
           _mk("p_shoe", "shoes", "Court Sneaker", sizes={"10": True, "11": True}),
           _mk("p_jacket", "outerwear", "Bomber", price=60.0), _mk("p_dress", "dress", "Slip Dress", colors=("red",)),
           _mk("p_women", "top", "Crop Top", department="women"),
           _mk("p_out", "top", "Sold Out Tee", sizes={"M": False}, in_stock=False)]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    monkeypatch.setattr(store, "root", Path(tmp_path))
    return TestClient(app)


def _put(user=None, products=CATALOG, closet=()):
    from app.store import store
    store.put("users", "u", {"id": "u", "display_name": "u", "shop_for": "men", **(user or {})})
    for p in products:
        store.put("products", p["id"], p)
    for c in closet:
        store.put("closet_items", c["id"], c)


def _ids(fit):
    return {(p["closet_item"] or p["product"])["id"] for p in fit["pieces"]}


def _slots(fit):
    return {p["slot"] for p in fit["pieces"]}


def _complete(fit):
    s = _slots(fit)
    return "shoes" in s and ("dress" in s or {"top", "bottom"} <= s)


def _ai(monkeypatch, reply):
    """Turn the AI path on with a canned Claude reply."""
    from app.ai import fit_creator
    calls = []
    monkeypatch.setattr(fit_creator, "text_mock", lambda: False)

    def fake(prompt, **kw):
        calls.append(prompt)
        return reply(prompt) if callable(reply) else reply
    monkeypatch.setattr(fit_creator, "ai_json", fake)
    return calls


# ---------- rules (mock AI): closet only ----------

FULL_CLOSET = [_closet("c_top", "top", "white", "white tee"), _closet("c_top2", "top", "black", "black polo"),
               _closet("c_bot", "bottom", "navy", "navy chinos"), _closet("c_bot2", "bottom", "grey", "grey jeans"),
               _closet("c_shoe", "shoes", "black", "black loafers"), _closet("c_bag", "accessory", "brown", "brown leather bag")]


def test_rules_fits_use_closet_only(client):
    _put(user={"body_profile": BP}, closet=FULL_CLOSET)
    r = client.post("/fits/create", json={"user_id": "u", "count": 2, "occasion": "class"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "rules" and 1 <= len(body["fits"]) <= 2
    closet_ids = {c["id"] for c in FULL_CLOSET}
    for f in body["fits"]:
        assert f["id"].startswith("fit_") and _complete(f) and _ids(f) <= closet_ids
        assert all(p["source"] == "closet" and p["product"] is None for p in f["pieces"])
        assert f["new_total_usd"] == 0.0 and f["closet_count"] == len(f["pieces"]) and f["try_on"] is None
        assert f["occasion"] == "class" and "class" in f["reason"]
        assert "slim build" in f["reason"].lower()
        assert f["missing"] == []  # shoes are in the closet
    assert body["fits"][0]["name"] == "white top fit"


def test_catalog_never_leaks_into_fits(client):
    """A catalog full of in-size pieces changes nothing: no 'crossbody' when they already own a leather bag."""
    _put(user={"body_profile": BP}, products=CATALOG + [_mk("a_cross", "accessory", "Crossbody Bag", sizes={}, department="men")],
         closet=FULL_CLOSET)
    fits = client.post("/fits/create", json={"user_id": "u", "count": 3}).json()["fits"]
    assert fits
    assert all(p["source"] == "closet" for f in fits for p in f["pieces"])
    assert not any("a_cross" in _ids(f) or "p_top" in _ids(f) for f in fits)


def test_missing_slot_is_left_out_and_reported(client):
    _put(closet=[_closet("c_top", "top"), _closet("c_bot", "bottom")])  # no shoes in the closet
    fits = client.post("/fits/create", json={"user_id": "u", "count": 1}).json()["fits"]
    assert fits and _slots(fits[0]) == {"top", "bottom"} and fits[0]["missing"] == ["shoes"]


def test_empty_closet_is_502_not_shop_fits(client):
    _put(user={"body_profile": BP})  # catalog present, closet empty
    assert client.post("/fits/create", json={"user_id": "u", "count": 3}).status_code == 502


def test_must_include_and_budget_are_ignored(client):
    _put(user={"body_profile": BP}, closet=FULL_CLOSET)
    fits = client.post("/fits/create", json={"user_id": "u", "must_include": ["p_jacket"], "budget_usd": 50}).json()["fits"]
    assert fits and all("p_jacket" not in _ids(f) and all(p["source"] == "closet" for p in f["pieces"]) for f in fits)


def test_cache_hit_and_get_fit(client, monkeypatch):
    from app.ai import fit_creator
    _put(user={"body_profile": BP}, closet=FULL_CLOSET)
    first = client.post("/fits/create", json={"user_id": "u", "occasion": "date"}).json()
    monkeypatch.setattr(fit_creator, "rules_fits", lambda *a, **k: pytest.fail("should be cached"))
    second = client.post("/fits/create", json={"user_id": "u", "occasion": "date"}).json()
    assert second == first
    fid = first["fits"][0]["id"]
    assert client.get(f"/fits/{fid}", params={"user_id": "u"}).json() == first["fits"][0]
    assert client.get(f"/fits/{fid}", params={"user_id": "someone_else"}).status_code == 404
    assert client.get("/fits/fit_nope", params={"user_id": "u"}).status_code == 404
    monkeypatch.setattr(fit_creator, "rules_fits", fit_creator.__dict__["rules_fits"])


def test_expired_fit_is_404(client, monkeypatch):
    from app.ai import fit_creator
    _put(closet=FULL_CLOSET)
    fid = client.post("/fits/create", json={"user_id": "u"}).json()["fits"][0]["id"]
    monkeypatch.setattr(fit_creator.time, "time", lambda: 1e12)
    assert client.get(f"/fits/{fid}", params={"user_id": "u"}).status_code == 404


def test_empty_pool_is_502(client):
    _put(products=[], closet=[])
    assert client.post("/fits/create", json={"user_id": "u"}).status_code == 502


# ---------- AI path ----------

def test_ai_fits_validate_ids_fill_slots_and_pass_occasion(client, monkeypatch):
    _put(user={"body_profile": BP, "style_text": "clean streetwear"}, closet=FULL_CLOSET)
    calls = _ai(monkeypatch, [
        {"name": "Rooftop Clean", "reason": "Slim build, 30.5 in waist: navy chinos under your white tee.",
         "pieces": [{"slot": "top", "id": "c_top"}, {"slot": "bottom", "id": "c_bot"}, {"slot": "shoes", "id": "c_shoe"}]},
        {"name": "Missing Bottom", "reason": "needs filling", "pieces": [{"slot": "top", "id": "c_top2"}, {"slot": "shoes", "id": "c_shoe"}]},
        {"name": "Fake", "reason": "hallucinated", "pieces": [{"slot": "top", "id": "p_top"}, {"slot": "bottom", "id": "c_bot2"}]},
    ])
    r = client.post("/fits/create", json={"user_id": "u", "count": 3, "occasion": "rooftop party"})
    body = r.json()
    assert body["source"] == "ai" and len(calls) == 1
    assert "rooftop party" in calls[0] and "slim build" in calls[0] and "white tee" in calls[0]
    assert "p_bot" not in calls[0] and "Catalog candidates" not in calls[0]  # no shop items offered to the AI
    fits = body["fits"]
    assert fits[0]["name"] == "Rooftop Clean" and _ids(fits[0]) == {"c_top", "c_bot", "c_shoe"}
    assert fits[0]["reason"].startswith("Slim build") and fits[0]["occasion"] == "rooftop party"
    assert fits[0]["closet_count"] == 3 and fits[0]["new_total_usd"] == 0.0
    assert fits[1]["name"] == "Missing Bottom" and "bottom" in _slots(fits[1])  # rules filled it from the closet
    closet_ids = {c["id"] for c in FULL_CLOSET}
    assert all(_complete(f) and _ids(f) <= closet_ids for f in fits) and len(fits) == 3  # third topped up by rules
    assert "p_top" not in {i for f in fits for i in _ids(f)}  # catalog id = hallucinated


def test_ai_failure_falls_back_to_rules(client, monkeypatch):
    from app.ai.llm import BadModelOutput
    _put(closet=FULL_CLOSET)

    def boom(prompt, **kw):
        raise BadModelOutput("nope")
    _ai(monkeypatch, boom)
    body = client.post("/fits/create", json={"user_id": "u"}).json()
    assert body["source"] == "rules" and body["fits"]


# ---------- try-on and cart (routes stay; fits don't render or buy) ----------

def test_create_never_renders_tryon(client, monkeypatch):
    from app.ai import fit_creator
    _put(user={"body_profile": BP, "body_photo_url": "http://localhost:8000/static/uploads/me.jpg"}, closet=FULL_CLOSET)
    monkeypatch.setattr(fit_creator, "_try_on", lambda *a, **k: pytest.fail("fits must not render try-ons"))
    plain = client.post("/fits/create?tryon=true", json={"user_id": "u", "count": 1}).json()["fits"][0]
    assert plain["try_on"] is None
    assert client.post("/fits/fit_nope/try-on", params={"user_id": "u"}).status_code == 404


def test_add_fit_to_cart_has_nothing_to_buy(client):
    _put(user={"body_profile": BP}, closet=FULL_CLOSET)
    fit = client.post("/fits/create", json={"user_id": "u", "count": 1}).json()["fits"][0]
    r = client.post(f"/fits/{fit['id']}/cart", params={"user_id": "u"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0
    assert client.post("/fits/fit_nope/cart", params={"user_id": "u"}).status_code == 404


def test_prompt_is_closet_only_and_cache_version_bumped(client, monkeypatch):
    from app.ai import prompts
    assert prompts.FIT_CREATOR_VERSION not in ("v1", "v2", "v3")
    _put(closet=FULL_CLOSET)
    calls = _ai(monkeypatch, [])
    client.post("/fits/create", json={"user_id": "u", "count": 1})
    assert "CLOSET ONLY" in calls[0] and "new pieces" not in calls[0]


# ---------- department filter on every slot ----------

ACCESSORIES = [_mk("a_hoops", "accessory", "Hoop Earrings", sizes={}),  # department null -> leaks for men
               _mk("a_purse", "accessory", "Mini Handbag", sizes={}, department="unisex"),
               _mk("a_cap", "accessory", "Wool Cap", sizes={}, department="unisex"),
               _mk("a_mens", "accessory", "Leather Belt", sizes={}, department="men"),
               _mk("a_womens", "accessory", "Silk Scarf", sizes={}, department="women"),
               _mk("a_tie", "accessory", "Knit Necktie", sizes={}, department="unisex"),
               _mk("a_cuff", "accessory", "Cufflinks", sizes={})]


def test_pool_department_filter_covers_accessories():
    from app.ai.fit_creator import candidate_pool
    from app.store import store
    _put(products=CATALOG + ACCESSORIES)
    men = {p["id"] for p in candidate_pool(store.get("users", "u"), [], None)}
    assert "a_hoops" not in men and "a_purse" not in men and "a_womens" not in men and "a_cuff" not in men
    assert {"a_cap", "a_mens", "a_tie"} <= men
    assert "p_top" in men and "p_women" not in men  # null-department non-accessories still pass

    store.put("users", "u", {"id": "u", "display_name": "u", "shop_for": "women"})
    women = {p["id"] for p in candidate_pool(store.get("users", "u"), [], None)}
    assert "a_tie" not in women and "a_cuff" not in women and "a_hoops" not in women and "a_mens" not in women
    assert {"a_cap", "a_purse", "a_womens", "p_women", "p_top"} <= women

    store.put("users", "u", {"id": "u", "display_name": "u", "shop_for": "both"})
    both = {p["id"] for p in candidate_pool(store.get("users", "u"), [], None)}
    assert {a["id"] for a in ACCESSORIES} <= both


