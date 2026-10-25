"""Home as reels (sprint-4 §10): photo labels -> hero_image_url, the extra /feed card fields (hero_image_url,
closet_picks, tryon) and the try-on prefetch routes, over Adam's ai.service functions (stubbed or real)."""
import json
import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

IMGS = [{"url": "https://cdn.shopify.com/a.jpg?v=1", "kind": "retailer_model"},
        {"url": "https://cdn.shopify.com/b.jpg?v=2", "kind": "retailer_model"},
        {"url": "https://cdn.shopify.com/c.jpg?v=3", "kind": "retailer_model"}]
CACHE = {"https://cdn.shopify.com/a.jpg": "model", "https://cdn.shopify.com/b.jpg": "product",
         "https://cdn.shopify.com/c.jpg": "detail"}


def _mk(pid, images=(), **kw):
    return {"id": pid, "retailer": "kith", "name": pid, "brand": "Kith", "category": "top", "price_usd": 20.0,
            "colors": ["black"], "sizes": [{"name": "M", "in_stock": True}], "in_stock": True,
            "image_url": "https://cdn.shopify.com/a.jpg?v=1", "images": list(images),
            "product_url": "https://x", "source": "ingest", **kw}


# ---------- photo labels ----------

def test_apply_sets_kinds_and_first_product_photo_as_hero():
    from app.commerce import image_kinds as ik

    p = ik.apply(_mk("p1", IMGS), CACHE)
    assert [i["kind"] for i in p["images"]] == ["retailer_model", "product", "detail"]
    assert p["hero_image_url"] == "https://cdn.shopify.com/b.jpg?v=2"  # keeps the real url (query and all)
    only_models = ik.apply(_mk("p2", IMGS[:1]), CACHE)
    assert only_models["hero_image_url"] is None
    unlabelled = _mk("p3", [{"url": "https://other/x.jpg", "kind": "retailer_model"}], hero_image_url="keep")
    assert ik.apply(unlabelled, CACHE) == unlabelled  # nothing labelled: untouched (a stored hero survives)


def test_single_photo_product_uses_image_url():
    from app.commerce import image_kinds as ik

    p = {**_mk("p4"), "images": [], "image_url": "https://cdn.shopify.com/b.jpg?v=9"}
    assert ik.apply(p, CACHE)["hero_image_url"] == "https://cdn.shopify.com/b.jpg?v=9"


def test_ingest_save_reapplies_cached_labels(tmp_path, monkeypatch):
    from app.commerce import image_kinds, ingest
    from app.store import store
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    monkeypatch.setattr(store, "root", Path(tmp_path))
    monkeypatch.setattr(image_kinds, "load_cache", lambda path=None: CACHE)
    [saved] = ingest.save([_mk("kith:1:black", IMGS)])
    assert saved["hero_image_url"] == "https://cdn.shopify.com/b.jpg?v=2"
    assert store.get("products", "kith:1:black")["images"][2]["kind"] == "detail"


def test_classify_apply_only_writes_snapshot(tmp_path, monkeypatch):
    from app.commerce import image_kinds as ik
    from scripts import classify_images

    seed, cache = tmp_path / "products.json", tmp_path / "image_kinds.json"
    seed.write_text(json.dumps([_mk("kith:1:black", IMGS)]))
    cache.write_text(json.dumps(CACHE))
    monkeypatch.setattr(classify_images, "SEED", seed)
    monkeypatch.setattr(ik, "CACHE", cache)
    assert classify_images.main(["--apply-only"]) == 0
    [p] = json.loads(seed.read_text())
    assert p["hero_image_url"] == "https://cdn.shopify.com/b.jpg?v=2"
    from app.models import Product
    Product.model_validate(p)  # detail/other kinds and hero_image_url are valid schema


# ---------- /feed card fields + prefetch routes ----------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.commerce import router
    from app.main import app
    from app.models import PairResult
    from app.store import store
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    monkeypatch.setattr(store, "root", Path(tmp_path))
    monkeypatch.setattr(router, "pair", lambda uid, cands, k: [
        PairResult(product_id=pid, score=0.9, reason="why") for pid in cands])
    store.put("users", "u_r", {"id": "u_r", "display_name": "R"})
    store.put("products", "a", _mk("a", IMGS, hero_image_url="https://cdn.shopify.com/b.jpg?v=2"))
    store.put("products", "b", {**_mk("b"), "name": "other"})
    return TestClient(app)


PICKS = [{"id": f"ci{i}", "label": f"piece {i}", "category": c, "image_url": f"https://x/{i}.jpg"}
         for i, c in enumerate(["bottom", "shoes", "outerwear", "accessory", "accessory"])]


