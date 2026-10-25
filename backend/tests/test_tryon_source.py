"""Try-on v5 picks the user's own best photo as image 1: an outfit photo that shows a garment of the same
category as the product (full body, big, not cut off, other pieces that go with it) beats the lone body
photo; the matched box goes into the prompt; the chosen photo is in the cache key and the response."""
import os

import pytest

os.environ["MOCK_AI"] = "1"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.store import JsonStore
    from app.ai import service, tryon_source

    s = JsonStore(tmp_path)
    monkeypatch.setattr(service, "store", s)
    monkeypatch.setattr(tryon_source, "store", s)
    monkeypatch.setattr(service, "get_product", lambda pid: s.get("products", pid))
    s.put("users", "u", {"id": "u", "body_photo_url": "https://x/static/uploads/body.png",
                         "body_profile": {"build": "slim", "full_body": True}})
    s.put("products", "tee", {"id": "tee", "name": "Boxy Tee", "category": "top", "colors": ["white"],
                              "style_tags": ["streetwear"], "price_usd": 20.0, "image_url": "https://img/tee.jpg"})
    s.put("products", "boots", {"id": "boots", "name": "Chelsea Boots", "category": "shoes", "colors": ["black"],
                                "price_usd": 90.0, "image_url": "https://img/boots.jpg"})
    return s


def _wear(s, item_id, category, photo, box, color="black", style=("streetwear",), outfit=None):
    s.put("closet_items", item_id, {"id": item_id, "user_id": "u", "category": category, "color": color,
                                    "style_tags": list(style), "image_url": f"https://x/{item_id}.jpg",
                                    "worn_in": [{"photo_url": photo, "at": "t", "source": "closet", "box": box}],
                                    "outfit_id": outfit})


def test_body_photo_when_nothing_else(env):
    from app.ai.tryon_source import candidate_photos, pick_source_photo

    assert [c["kind"] for c in candidate_photos("u")] == ["body"]
    best = pick_source_photo("u", [env.get("products", "tee")])
    assert best["url"].endswith("body.png") and best["boxes"] == [None]


def test_outfit_photo_with_same_category_beats_body_photo(env):
    from app.ai.tryon_source import pick_source_photo, score_photo, candidate_photos

    fit = "https://x/static/uploads/fit1.jpg"
    env.put("outfits", "of_1", {"id": "of_1", "user_id": "u", "photo_url": fit, "piece_ids": ["ci_top", "ci_jeans", "ci_shoes"],
                                "source": "closet", "created_at": "2026-10-24T01:00:00"})
    _wear(env, "ci_top", "top", fit, [0.3, 0.2, 0.7, 0.5], color="black", outfit="of_1")
    _wear(env, "ci_jeans", "bottom", fit, [0.3, 0.5, 0.7, 0.9], color="blue", outfit="of_1")
    _wear(env, "ci_shoes", "shoes", fit, [0.35, 0.88, 0.65, 0.97], color="black", outfit="of_1")
    # a second outfit photo: bottoms only, so there is no top to replace
    jeans_only = "https://x/static/uploads/fit2.jpg"
    _wear(env, "ci_shorts", "bottom", jeans_only, [0.3, 0.5, 0.7, 0.8], color="khaki")

    tee = env.get("products", "tee")
    best = pick_source_photo("u", [tee])
    assert best["url"] == fit and best["kind"] == "outfit"
    assert best["boxes"] == [[0.3, 0.2, 0.7, 0.5]]  # the top being replaced
    by_url = {c["url"]: c for c in candidate_photos("u")}
    assert score_photo(by_url[fit], [tee])[0] > score_photo(by_url[jeans_only], [tee])[0]
    assert score_photo(by_url[jeans_only], [tee])[0] < score_photo(by_url["https://x/static/uploads/body.png"], [tee])[0]
    # two garments: each gets its own box, in product order
    best2 = pick_source_photo("u", [tee, env.get("products", "boots")])
    assert best2["boxes"] == [[0.3, 0.2, 0.7, 0.5], [0.35, 0.88, 0.65, 0.97]]


