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


def test_tryon_unknown_product(client):
    r = client.post("/tryon", json={"user_id": "u_demo", "product_ids": ["nope"]})
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
    item = r.json()
    # closet v2: the mock tagger says "black tee" again, so this merges into the /closet/tag item above and the
    # photo lands in worn_in; image_url/display_image_url may be a catalog match. The upload is still served.
    url = item["worn_in"][-1]["photo_url"]
    assert "/static/uploads/" in url and item["image_url"] == item["display_image_url"]
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


def test_finder_live_search_uses_hm_actor(monkeypatch):
    from app.ai import finder
    from app.commerce import ingest
    from app.store import store

    raw = [{"id": "0970819001", "title": "Loose Fit Hoodie", "category": "men_hoodiessweatshirts",
            "color": "Mustard yellow", "price": 24.99, "model_image": "https://img/x.jpg",
            "url": "https://www2.hm.com/en_us/productpage.0970819001.html",
            "sizes": [{"size": "M", "in_stock": True}]},
           {"id": "kid1", "title": "Kids hoodie", "category": "kids_hoodies", "color": "Mustard",
            "price": 9.99, "model_image": "https://img/k.jpg", "url": "https://www2.hm.com/k"}]
    calls = []
    monkeypatch.setenv("APIFY_TOKEN", "t")
    monkeypatch.setattr(ingest, "fetch_hm", lambda kw, n, token: calls.append((kw, n)) or raw)
    tag = {"label": "mustard oversized hoodie", "color": "mustard", "category": "top"}
    got = finder.live_search(tag)
    assert calls == [(["mustard oversized hoodie"], finder.LIVE_SEARCH_MAX)]  # color not doubled
    assert [p["id"] for p in got] == ["hm:0970819001:mustard-yellow"]        # kids item dropped
    assert got[0]["source"] == "live_search" and store.get("products", got[0]["id"])
    assert finder.live_search(tag)[0]["id"] == got[0]["id"] and len(calls) == 1  # cached
    assert finder.best_matches(tag, got) == got


def test_finder_live_search_keeps_catalog_copy(monkeypatch):
    from app.ai import finder
    from app.commerce import ingest
    from app.store import store

    store.put("products", "hm:111:black", {"id": "hm:111:black", "label": "tagged already", "source": "ingest"})
    raw = [{"id": "111", "title": "Hoodie", "category": "men_hoodies", "color": "Black", "price": 20,
            "model_image": "https://img/h.jpg", "url": "https://www2.hm.com/h"}]
    monkeypatch.setenv("APIFY_TOKEN", "t")
    monkeypatch.setattr(ingest, "fetch_hm", lambda kw, n, token: raw)
    got = finder.live_search({"label": "plain black hoodie zz", "category": "top"})
    assert got[0]["label"] == "tagged already"
    assert store.get("products", "hm:111:black")["source"] == "ingest"


def test_finder_live_search_failure_is_quiet(monkeypatch, caplog):
    from app.ai import finder
    from app.commerce import ingest

    def boom(*a, **k):
        raise RuntimeError("https://api.apify.com/...?token=secret")
    monkeypatch.setenv("APIFY_TOKEN", "secret")
    monkeypatch.setattr(ingest, "fetch_hm", boom)
    assert finder.live_search({"label": "unfindable thing qq"}) == []
    assert "secret" not in caplog.text


def test_finder_no_token_no_live_search(monkeypatch):
    from app.ai import finder
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert finder.live_search({"label": "hoodie"}) == []


NABIL_PRODUCT = {
    "id": "asos:211172667:ivory", "retailer": "asos",
    "name": "Topshop knitted high neck ribbed sweater lace detail in ivory", "price": 96.73,
    "currency": "USD", "sizes": [{"name": "S", "inStock": True}, {"name": "M", "inStock": False}],
    "image_url": "https://images.asos-media.com/x", "url": "https://www.asos.com/prd/211172667",
    "category": "tops", "color": "ivory",
    "tags": {"category": "tops", "color": "ivory", "pattern": "solid", "style": ["cozy", "minimal"],
             "formality": "casual"}}