def _adam(monkeypatch, render=None):
    """Stand-ins for Adam's ai.service functions (ai.feed_tryon), same signatures."""
    from app.ai import service
    calls = {"status": [], "render": []}
    monkeypatch.setattr(service, "closet_picks", lambda uid, p, k=4: PICKS)

    def status(uid, p, picks=None):
        pid = p["id"] if isinstance(p, dict) else p
        calls["status"].append((pid, [c["id"] for c in picks or []]))
        return {"status": "ready", "image_url": f"https://x/tryon-{pid}.png", "mode": "ai"} if pid == "a" \
            else {"status": "pending"}
    monkeypatch.setattr(service, "tryon_status", status)

    def prefetch(uid, items):
        calls["render"].append([p["id"] for p in items])
        return render or {}
    monkeypatch.setattr(service, "prefetch_tryons", prefetch)
    return calls


def test_feed_cards_with_adams_real_functions(client):
    """No stubs: an empty closet -> no picks; no photo of the user -> needs_photo."""
    cards = {c["id"]: c for c in client.get("/feed", params={"user_id": "u_r"}).json()}
    assert cards["a"]["hero_image_url"] == "https://cdn.shopify.com/b.jpg?v=2"
    assert cards["b"]["hero_image_url"] == cards["b"]["image_url"]  # no product-only shot: the primary photo
    assert all(c["closet_picks"] == [] for c in cards.values())
    assert all(c["tryon"]["status"] in ("needs_photo", "none", "unavailable") for c in cards.values())


def test_feed_cards_use_picks_and_tryon_status(client, monkeypatch):
    calls = _adam(monkeypatch)
    cards = {c["id"]: c for c in client.get("/feed", params={"user_id": "u_r"}).json()}
    assert [c["id"] for c in cards["a"]["closet_picks"]] == ["ci0", "ci1", "ci2", "ci3"]  # capped at 4
    assert cards["a"]["tryon"]["status"] == "ready" and cards["b"]["tryon"] == {"status": "pending"}
    assert ("a", ["ci0", "ci1", "ci2", "ci3"]) in calls["status"]  # the try-on of exactly the pieces shown
    seeded = client.get("/feed", params={"user_id": "u_r", "seed": "a"}).json()
    assert seeded[0]["id"] == "a" and seeded[0]["closet_picks"] and "tryon" in seeded[0]


def test_feed_survives_broken_helpers(client, monkeypatch):
    from app.ai import service

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(service, "closet_picks", boom)
    monkeypatch.setattr(service, "tryon_status", boom)
    cards = client.get("/feed", params={"user_id": "u_r"}).json()
    assert cards and all(c["closet_picks"] == [] and c["tryon"] == {"status": "none"} for c in cards)


def test_prefetch_starts_renders_and_answers_statuses(client, monkeypatch):
    calls = _adam(monkeypatch, render={"b": {"status": "pending"}})
    r = client.post("/feed/u_r/tryons", json={"product_ids": ["a", "b", "a"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"a": {"status": "ready", "image_url": "https://x/tryon-a.png", "mode": "ai"},
                        "b": {"status": "pending"}}
    assert calls["render"] == [["a", "b"]]  # de-duped, in order, as products
    assert client.post("/feed/u_r/tryons", json={"product_ids": ["nope"]}).status_code == 404
    assert client.post("/feed/u_r/tryons", json={"product_ids": list("abcdef")}).status_code == 422
    assert client.post("/feed/u_r/tryons", json={"product_ids": []}).status_code == 422


def test_poll_statuses(client, monkeypatch):
    _adam(monkeypatch)
    r = client.get("/feed/u_r/tryons", params={"ids": "a,b,a"})
    assert r.status_code == 200 and list(r.json()) == ["a", "b"]
    assert r.json()["b"] == {"status": "pending"}
    assert client.get("/feed/u_r/tryons", params={"ids": ","}).status_code == 422
    assert client.get("/feed/u_r/tryons", params={"ids": "zzz"}).status_code == 404


def test_model_filenames_override_the_ai(tmp_path):
    from app.commerce import image_kinds as ik

    shot = "https://cdn.shopify.com/files/1-modelinfo-saskia-us2_774a8fe3.jpg"
    assert ik.fixed_kind(shot + "?v=1", "product") == "model"
    assert ik.fixed_kind("https://cdn.shopify.com/files/ARIANWYN-TOP-BLUE.jpg", "product") == "product"
    cache = tmp_path / "kinds.json"
    cache.write_text(json.dumps({shot: "product"}))
    assert ik.load_cache(cache) == {shot: "model"}  # labels cached before the rule are corrected on load
