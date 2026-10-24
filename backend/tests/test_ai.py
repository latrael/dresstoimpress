import os
import subprocess
import sys

import pytest

os.environ["MOCK_AI"] = "1"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    backend = os.path.dirname(os.path.dirname(__file__))
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=backend, check=True,
                   env={**os.environ})
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_tag(client):
    r = client.post("/closet/tag", json={"user_id": "u_demo", "image_url": "https://x/y.jpg"})
    assert r.status_code == 200
    assert r.json()["category"] in {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}


def test_tryon_caches(client):
    body = {"user_id": "u_demo", "product_ids": ["hm-demo-1"], "closet_item_ids": ["ci_demo_2"]}
    first = client.post("/tryon", json=body).json()
    second = client.post("/tryon", json=body).json()
    assert first["cached"] is False and second["cached"] is True
    assert first["image_url"] == second["image_url"]


def test_tryon_unknown_user(client):
    r = client.post("/tryon", json={"user_id": "nobody", "product_ids": ["hm-demo-1"]})
    assert r.status_code == 400


def test_pair_budget_first(client):
    r = client.post("/pair", json={"user_id": "u_demo", "candidate_product_ids": []})
    ids = [p["product_id"] for p in r.json()]
    assert ids and ids[-1] == "mango-demo-1"  # $130 bomber is over the outerwear budget


