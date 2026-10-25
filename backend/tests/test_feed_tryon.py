"""Sprint 4 §10: closet_picks (rules, one per slot, clash guard), tryon status, background prefetch."""
import os

import pytest

os.environ["MOCK_AI"] = "1"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.store import JsonStore
    from app.ai import feed_tryon, service, tryon_source

    s = JsonStore(tmp_path)
    monkeypatch.setattr(service, "store", s)
    monkeypatch.setattr(tryon_source, "store", s)
    monkeypatch.setattr(service, "get_product", lambda pid: s.get("products", pid))
    feed_tryon._inflight.clear()
    s.put("users", "u", {"id": "u", "body_photo_url": "https://x/static/uploads/body.png",
                         "body_profile": {"build": "slim", "full_body": True}})
    s.put("products", "jeans", {"id": "jeans", "name": "Baggy Jeans", "category": "bottom", "colors": ["blue"],
                                "style_tags": ["streetwear"], "formality": 2, "price_usd": 40.0,
                                "image_url": "https://img/jeans.jpg"})
    return s


def _ci(s, id_, cat, label, color="black", tags=("streetwear",), formality=2, **kw):
    s.put("closet_items", id_, {"id": id_, "user_id": "u", "category": cat, "label": label, "color": color,
                                "style_tags": list(tags), "formality": formality,
                                "image_url": f"https://x/{id_}.jpg", **kw})


def test_empty_closet_gives_no_picks(env):
    from app.ai.service import closet_picks

    assert closet_picks("u", env.get("products", "jeans")) == []
    assert closet_picks("u", "missing") == []


def test_one_per_slot_in_order_for_a_bottom(env):
    from app.ai.service import closet_picks

    _ci(env, "a1", "accessory", "silver chain")
    _ci(env, "t1", "top", "black tee", display_image_url="https://x/t1-clean.png")
    _ci(env, "t2", "top", "grey tee", color="grey")
    _ci(env, "s1", "shoes", "white sneakers", color="white")
    _ci(env, "o1", "outerwear", "denim jacket", color="blue")
    _ci(env, "b1", "bottom", "cargo pants")  # same category as the anchor: never picked
    picks = closet_picks("u", "jeans")
    assert [p["category"] for p in picks] == ["top", "shoes", "outerwear", "accessory"]
    assert {"id", "label", "category", "image_url"} <= set(picks[0])
    tee = next(p for p in picks if p["category"] == "top")
    if tee["id"] == "t1":
        assert tee["image_url"] == "https://x/t1-clean.png"  # the clean shot, not the raw crop
    assert closet_picks("u", "jeans") == picks  # deterministic
    assert len(closet_picks("u", "jeans", k=2)) == 2


def test_dress_order_uses_bag_slot(env):
    from app.ai.service import closet_picks

    env.put("products", "dress", {"id": "dress", "name": "Slip Dress", "category": "dress", "colors": ["black"],
                                  "style_tags": ["minimalist"], "formality": 3, "image_url": "https://img/d.jpg"})
    _ci(env, "bag", "accessory", "black shoulder bag", tags=("minimalist",), formality=3)
    _ci(env, "ear", "accessory", "gold earrings", tags=("minimalist",), formality=3)
    _ci(env, "hee", "shoes", "black heels", tags=("minimalist",), formality=3)
    assert [p["id"] for p in closet_picks("u", "dress")] == ["hee", "bag", "ear"]


def test_athletic_anchor_never_gets_a_formal_pick(env):
    from app.ai.service import closet_picks

    env.put("products", "gymtee", {"id": "gymtee", "name": "Training Tee", "category": "top", "colors": ["black"],
                                   "style_tags": ["athleisure"], "formality": 1, "image_url": "https://img/g.jpg"})
    _ci(env, "belt", "accessory", "leather belt", color="brown", tags=("business",), formality=4)
    _ci(env, "jog", "bottom", "joggers", color="grey", tags=("athleisure",), formality=1)
    ids = [p["id"] for p in closet_picks("u", "gymtee")]
    assert "belt" not in ids and "jog" in ids


def test_status_needs_photo_without_any_photo(env):
    from app.ai.service import tryon_status

    env.put("users", "u", {"id": "u"})
    assert tryon_status("u", "jeans")["status"] == "needs_photo"


def test_status_unavailable_when_ai_off_then_prefetch_makes_collage(env):
    from app.ai import feed_tryon
    from app.ai.service import prefetch_tryons, tryon_status

    _ci(env, "t1", "top", "black tee")
    _ci(env, "a1", "accessory", "silver chain")
    assert tryon_status("u", "jeans")["status"] == "unavailable"  # MOCK_AI: no Gemini
    assert prefetch_tryons("u", ["jeans"])["jeans"]["status"] == "pending"
    feed_tryon.wait_prefetch()
    st = tryon_status("u", "jeans")
    assert st["status"] == "unavailable" and st["mode"] == "collage" and st["image_url"]
    assert feed_tryon.prefetch_used("u") == 0  # collages don't count toward the daily cap


def _ai_on(monkeypatch):
    from app.ai import feed_tryon, service

    monkeypatch.setattr(feed_tryon, "_ai_available", lambda: True)
    calls = []

    def fake_try_on(user_id, pids, cids):
        calls.append((pids, cids))
        src = service.store.get("users", user_id)["body_photo_url"]
        key = service._tryon_key(user_id, pids, cids, src)
        service.store.put("tryon_cache", key, {"image_url": f"https://x/{key}.png", "mode": "ai", "user_id": user_id})

    monkeypatch.setattr(service, "try_on", fake_try_on)
    return calls


def test_prefetch_renders_once_with_wearable_picks_only(env, monkeypatch):
    from app.ai import feed_tryon
    from app.ai.service import prefetch_tryons, tryon_status

    calls = _ai_on(monkeypatch)
    _ci(env, "t1", "top", "black tee")
    _ci(env, "a1", "accessory", "silver chain")
    assert tryon_status("u", "jeans")["status"] == "none"
    prefetch_tryons("u", ["jeans", "jeans"])
    feed_tryon.wait_prefetch()
    assert calls == [(["jeans"], ["t1"])]  # de-duplicated, accessory left out of the render
    st = tryon_status("u", "jeans")
    assert st["status"] == "ready" and st["mode"] == "ai"
    assert prefetch_tryons("u", ["jeans"])["jeans"]["status"] == "ready"
    feed_tryon.wait_prefetch()
    assert len(calls) == 1 and feed_tryon.prefetch_used("u") == 1


def test_in_flight_reports_pending(env, monkeypatch):
    from app.ai import feed_tryon, service
    from app.ai.service import tryon_status

    _ai_on(monkeypatch)
    pids, cids, body = feed_tryon._render_args("u", env.get("products", "jeans"), None)
    feed_tryon._inflight.add(service._tryon_key("u", pids, cids, body))
    assert tryon_status("u", "jeans")["status"] == "pending"


def test_daily_cap_turns_unavailable(env, monkeypatch):
    from app.ai import feed_tryon
    from app.ai.service import tryon_status

    _ai_on(monkeypatch)
    monkeypatch.setattr(feed_tryon, "PREFETCH_PER_USER_DAY", 1)
    env.put("prefetch_usage", feed_tryon._day_key("u"), {"n": 1})
    assert tryon_status("u", "jeans")["status"] == "unavailable"