def test_bigger_uncut_photo_wins_and_compat_breaks_ties(env):
    from app.ai.tryon_source import candidate_photos, score_photo

    tee = env.get("products", "tee")
    small = "https://x/s.jpg"
    big = "https://x/b.jpg"
    cut = "https://x/c.jpg"
    _wear(env, "a", "top", small, [0.4, 0.3, 0.6, 0.5])
    _wear(env, "b", "top", big, [0.2, 0.2, 0.8, 0.6])
    _wear(env, "c", "top", cut, [0.0, 0.2, 0.8, 0.6])  # flush with the left edge
    by_url = {c["url"]: c for c in candidate_photos("u")}
    assert score_photo(by_url[big], [tee])[0] > score_photo(by_url[small], [tee])[0]
    assert score_photo(by_url[big], [tee])[0] > score_photo(by_url[cut], [tee])[0]

    # same top box, but the trousers in one photo clash (warm) and go (neutral) in the other
    clash, goes = "https://x/clash.jpg", "https://x/goes.jpg"
    _wear(env, "t1", "top", clash, [0.3, 0.2, 0.7, 0.5])
    _wear(env, "p1", "bottom", clash, [0.3, 0.5, 0.7, 0.9], color="orange", style=("boho",))
    _wear(env, "t2", "top", goes, [0.3, 0.2, 0.7, 0.5])
    _wear(env, "p2", "bottom", goes, [0.3, 0.5, 0.7, 0.9], color="black", style=("streetwear",))
    by_url = {c["url"]: c for c in candidate_photos("u")}
    blue_tee = {**tee, "colors": ["blue"]}  # a white tee is neutral and goes with anything
    assert score_photo(by_url[goes], [blue_tee])[0] > score_photo(by_url[clash], [blue_tee])[0]


def test_prompt_gets_the_box_and_cache_key_tracks_the_photo(env, monkeypatch):
    from app.ai import prompts, service

    p = prompts.tryon_prompt(["top"], ["Boxy Tee"], boxes=[[0.3, 0.2, 0.7, 0.5]])
    assert "located at roughly 30%-70% across and 20%-50% down image 1" in p
    assert "(" not in prompts.tryon_prompt(["top"]).split("Image 2")[1].split("replace")[0]  # no box, no location

    tee_only = service.try_on("u", ["tee"], [])
    assert tee_only.source_photo_url.endswith("body.png") and tee_only.cached is False
    assert service.try_on("u", ["tee"], []).cached is True
    # an outfit photo with a top appears: it is now the source, so the old try-on is not reused
    fit = "https://x/static/uploads/fit1.jpg"
    _wear(env, "ci_top", "top", fit, [0.3, 0.2, 0.7, 0.5])
    _wear(env, "ci_jeans", "bottom", fit, [0.3, 0.5, 0.7, 0.9])
    again = service.try_on("u", ["tee"], [])
    assert again.cached is False and again.source_photo_url == fit
    assert service.try_on("u", ["tee"], []).source_photo_url == fit


def test_route_and_fit_creator_return_source_photo_url(env, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ai import fit_creator, service

    fit = "https://x/static/uploads/fit1.jpg"
    _wear(env, "ci_top", "top", fit, [0.3, 0.2, 0.7, 0.5])
    r = TestClient(app).post("/tryon", json={"user_id": "u", "product_ids": ["tee"]})
    assert r.status_code == 200, r.text
    assert r.json()["source_photo_url"] == fit and set(r.json()) >= {"image_url", "cached", "mode", "source_photo_url"}

    monkeypatch.setattr(fit_creator, "store", env)
    out = fit_creator._try_on("u", {"pieces": [{"source": "catalog", "product": {"id": "tee"}}]})
    assert out == {"image_url": "https://img/tee.jpg", "mode": "collage", "source_photo_url": fit}
