"""Product.department (from the raw scrapes) + User.shop_for filtering of Home and Discover."""
import copy
import gzip
import json
import os
from collections import Counter
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

from app.commerce.ingest import hm_department, normalize_hm, normalize_uniqlo, uniqlo_department  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures"
SNAPSHOT = json.loads((BACKEND / "seed" / "products.json").read_text())


# ---------- department from the raw scrapes ----------

def _raw(prefix):
    return [it for f in sorted((BACKEND / "seed" / "raw").glob(f"{prefix}*.json.gz"))
            for it in json.loads(gzip.decompress(f.read_bytes()))]


def test_department_rules():
    assert hm_department("ladies_tops_longsleeve") == "women" and hm_department("men_jeans_baggy") == "men"
    assert hm_department("sportswear_women_clothing_hoodiessweatshirts") == "women"
    assert hm_department("sportswear_men_clothing_shorts") == "men"
    assert hm_department("divided_tops") is None and hm_department("kids_boys_tshirts") is None
    assert hm_department("") is None
    assert uniqlo_department({"genderCategory": "UNISEX", "genderName": "MEN"}) == "unisex"
    assert uniqlo_department({"genderName": "women"}) == "women" and uniqlo_department({}) is None


def test_normalizers_set_department():
    hm = {p["id"]: p["department"] for p in normalize_hm(json.loads((FIX / "hm_raw.json").read_text()))}
    assert hm["hm:1234567001:light-denim-blue"] == "men" and hm["hm:1361447006:burgundy-striped"] == "women"
    assert {p["department"] for p in normalize_uniqlo(json.loads((FIX / "uniqlo_raw.json").read_text()))} == \
        {"women"}  # fixture only has genderName


def test_snapshot_backfill_matches_raw():
    by_hm = {str(it["id"]): it["category"] for it in _raw("hm")}
    by_uq = {it["productId"]: it["genderCategory"] for it in _raw("uniqlo")}
    want = {"ladies": "women", "men": "men", "sportswear_women": "women"}
    for p in SNAPSHOT:
        code = p["id"].split(":")[1]
        if p["retailer"] == "hm":
            cat = by_hm[code]
            if cat.startswith(("ladies_", "men_")):  # every men_/ladies_ item is mapped
                assert p["department"] == want[cat.split("_")[0]], p["id"]
            else:
                assert p["department"] == want["_".join(cat.split("_")[:2])], p["id"]
        else:
            assert p["department"] == by_uq[code].lower(), p["id"]
    counts = Counter(p["department"] for p in SNAPSHOT)
    assert counts == {"women": 212, "men": 159, "unisex": 47}  # none left unknown


def test_backfill_only_adds_department():
    from scripts.backfill_department import backfill, departments
    stripped = copy.deepcopy(SNAPSHOT)
    for p in stripped:
        del p["department"]
    out = backfill(stripped, departments())
    assert out == SNAPSHOT and [list(p) for p in out] == [list(p) for p in SNAPSHOT]  # same keys, same order
    assert backfill(copy.deepcopy(SNAPSHOT), departments()) == SNAPSHOT  # idempotent
    assert backfill([{**SNAPSHOT[0], "id": "hm:nope:black"}], departments())[0]["department"] is None


# ---------- the filter ----------

@pytest.mark.parametrize("shop_for, dept, ok", [
    ("both", "men", True), ("both", "women", True), ("both", "unisex", True), ("both", None, True),
    (None, "women", True),  # users saved before shop_for existed
    ("men", "men", True), ("men", "unisex", True), ("men", None, True), ("men", "women", False),
    ("women", "women", True), ("women", "unisex", True), ("women", None, True), ("women", "men", False),
])
def test_dept_filter_matrix(shop_for, dept, ok):
    from app.commerce.router import _dept_ok  # imported late: app.store must not load at collection (test_ai)
    assert _dept_ok({"id": "x", "department": dept}, shop_for) is ok


def test_dept_filter_missing_key_is_unknown():
    from app.commerce.router import _dept_ok
    assert _dept_ok({"id": "x"}, "men") and _dept_ok({"id": "x"}, "women")


# ---------- endpoints ----------

def _mk(pid, dept, category="top", name=None, tags=("y2k",)):
    return {"id": pid, "retailer": "hm", "name": name or pid, "brand": "H&M", "category": category,
            "price_usd": 20.0, "colors": ["blue"], "style_tags": list(tags), "label": "",
            "sizes": [{"name": "M", "in_stock": True}], "in_stock": True, "image_url": "https://x/y.jpg",
            "product_url": "https://x", "source": "ingest", "department": dept}


