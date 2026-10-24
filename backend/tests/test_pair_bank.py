"""pair() reason bank: after a swipe, /feed reuses Claude's earlier reasons at once and re-ranks in the background."""
import pytest

BASE = {"retailer": "hm", "brand": "H&M", "category": "top", "price_usd": 20.0, "colors": ["black"],
        "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p", "style_tags": ["streetwear"]}
IDS = [f"p{i}" for i in range(8)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(service, "PAIR_REUSE", True)
    store.put("closet_items", "ci1", {"id": "ci1", "user_id": "u_b", "image_url": "https://img/c.jpg",
                                      "category": "bottom", "color": "light blue", "pattern": "solid",
                                      "style_tags": ["streetwear"], "formality": 2, "label": "baggy jeans"})
    for i in IDS:
        store.put("products", i, {**BASE, "id": i, "name": f"Tee {i}"})

    calls, queued = [], []

    def fake_ai(prompt, **kw):
        calls.append(prompt)
        n = len(calls)
        return [{"product_id": i, "score": 0.9 - 0.05 * j, "reason": f"call {n}: goes with your baggy jeans",
                 "pairs_with": ["ci1"]} for j, i in enumerate(IDS) if f'"{i}"' in prompt]

    monkeypatch.setattr(service, "ai_json", fake_ai)
    monkeypatch.setattr(service, "_spawn", queued.append)  # hold background refreshes until the test runs them
    service._refreshing.clear()
    return service, store, calls, queued


def _swipe(store, pid):
    store.put("swipes", f"u_b:{pid}", {"user_id": "u_b", "product_id": pid, "action": "discard"})


def test_after_a_swipe_feed_answers_from_the_bank_without_waiting_for_claude(env):
    service, store, calls, queued = env
    first = service.pair("u_b", IDS, k=6)
    assert len(calls) == 1 and first[0].reason.lower().startswith("call 1")

    _swipe(store, "p0")
    second = service.pair("u_b", IDS[1:], k=6)
    assert len(calls) == 1, "no blocking Claude call after a swipe"
    assert [r.product_id for r in second][:3] == ["p1", "p2", "p3"]
    assert all(r.reason.lower().startswith("call 1") for r in second if r.product_id in IDS[1:6])
    assert len(queued) == 1, "one background re-rank queued"

    queued.pop()()  # the background refresh lands
    assert len(calls) == 2
    third = service.pair("u_b", IDS[1:], k=6)
    assert len(calls) == 2 and third[0].reason.lower().startswith("call 2"), "next load uses the fresh ranking"


def test_only_one_background_refresh_at_a_time(env):
    service, store, calls, queued = env
    service.pair("u_b", IDS, k=6)
    _swipe(store, "p0")
    service.pair("u_b", IDS[1:], k=6)
    _swipe(store, "p1")
    service.pair("u_b", IDS[2:], k=6)
    assert len(queued) == 1


def test_bank_too_thin_falls_back_to_a_fresh_claude_call(env):
    service, store, calls, queued = env
    service.pair("u_b", IDS[:2], k=2)  # bank only knows p0, p1
    out = service.pair("u_b", IDS[2:], k=6)  # none of these are banked
    assert len(calls) == 2 and not queued
    assert out[0].reason.lower().startswith("call 2")


def test_closet_change_starts_a_new_bank(env):
    service, store, calls, queued = env
    service.pair("u_b", IDS, k=6)
    store.put("closet_items", "ci2", {"id": "ci2", "user_id": "u_b", "image_url": "https://img/d.jpg",
                                      "category": "shoes", "color": "white", "pattern": "solid",
                                      "style_tags": ["streetwear"], "formality": 2, "label": "white sneakers"})
    service.pair("u_b", IDS, k=6)
    assert len(calls) == 2 and not queued


def test_reuse_off_keeps_the_old_behaviour(env, monkeypatch):
    service, store, calls, queued = env
    monkeypatch.setattr(service, "PAIR_REUSE", False)
    service.pair("u_b", IDS, k=6)
    _swipe(store, "p0")
    service.pair("u_b", IDS[1:], k=6)
    assert len(calls) == 2 and not queued


def test_failed_background_refresh_keeps_the_bank(env, monkeypatch):
    service, store, calls, queued = env
    service.pair("u_b", IDS, k=6)
    _swipe(store, "p0")
    service.pair("u_b", IDS[1:], k=6)

    def boom(prompt, **kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr(service, "ai_json", boom)
    queued.pop()()  # logs and swallows
    assert not service._refreshing
    out = service.pair("u_b", IDS[2:], k=6)
    assert out and out[0].reason.lower().startswith("call 1")


def test_bank_merges_newest_first_and_ages_older_scores(env):
    service, store, calls, queued = env
    service.pair("u_b", IDS[:4], k=4)
    service.pair("u_b", IDS[4:], k=4)  # thin bank for these -> fresh call, merged in
    bank = [d for k, d in store._load("pair_cache").items() if k.startswith("bank_")]
    assert len(bank) == 1
    rows = bank[0]["raw"]
    assert [r["product_id"] for r in rows[:4]] == IDS[4:]
    assert {r["product_id"] for r in rows} == set(IDS)
    assert rows[4]["score"] == pytest.approx(0.9 * 0.9)