def test_extract_json():
    from app.ai.llm import extract_json
    assert extract_json('sure!\n```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert extract_json('here: {"category": "top"} done') == {"category": "top"}


PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def test_upload_tags_and_serves(client):
    r = client.post("/closet/upload", data={"user_id": "u_demo"},
                    files={"file": ("shirt.png", PNG_1PX, "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["image_url"]
    assert "/static/uploads/" in url
    assert client.get(url.split("8000", 1)[1]).content == PNG_1PX


def test_upload_rejects_non_image(client):
    r = client.post("/closet/upload", data={"user_id": "u_demo"},
                    files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 415


def test_body_photo_sets_user(client):
    r = client.post("/users/u_new/body-photo", files={"file": ("me.png", PNG_1PX, "image/png")})
    assert r.status_code == 200
    from app.store import store
    assert store.get("users", "u_new")["body_photo_url"] == r.json()["body_photo_url"]


def test_tag_rejects_file_url(client):
    r = client.post("/closet/tag", json={"user_id": "u_demo", "image_url": "file:///etc/passwd"})
    assert r.status_code == 400


def test_fetch_image_blocks_traversal_and_file(client):
    from app.ai.llm import fetch_image
    with pytest.raises(ValueError):
        fetch_image("/static/../../etc/passwd")
    with pytest.raises(ValueError):
        fetch_image("file:///etc/passwd")


def test_shop_fit_matches_tags(client):
    body = {"viewer_id": "u_demo", "tagged": [
        {"label": "denim jacket", "retailer": "zara"},
        {"label": "baby tee"},
        {"label": "nothing like this exists"},
    ]}
    r = client.post("/ai/shop-fit", json=body)
    assert r.status_code == 200
    got = {p["id"]: p["matched_tag"] for p in r.json()}
    assert got == {"zara-demo-1": "denim jacket", "hm-demo-1": "baby tee"}
    assert all("reason" in p for p in r.json())


def test_style_memory_from_swipes(client):
    from app.ai.memory import style_memory
    from app.store import store
    assert style_memory("u_demo") == ""
    store.put("swipes", "s1", {"user_id": "u_demo", "product_id": "hm-demo-1", "action": "cart"})
    store.put("swipes", "s2", {"user_id": "u_demo", "product_id": "mango-demo-1", "action": "discard"})
    mem = style_memory("u_demo")
    assert "Cropped baby tee" in mem.split("\n")[0] and "Leather bomber" in mem.split("\n")[1]


def test_record_swipe_noop_without_moss(client):
    from app.ai.memory import record_swipe
    from app.store import store
    record_swipe("u_demo", store.get("products", "hm-demo-1"), "cart")  # must not raise


def test_usage_endpoint(client):
    r = client.get("/ai/usage").json()
    assert {"claude_calls", "est_usd", "gemini_images", "budget_usd"} <= r.keys()


def test_budget_stops_claude_before_calling(client, monkeypatch):
    from app.ai import llm
    from app.store import store
    monkeypatch.setattr(llm, "AI_BUDGET_USD", 1.0)
    store.put("ai_usage", "total", {**llm.usage(), "est_usd": 1.5})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")  # would fail loudly if a real call happened
    with pytest.raises(llm.BadModelOutput, match="budget"):
        llm.claude_json("hi")
    store.put("ai_usage", "total", {**llm.usage(), "est_usd": 0.0})


def test_cost_accounting(client):
    from app.ai import llm
    before = llm.usage()["est_usd"]
    llm._record_claude("claude-haiku-5-5", 1_000_000, 0)
    assert round(llm.usage()["est_usd"] - before, 4) == 0.10


def test_pair_cache_reuses_claude(client, monkeypatch):
    from app.ai import llm, service
    calls = []

    def fake(prompt, **kw):
        calls.append(1)
        return [{"product_id": "hm-demo-1", "score": 0.9, "reason": "goes with your baggy jeans",
                 "pairs_with": ["ci_demo_2"]}]
    monkeypatch.setattr(service, "ai_json", fake)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    a = service.pair("u_demo", ["hm-demo-1", "zara-demo-1"])
    b = service.pair("u_demo", ["hm-demo-1", "zara-demo-1"])
    assert len(calls) == 1 and a == b and a[0].pairs_with == ["ci_demo_2"]


def test_text_provider_routing(monkeypatch):
    from app.ai import llm
    monkeypatch.delenv("MOCK_AI", raising=False)
    monkeypatch.delenv("AI_TEXT_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm.text_provider() == "mock"
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert llm.text_provider() == "gemini"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert llm.text_provider() == "claude"
    monkeypatch.setenv("AI_TEXT_PROVIDER", "gemini")
    assert llm.text_provider() == "gemini"
    monkeypatch.setenv("MOCK_AI", "1")
    assert llm.text_provider() == "mock"


def test_claude_failure_falls_back_to_gemini(client, monkeypatch):
    from app.ai import llm
    monkeypatch.delenv("MOCK_AI", raising=False)
    monkeypatch.delenv("AI_TEXT_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    def broke(*a, **k):
        raise RuntimeError("Your credit balance is too low")
    monkeypatch.setattr(llm, "claude_json", broke)
    monkeypatch.setattr(llm, "gemini_json", lambda *a, **k: {"category": "top"})
    assert llm.ai_json("x") == {"category": "top"}
    assert "credit balance" in llm.usage()["last_claude_error"]


def test_tag_sets_label(client):
    r = client.post("/closet/tag", json={"user_id": "u_demo", "image_url": "https://x/label.jpg"})
    assert r.json()["label"] == "black tee"


def test_pair_sorted_by_score(client, monkeypatch):
    from app.ai import service
    monkeypatch.setattr(service, "ai_json", lambda p, **k: [
        {"product_id": "uniqlo-demo-1", "score": 0.4, "reason": "a", "pairs_with": []},
        {"product_id": "asos-demo-1", "score": 0.95, "reason": "b", "pairs_with": []}])
    monkeypatch.setattr(service, "text_mock", lambda: False)
    got = service.pair("u_demo", ["uniqlo-demo-1", "asos-demo-1"])
    assert [r.product_id for r in got] == ["asos-demo-1", "uniqlo-demo-1"]


def test_tag_fit_mock(client):
    r = client.post("/ai/tag-fit", json={"image_url": "https://x/fit.jpg"})
    assert r.status_code == 200
    labels = [t["label"] for t in r.json()]
    assert labels == ["light-wash baggy jeans", "white baby tee"]


def test_tag_fit_rejects_file_url(client):
    assert client.post("/ai/tag-fit", json={"image_url": "file:///etc/passwd"}).status_code == 400


def test_tag_fit_maps_brand_and_drops_junk(client, monkeypatch):
    from app.ai import service
    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(service, "ai_json", lambda p, **k: [
        {"label": "denim jacket", "category": "outerwear", "brand": "Zara"},
        {"label": ""}, "junk", {"label": "cap", "category": "hat"}])
    got = service.tag_fit("https://x/brand.jpg")
    assert got[0]["retailer"] == "zara" and got[0]["category"] == "outerwear"
    assert len(got) == 2 and got[1]["category"] == "accessory"


def test_shop_fit_from_photo(client):
    r = client.post("/ai/shop-fit", json={"viewer_id": "u_demo", "photo_url": "https://x/fit2.jpg"})
    assert r.status_code == 200
    assert "hm-demo-1" in {p["id"] for p in r.json()}  # "white baby tee" -> Cropped baby tee


def test_finder_rejects_wrong_type_and_category():
    from app.ai.finder import best_matches, match_score
    tee = {"id": "t", "name": "Cropped baby tee", "category": "top", "colors": ["white"], "retailer": "hm"}
    hoodie = {"id": "h", "name": "Cropped hoodie", "category": "top", "colors": ["mustard"], "retailer": "asos"}
    jeans = {"id": "j", "name": "Baggy jeans", "category": "bottom", "colors": ["light blue"], "retailer": "zara"}
    tag = {"label": "cropped pullover hoodie", "category": "top", "color": "mustard yellow"}
    assert match_score(tag, tee) == 0            # same "cropped", wrong type
    assert match_score(tag, jeans) == 0          # wrong category
    assert best_matches(tag, [tee, hoodie, jeans]) == [hoodie]


def test_finder_live_search_normalizes(monkeypatch):
    import httpx
    from app.ai import finder

    class R:
        def raise_for_status(self): pass
        def json(self):
            return [{"site": "asos", "name": "ASOS DESIGN oversized hoodie in mustard", "price": "$42.00",
                     "image": "https://img/x.jpg", "url": "https://asos.com/p/1", "sizes": ["S", "M"]},
                    {"site": "asos", "name": "no price"}]
    sent = {}
    monkeypatch.setenv("APIFY_TOKEN", "t")
    monkeypatch.setattr(httpx, "post", lambda url, **k: sent.update(k) or R())
    got = finder.live_search({"label": "oversized hoodie", "color": "mustard", "category": "top"})
    assert len(got) == 1 and got[0]["price_usd"] == 42.0 and got[0]["retailer"] == "asos"
    assert "mustard+oversized+hoodie" in sent["json"]["asosCategoryUrl"]
    assert got[0]["id"] == finder.live_search({"label": "oversized hoodie", "color": "mustard"})[0]["id"]  # cached, stable id


def test_finder_no_token_no_live_search(monkeypatch):
    from app.ai import finder
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert finder.live_search({"label": "hoodie"}) == []