PRODUCTS = [_mk("m-tee", "men", name="Men Tee"), _mk("w-tee", "women", name="Women Tee"),
            _mk("u-tee", "unisex", name="Unisex Tee"), _mk("n-tee", None, name="Live Tee"),
            _mk("w-jeans", "women", "bottom", "Women Jeans", tags=("boho",)),
            _mk("m-jeans", "men", "bottom", "Men Jeans", tags=("grunge",))]
MEN_OK = {"m-tee", "u-tee", "n-tee", "m-jeans"}
WOMEN_OK = {"w-tee", "u-tee", "n-tee", "w-jeans"}
ALL_IDS = {p["id"] for p in PRODUCTS}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.commerce import router
    from app.main import app
    from app.models import PairResult
    from app.store import store
    if hasattr(store, "root"):
        monkeypatch.setattr(store, "root", Path(tmp_path))  # empty store per test
    for p in PRODUCTS:
        store.put("products", p["id"], p)
    for uid, shop_for in [("u_m", "men"), ("u_w", "women"), ("u_b", "both")]:
        store.put("users", uid, {"id": uid, "display_name": uid, "shop_for": shop_for})
    store.put("users", "u_old", {"id": "u_old", "display_name": "old"})  # saved before shop_for existed
    monkeypatch.setattr(router, "pair", lambda uid, cands, k: [
        PairResult(product_id=pid, score=0.9, reason=f"why {pid}") for pid in cands])
    return TestClient(app)


def _feed_ids(client, uid, **params):
    r = client.get("/feed", params={"user_id": uid, **params})
    assert r.status_code == 200, r.text
    return [c["id"] for c in r.json()]


@pytest.mark.parametrize("uid, want", [("u_m", MEN_OK), ("u_w", WOMEN_OK), ("u_b", ALL_IDS),
                                       ("u_old", ALL_IDS), ("nobody", ALL_IDS)])
def test_feed_respects_shop_for(client, uid, want):
    assert set(_feed_ids(client, uid)) == want


def test_seeded_feed_shows_seed_then_filters(client):
    ids = _feed_ids(client, "u_m", seed="w-jeans")  # a men's shopper opened a women's item (e.g. a shared link)
    assert ids[0] == "w-jeans" and set(ids[1:]) == MEN_OK
    assert set(_feed_ids(client, "u_b", seed="w-jeans")) == ALL_IDS


def test_products_department_param(client):
    def ids(**params):
        return {p["id"] for p in client.get("/products", params={"limit": 100, **params}).json()["items"]}
    assert ids() == ids(department="both") == ALL_IDS
    assert ids(department="men") == MEN_OK and ids(department="women") == WOMEN_OK
    assert ids(q="jeans", department="men") == {"m-jeans"}
    assert client.get("/products", params={"department": "kids"}).status_code == 422


def test_search_respects_shop_for(client):
    def search(uid, q):
        r = client.get("/search", params={"user_id": uid, "q": q}).json()
        return {p["id"] for p in r["similar"]}, {g["id"] for g in r["goes_with"]}
    similar, goes_with = search("u_m", "tee")
    assert similar == {"m-tee", "u-tee", "n-tee"} and "w-jeans" not in goes_with
    assert search("u_w", "jeans")[0] == {"w-jeans"}
    assert search("u_b", "jeans")[0] == {"w-jeans", "m-jeans"}


def test_goes_with_drops_other_department(client, monkeypatch):
    from app.commerce import search
    monkeypatch.setattr(search, "complete_look_route", lambda req: {"items": [
        {"id": "w-jeans", "source": "catalog", "reason": "r"}, {"id": "m-jeans", "source": "catalog", "reason": "r"}]})
    r = client.get("/search", params={"user_id": "u_m", "q": "men tee"}).json()
    assert [g["id"] for g in r["goes_with"]] == ["m-jeans"]