def test_compat_reads_nabil_schema():
    from app.ai.compat import as_product
    p = as_product(NABIL_PRODUCT)
    assert p["price_usd"] == 96.73 and p["product_url"].endswith("211172667")
    assert p["category"] == "top" and p["colors"] == ["ivory"] and p["sizes"] == ["S"]
    assert p["style_tags"] == ["cozy", "minimal"] and p["formality"] == 2 and p["brand"] == "ASOS"


def test_pair_and_shop_fit_with_nabil_products(client):
    from app.store import store
    store.put("products", NABIL_PRODUCT["id"], NABIL_PRODUCT)
    r = client.post("/pair", json={"user_id": "u_demo", "candidate_product_ids": [NABIL_PRODUCT["id"]]})
    assert r.status_code == 200 and r.json()[0]["id"] == NABIL_PRODUCT["id"]
    r = client.post("/ai/shop-fit", json={"viewer_id": "u_demo", "tagged": [
        {"label": "ivory ribbed sweater"}]})
    assert NABIL_PRODUCT["id"] in {p["id"] for p in r.json()}


def test_products_tag_returns_nabil_tags(client):
    r = client.post("/products/tag", json={"image_url": "https://x/prod.jpg"})
    assert r.status_code == 200
    t = r.json()["tags"]
    assert t["category"] == "tops" and t["formality"] == "casual" and t["style"] == ["streetwear"]


def test_size_endpoint_reads_both_schemas(client):
    from app.store import store
    r = client.post("/size", json={"product_id": "zara-demo-1", "height_cm": 175, "weight_kg": 68})
    assert r.status_code == 200 and r.json()["size"] == "L"  # base M, Zara runs small
    store.put("products", NABIL_PRODUCT["id"], NABIL_PRODUCT)  # sizes S (in stock), M (sold out)
    r = client.post("/size", json={"product_id": NABIL_PRODUCT["id"], "height_cm": 175, "weight_kg": 68})
    assert r.json()["size"] == "S"  # never a sold-out size
    assert client.post("/size", json={"product_id": "nope", "height_cm": 1, "weight_kg": 1}).status_code == 404


def test_fallback_uses_outfit_rules(client, monkeypatch):
    from app.ai import service
    monkeypatch.setattr(service, "text_mock", lambda: True)  # force the no-AI path
    got = service.pair("u_demo", ["hm-demo-1", "zara-demo-1", "mango-demo-1"])
    assert got[-1].product_id == "mango-demo-1"  # over budget goes last
    assert got[0].reason.lower().startswith("goes with your")  # names a closet item now


def test_to_canonical_unifies_both_shapes():
    from app.ai.compat import to_canonical
    from app.models import Product
    a = to_canonical(NABIL_PRODUCT)
    assert a["category"] == "top" and a["price_usd"] == 96.73 and a["product_url"].endswith("211172667")
    assert a["sizes"] == [{"name": "S", "in_stock": True}, {"name": "M", "in_stock": False}]
    old = {"id": "hm-1", "retailer": "hm", "name": "Tee", "brand": "H&M", "category": "top",
           "price_usd": 9.99, "sizes": ["S", "M"], "image_url": "https://i", "product_url": "https://p"}
    b = to_canonical(old)
    assert b["sizes"][0] == {"name": "S", "in_stock": True} and b["currency"] == "USD"
    assert set(a) == set(b) == set(Product.model_fields)


def test_seeded_products_match_schema(client):
    from app.models import Product
    from app.store import store
    for p in store.list("products"):
        if p.get("source") == "seed":
            Product.model_validate(p)


