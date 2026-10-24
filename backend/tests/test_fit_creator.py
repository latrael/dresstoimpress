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


# ---------- rules (mock AI) ----------

def test_rules_fits_are_complete_use_pool_ids_and_sizes(client):
    _put(user={"body_profile": BP}, closet=[_closet("c_top", "top", "white", "white tee"), _closet("c_bot", "bottom", "navy")])
    r = client.post("/fits/create", json={"user_id": "u", "count": 2, "occasion": "class"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "rules" and 1 <= len(body["fits"]) <= 2
    pool = {p["id"] for p in CATALOG} | {"c_top", "c_bot"}
    for f in body["fits"]:
        assert f["id"].startswith("fit_") and _complete(f) and _ids(f) <= pool
        assert f["occasion"] == "class" and "class" in f["reason"]
        assert "slim build" in f["reason"].lower() and "30.5 in waist" in f["reason"]
        assert f["closet_count"] >= 1 and f["try_on"] is None
        assert "p_women" not in _ids(f) and "p_out" not in _ids(f)
        for p in f["pieces"]:
            if p["source"] == "catalog":
                assert p["your_size"] is not None and p["in_your_size"] is True
                assert p["product"]["your_size"] == p["your_size"]
            else:
                assert p["closet_item"]["id"].startswith("c_") and p["your_size"] is None
        assert f["new_total_usd"] == round(sum(p["product"]["price_usd"] for p in f["pieces"] if p["source"] == "catalog"), 2)
    assert body["fits"][0]["name"] == "white top fit"


def test_no_body_profile_means_no_size_filter_and_null_sizes(client):
    _put(closet=[_closet("c_top", "top")])
    fits = client.post("/fits/create", json={"user_id": "u"}).json()["fits"]
    assert fits and all(_complete(f) for f in fits)
    assert all(p["your_size"] is None for f in fits for p in f["pieces"] if p["source"] == "catalog")


def test_empty_closet_builds_all_new_fits(client):
    _put(user={"body_profile": BP})
    fits = client.post("/fits/create", json={"user_id": "u", "count": 3}).json()["fits"]
    assert fits and all(_complete(f) and f["closet_count"] == 0 for f in fits)


def test_must_include_and_budget(client):
    _put(user={"body_profile": BP}, closet=[_closet("c_top", "top")])
    r = client.post("/fits/create", json={"user_id": "u", "must_include": ["p_jacket"], "budget_usd": 50})
    fits = r.json()["fits"]
    assert fits and all("p_jacket" in _ids(f) for f in fits)  # even though $60 > budget: must-include always wins
    # nothing else over budget is in the pool
    assert all(p["product"]["price_usd"] <= 50 for f in fits for p in f["pieces"]
               if p["source"] == "catalog" and p["product"]["id"] != "p_jacket")


def test_cache_hit_and_get_fit(client, monkeypatch):
    from app.ai import fit_creator
    _put(user={"body_profile": BP}, closet=[_closet("c_top", "top")])
    first = client.post("/fits/create", json={"user_id": "u", "occasion": "date"}).json()
    monkeypatch.setattr(fit_creator, "rules_fits", lambda *a, **k: pytest.fail("should be cached"))
    second = client.post("/fits/create", json={"user_id": "u", "occasion": "date"}).json()
    assert second == first
    fid = first["fits"][0]["id"]
    assert client.get(f"/fits/{fid}", params={"user_id": "u"}).json() == first["fits"][0]
    assert client.get(f"/fits/{fid}", params={"user_id": "someone_else"}).status_code == 404
    assert client.get("/fits/fit_nope", params={"user_id": "u"}).status_code == 404
    # a different occasion is a different cache entry
    monkeypatch.setattr(fit_creator, "rules_fits", fit_creator.__dict__["rules_fits"])


def test_expired_fit_is_404(client, monkeypatch):
    from app.ai import fit_creator
    _put(closet=[_closet("c_top", "top")])
    fid = client.post("/fits/create", json={"user_id": "u"}).json()["fits"][0]["id"]
    monkeypatch.setattr(fit_creator.time, "time", lambda: 1e12)
    assert client.get(f"/fits/{fid}", params={"user_id": "u"}).status_code == 404


def test_empty_pool_is_502(client):
    _put(products=[], closet=[])
    assert client.post("/fits/create", json={"user_id": "u"}).status_code == 502


# ---------- AI path ----------

def test_ai_fits_validate_ids_fill_slots_and_pass_occasion(client, monkeypatch):
    _put(user={"body_profile": BP, "style_text": "clean streetwear"}, closet=[_closet("c_top", "top", "white", "white tee")])
    calls = _ai(monkeypatch, [
        {"name": "Rooftop Clean", "reason": "Slim build, 30.5 in waist: tapered denim under your white tee.",
         "pieces": [{"slot": "top", "id": "c_top"}, {"slot": "bottom", "id": "p_bot"}, {"slot": "shoes", "id": "p_shoe"}]},
        {"name": "Missing Shoes", "reason": "needs filling", "pieces": [{"slot": "top", "id": "p_top"}, {"slot": "bottom", "id": "p_bot"}]},
        {"name": "Fake", "reason": "hallucinated", "pieces": [{"slot": "top", "id": "p_nope"}, {"slot": "shoes", "id": "p_shoe"}]},
    ])
    r = client.post("/fits/create", json={"user_id": "u", "count": 3, "occasion": "rooftop party"})
    body = r.json()
    assert body["source"] == "ai" and len(calls) == 1
    assert "rooftop party" in calls[0] and "slim build" in calls[0] and "white tee" in calls[0] and "p_bot" in calls[0]
    fits = body["fits"]
    assert fits[0]["name"] == "Rooftop Clean" and _ids(fits[0]) == {"c_top", "p_bot", "p_shoe"}
    assert fits[0]["reason"].startswith("Slim build") and fits[0]["occasion"] == "rooftop party"
    assert fits[0]["closet_count"] == 1 and fits[0]["new_total_usd"] == 40.0
    assert fits[1]["name"] == "Missing Shoes" and "shoes" in _slots(fits[1])  # rules filled the missing slot
    pool = {p["id"] for p in CATALOG} | {"c_top"}
    assert all(_complete(f) and _ids(f) <= pool for f in fits) and len(fits) == 3  # third topped up by rules
    assert "p_nope" not in {i for f in fits for i in _ids(f)}


def test_ai_failure_falls_back_to_rules(client, monkeypatch):
    from app.ai.llm import BadModelOutput
    _put(closet=[_closet("c_top", "top")])

    def boom(prompt, **kw):
        raise BadModelOutput("nope")
    _ai(monkeypatch, boom)
    body = client.post("/fits/create", json={"user_id": "u"}).json()
    assert body["source"] == "rules" and body["fits"]


def test_ai_must_include_is_enforced(client, monkeypatch):
    _put(user={"body_profile": BP}, closet=[_closet("c_top", "top")])
    _ai(monkeypatch, [{"name": "Forgot", "reason": "r", "pieces": [{"slot": "top", "id": "c_top"},
                                                                    {"slot": "bottom", "id": "p_bot"}, {"slot": "shoes", "id": "p_shoe"}]}])
    fits = client.post("/fits/create", json={"user_id": "u", "count": 1, "must_include": ["p_jacket"]}).json()["fits"]
    assert all("p_jacket" in _ids(f) for f in fits)


# ---------- try-on and cart ----------

def test_tryon_only_on_request_and_lazy_route(client):
    _put(user={"body_profile": BP, "body_photo_url": "http://localhost:8000/static/uploads/me.jpg"}, closet=[_closet("c_top", "top")])
    plain = client.post("/fits/create", json={"user_id": "u", "count": 1}).json()["fits"][0]
    assert plain["try_on"] is None
    lazy = client.post(f"/fits/{plain['id']}/try-on", params={"user_id": "u"}).json()
    assert lazy["mode"] == "collage" and lazy["image_url"].startswith("http")  # MOCK_AI placeholder
    assert client.get(f"/fits/{plain['id']}", params={"user_id": "u"}).json()["try_on"] == lazy
    eager = client.post("/fits/create?tryon=true", json={"user_id": "u", "count": 1}).json()["fits"][0]
    assert eager["try_on"] == lazy
    assert client.post("/fits/fit_nope/try-on", params={"user_id": "u"}).status_code == 404


def test_add_fit_to_cart_uses_your_size(client):
    _put(user={"body_profile": BP}, closet=[_closet("c_top", "top")])
    fit = client.post("/fits/create", json={"user_id": "u", "count": 1}).json()["fits"][0]
    r = client.post(f"/fits/{fit['id']}/cart", params={"user_id": "u"})
    assert r.status_code == 200, r.text
    cart = r.json()
    lines = {(i["product_id"], i["size"]) for g in cart["groups"] for i in g["items"]}
    want = {(p["product"]["id"], p["your_size"]) for p in fit["pieces"] if p["source"] == "catalog"}
    assert lines == want and cart["count"] == len(want) and cart["total_usd"] == fit["new_total_usd"]
    assert client.get("/cart/u").json() == cart
    assert client.post("/fits/fit_nope/cart", params={"user_id": "u"}).status_code == 404