def test_styles_and_trending_respect_shop_for(client):
    for uid in ("t1", "t2"):
        client.put(f"/wishlist/{uid}/items/w-jeans")
    client.put("/wishlist/t1/items/m-jeans")

    def styles(uid):
        return client.get("/search/styles", params={"user_id": uid, "limit": 10}).json()
    men, women, both = styles("u_m"), styles("u_w"), styles("u_b")
    assert men["styles"] == [{"tag": "y2k", "count": 3}, {"tag": "grunge", "count": 1}]
    assert women["styles"] == [{"tag": "y2k", "count": 3}, {"tag": "boho", "count": 1}]
    assert {s["tag"]: s["count"] for s in both["styles"]} == {"y2k": 4, "boho": 1, "grunge": 1}
    assert men["trending"][0]["id"] == "m-jeans" and {p["id"] for p in men["trending"]} == MEN_OK
    assert women["trending"][0]["id"] == "w-jeans" and {p["id"] for p in women["trending"]} == WOMEN_OK
    assert [p["id"] for p in both["trending"][:2]] == ["w-jeans", "m-jeans"]


def test_photo_search_respects_shop_for(client, monkeypatch):
    from app.ai import service
    monkeypatch.setattr(service, "tag_fit", lambda url: [{"label": "tee", "category": "top"}])
    monkeypatch.setattr(service, "shop_fit", lambda uid, tags: [
        {"id": pid, "reason": "r", "score": 0.9, "matched_tag": "tee"} for pid in ("w-tee", "m-tee", "n-tee")])

    def similar(uid):
        r = client.post("/search/photo", data={"user_id": uid},
                        files={"file": ("fit.png", b"\x89PNG fake", "image/png")})
        assert r.status_code == 200, r.text
        return [p["id"] for p in r.json()["similar"]]
    assert similar("u_m") == ["m-tee", "n-tee"]
    assert similar("u_w") == ["w-tee", "n-tee"]
    assert similar("u_b") == ["w-tee", "m-tee", "n-tee"]


def test_shop_for_patch_round_trip_and_onboarding_keeps_it(client):
    assert client.get("/users/u_old").json()["shop_for"] == "both"  # existing users load with the default
    u = client.patch("/users/u_old", json={"shop_for": "men"}).json()
    assert u["shop_for"] == "men" and client.get("/users/u_old").json() == u
    assert set(_feed_ids(client, "u_old")) == MEN_OK
    u = client.post("/onboarding", json={"user_id": "u_old", "text": "y2k, tops under $40"}).json()["user"]
    assert u["shop_for"] == "men"
    assert client.patch("/users/u_old", json={"display_name": "Old"}).json()["shop_for"] == "men"  # not sent: kept
    assert client.patch("/users/u_old", json={"shop_for": "kids"}).status_code == 422
    assert client.patch("/users/u_old", json={"shop_for": "both"}).json()["shop_for"] == "both"
    new = client.post("/onboarding", json={"display_name": "New", "text": ""}).json()["user"]
    assert new["shop_for"] == "both"


def test_onboarding_and_create_accept_shop_for(client):
    u = client.post("/onboarding", json={"user_id": "u_b", "text": "y2k", "shop_for": "women"}).json()["user"]
    assert u["shop_for"] == "women"
    new = client.post("/onboarding", json={"display_name": "Ana", "text": "", "shop_for": "men"}).json()["user"]
    assert new["shop_for"] == "men"
    assert client.post("/users", json={"display_name": "Kai", "shop_for": "women"}).json()["shop_for"] == "women"
    assert client.post("/users", json={"display_name": "Lee"}).json()["shop_for"] == "both"
    assert client.post("/onboarding", json={"text": "", "shop_for": "kids"}).status_code == 422


def test_shop_this_fit_respects_shop_for(client, monkeypatch):
    from app.ai import service
    from app.store import store
    store.put("fitcheck_posts", "fc_x", {"id": "fc_x", "user_id": "u_w", "photo_url": "https://x/p.jpg",
                                         "caption": "", "tagged": [{"label": "tee"}], "visibility": "public",
                                         "created_at": "2026-10-24T00:00:00+00:00", "likes": [], "comments": []})
    monkeypatch.setattr(service, "shop_fit", lambda uid, tags: [
        {"id": pid, "reason": "r"} for pid in ("w-tee", "m-tee", "u-tee", "live:1")])

    def ids(uid):
        r = client.get("/fitcheck/fc_x/shop", params={"user_id": uid})
        assert r.status_code == 200, r.text
        return [p["id"] for p in r.json()]
    assert ids("u_m") == ["m-tee", "u-tee", "live:1"]  # live results (no department) are kept
    assert ids("u_w") == ["w-tee", "u-tee", "live:1"]
    assert ids("u_b") == ["w-tee", "m-tee", "u-tee", "live:1"]