def test_tryon_unavailable_caches_nothing_and_never_makes_a_board(client, monkeypatch, tmp_path):
    import io
    from PIL import Image
    from app.ai import service
    from app.store import store
    # local images so no network is needed
    for name, color in [("body.png", (200, 180, 160)), ("tee.png", (250, 250, 250))]:
        (service.DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (300, 500), color).save(service.DATA_DIR / "uploads" / name)
    store.put("users", "u_board", {"id": "u_board", "display_name": "B",
                                   "body_photo_url": "/static/uploads/body.png"})
    store.put("products", "board-tee", {"id": "board-tee", "retailer": "hm", "name": "Tee", "brand": "H&M",
                                        "category": "top", "price_usd": 10, "image_url": "/static/uploads/tee.png",
                                        "product_url": "https://p"})
    monkeypatch.setattr(service, "mock_mode", lambda k: False)
    monkeypatch.delenv("MOCK_AI", raising=False)

    def no_images(*a, **k):
        raise service.BadModelOutput("429 quota")
    monkeypatch.setattr(service, "gemini_image", no_images)
    import pytest
    with pytest.raises(service.TryOnUnavailable):
        service.try_on("u_board", ["board-tee"], [])
    assert store.list("tryon_cache", user_id="u_board") == []  # nothing cached: next call retries
    assert not list(service.TRYON_DIR.glob("*-board.png")) if service.TRYON_DIR.exists() else True
    r = client.post("/tryon", json={"user_id": "u_board", "product_ids": ["board-tee"]})
    assert r.status_code == 503 and r.json()["detail"]["error"] == "tryon_unavailable"


def test_tryon_without_body_photo_is_unavailable(client):
    r = client.post("/tryon", json={"user_id": "nobody", "product_ids": ["hm-demo-1"]})
    assert r.status_code == 503 and r.json()["detail"]["error"] == "tryon_unavailable"


def test_complete_look_endpoint(client):
    r = client.post("/complete-look", json={"user_id": "u_demo", "product_id": "hm-demo-1"})
    assert r.status_code == 200
    body = r.json()
    cats = {i["category"]: i for i in body["items"]}
    assert cats["bottom"]["source"] == "closet"   # u_demo owns jeans and cargos
    assert cats["shoes"]["source"] == "closet"    # and white sneakers
    assert client.post("/complete-look", json={"user_id": "u_demo", "product_id": "nope"}).status_code == 404


def test_shop_fit_keeps_tag_category_and_color(client):
    # category/color from /ai/tag-fit must survive the API model, or strict matching loses them
    from app.models import FitTag
    t = FitTag(label="ivory ribbed sweater", category="top", color="ivory", style_tags=["minimalist"])
    assert t.model_dump()["category"] == "top" and t.model_dump()["color"] == "ivory"


def test_to_canonical_rejects_unknown_category_and_adds_gallery():
    import pytest
    from app.ai.compat import to_canonical
    base = {"id": "hm:1:black", "retailer": "hm", "name": "Tee", "brand": "H&M", "price_usd": 9.99,
            "sizes": ["S"], "image_url": "https://i/1.jpg", "product_url": "https://p"}
    with pytest.raises(ValueError, match="unknown category"):
        to_canonical({**base, "category": "socks-and-tights"})
    p = to_canonical({**base, "category": "tops"})
    assert p["images"] == [{"url": "https://i/1.jpg", "kind": "product"}] and p["description"] is None
    q = to_canonical({**base, "category": "top", "description": "Soft cotton tee.",
                      "images": [{"url": "https://i/1.jpg"}, {"url": "https://i/m.jpg", "kind": "retailer_model"}]})
    assert [i["kind"] for i in q["images"]] == ["product", "retailer_model"] and q["description"] == "Soft cotton tee."


def test_static_serves_images_not_the_database(client):
    from app.store import store
    store.put("users", "u_secret", {"id": "u_secret"})
    assert client.get("/static/users.json").status_code == 404


def test_shared_key_guard(client, monkeypatch):
    monkeypatch.setenv("API_SHARED_KEY", "s3cret")
    assert client.get("/ai/usage").status_code == 401
    assert client.get("/ai/usage", headers={"X-DTI-Key": "wrong"}).status_code == 401
    assert client.get("/ai/usage", headers={"X-DTI-Key": "s3cret"}).status_code == 200
    assert client.get("/health").status_code == 200  # open
