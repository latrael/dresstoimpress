"""Shop the look, grouped per tagged piece (`grouped=true`): one {tag, products} group per tag in post order,
empty `products` for a tag with no match, up to 6 per tag, the viewer's shop_for respected, flat unchanged.
Mock AI (conftest sets MOCK_AI=1); the finder is stubbed so no catalog or live search runs."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

PHOTO = "https://picsum.photos/seed/grouped/600/800"
TAGS = [
    {"label": "baggy jeans", "category": "bottom", "color": "light blue", "box": [0.2, 0.5, 0.8, 0.95]},
    {"label": "unicorn hat", "category": "accessory", "color": "pink"},  # nothing matches
    {"label": "white tee", "category": "top", "color": "white", "box": [0.3, 0.2, 0.7, 0.5]},
]


def _p(pid, name, category, department=None):
    return {"id": pid, "name": name, "category": category, "colors": ["white"], "retailer": "hm",
            "price_usd": 20.0, "department": department}


def _fake_finder(monkeypatch):
    """7 jeans (dedup keeps distinct names), 2 tees (one women-only), nothing for the hat."""
    from app.ai import service

    jeans = [_p(f"j{i}", f"Baggy Jeans {i}", "bottom") for i in range(7)]
    tees = [_p("t1", "Basic Tee", "top"), _p("t2", "Womens Tee", "top", department="women")]
    by_id = {p["id"]: p for p in jeans + tees}

    def find_products(tag, products, n=3):
        hits = {"baggy jeans": jeans, "white tee": tees}.get(tag["label"], [])
        assert n in (3, 6)
        return hits[:n]

    monkeypatch.setattr("app.ai.finder.find_products", find_products)
    monkeypatch.setattr(service, "get_product", lambda pid: by_id.get(pid))
    monkeypatch.setattr(service, "list_products", lambda: list(by_id.values()))
    return by_id


def test_grouped_keeps_post_order_and_empty_groups(monkeypatch):
    from app.ai import service

    _fake_finder(monkeypatch)
    groups = service.shop_fit_grouped("u_g", TAGS)
    assert [g["tag"]["label"] for g in groups] == ["baggy jeans", "unicorn hat", "white tee"]
    assert groups[0]["tag"] == {"label": "baggy jeans", "category": "bottom", "color": "light blue",
                                "box": [0.2, 0.5, 0.8, 0.95], "product_id": None}
    assert groups[1]["products"] == []
    assert len(groups[0]["products"]) == 6  # per-tag cap raised to 6 for the grouped view
    assert [p["id"] for p in groups[2]["products"]] == ["t1", "t2"]
    for g in groups:
        for p in g["products"]:
            assert {"reason", "pairs_with", "score", "matched_tag"} <= set(p)
            assert p["matched_tag"] == g["tag"]["label"]


def test_flat_default_unchanged(monkeypatch):
    from app.ai import service

    _fake_finder(monkeypatch)
    flat = service.shop_fit("u_g", TAGS)
    assert [p["id"] for p in flat] == ["j0", "j1", "j2", "t1", "t2"]  # still 3 per tag, post order, no groups
    assert all("tag" not in p for p in flat)


def test_grouped_keep_filter_drops_cards_not_tags(monkeypatch):
    from app.ai import service

    _fake_finder(monkeypatch)
    groups = service.shop_fit_grouped("u_g", TAGS, keep=lambda p: p.get("department") != "women")
    assert [p["id"] for p in groups[2]["products"]] == ["t1"]
    assert len(groups) == 3


def test_keep_filters_catalog_before_matching(monkeypatch):
    """6 women's tees outrank 3 men's tees: filtering after the top 6 would leave a men viewer 0 cards."""
    from app.ai import service

    tees = ([_p(f"w{i}", f"Womens Tee {i}", "top", department="women") for i in range(6)]
            + [_p(f"m{i}", f"Mens Tee {i}", "top", department="men") for i in range(3)])
    by_id = {p["id"]: p for p in tees}

    def find_products(tag, products, n=3):  # ranks what it is given: women's tees first
        return sorted(products, key=lambda p: p["department"] != "women")[:n]

    monkeypatch.setattr("app.ai.finder.find_products", find_products)
    monkeypatch.setattr(service, "get_product", lambda pid: by_id.get(pid))
    monkeypatch.setattr(service, "list_products", lambda: list(by_id.values()))
    men = lambda p: p.get("department") in ("men", "unisex", None)  # noqa: E731
    tag = [{"label": "white tee", "category": "top"}]

    assert [p["id"] for p in service.shop_fit_grouped("u_g", tag, keep=men)[0]["products"]] == ["m0", "m1", "m2"]
    assert [p["id"] for p in service.shop_fit("u_g", tag, keep=men)] == ["m0", "m1", "m2"]
    assert [p["id"] for p in service.shop_fit_grouped("u_g", tag)[0]["products"]] == [f"w{i}" for i in range(6)]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data = tmp_path_factory.mktemp("shop_grouped")
    backend = os.path.dirname(os.path.dirname(__file__))
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=backend, check=True,
                   env={**os.environ, "DATA_DIR": str(data)})
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        store.root = Path(data)
    store.put("users", "u_m", {"id": "u_m", "display_name": "Max", "friends": [], "shop_for": "men"})
    return TestClient(app)


def test_route_grouped_respects_shop_for(client, monkeypatch):
    from app.ai import service
    from app.store import store

    by_id = _fake_finder(monkeypatch)
    for p in by_id.values():
        store.put("products", p["id"], p)
    r = client.post("/fitcheck", json={"user_id": "u_m", "photo_url": PHOTO, "tagged": TAGS})
    assert r.status_code == 200, r.text
    post_id = r.json()["id"]

    g = client.get(f"/fitcheck/{post_id}/shop", params={"user_id": "u_m", "grouped": "true"})
    assert g.status_code == 200, g.text
    groups = g.json()
    assert [x["tag"]["label"] for x in groups] == ["baggy jeans", "unicorn hat", "white tee"]
    assert groups[1]["products"] == []
    assert [p["id"] for p in groups[2]["products"]] == ["t1"]  # women-only tee hidden for a men viewer
    assert len(groups[0]["products"]) == 6

    flat = client.get(f"/fitcheck/{post_id}/shop", params={"user_id": "u_m"}).json()
    assert isinstance(flat, list) and flat and "tag" not in flat[0]
    assert [p["id"] for p in flat] == ["j0", "j1", "j2", "t1"]

    ai = client.post("/ai/shop-fit", json={"viewer_id": "u_m", "tagged": TAGS, "grouped": True}).json()
    assert [x["tag"]["label"] for x in ai] == ["baggy jeans", "unicorn hat", "white tee"]
    assert service.shop_tag_summary(TAGS[1])["box"] is None
