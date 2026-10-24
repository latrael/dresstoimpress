import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

PHOTO = "https://picsum.photos/seed/fit/600/800"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data = tmp_path_factory.mktemp("fitcheck")
    backend = os.path.dirname(os.path.dirname(__file__))
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=backend, check=True,
                   env={**os.environ, "DATA_DIR": str(data)})
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        store.root = Path(data)  # store is built at import; point it at this module's fresh data
    store.put("users", "u_a", {"id": "u_a", "display_name": "Ana", "friends": ["u_b"]})
    store.put("users", "u_b", {"id": "u_b", "display_name": "Ben", "friends": ["u_a"]})
    store.put("users", "u_c", {"id": "u_c", "display_name": "Cy", "friends": ["u_x"]})
    return TestClient(app)


def _post(client, uid, **kw):
    r = client.post("/fitcheck", json={"user_id": uid, "photo_url": PHOTO, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_with_tags(client):
    p = _post(client, "u_a", caption="fit", tagged=[{"label": "baggy jeans", "product_id": "hm-demo-1"}])
    assert p["id"].startswith("fc_") and p["visibility"] == "friends"
    assert p["tagged"] == [{"label": "baggy jeans", "retailer": None, "product_id": "hm-demo-1",
                            "closet_item_id": None}]
    assert p["author"] == {"id": "u_a", "display_name": "Ana"}
    assert (p["like_count"], p["liked_by_me"], p["comment_count"]) == (0, False, 0)


def test_create_without_tags_prefills(client):
    p = _post(client, "u_a")
    assert [t["label"] for t in p["tagged"]] == ["light-wash baggy jeans", "white baby tee"]
    assert set(p["tagged"][0]) == {"label", "retailer", "product_id", "closet_item_id"}


def test_tag_failure_never_500s(client, monkeypatch):
    from app.ai import service

    def boom(url):
        raise RuntimeError("model down")
    monkeypatch.setattr(service, "tag_fit", boom)
    assert _post(client, "u_a")["tagged"] == []


def test_create_multipart(client):
    r = client.post("/fitcheck", data={"user_id": "u_b", "caption": "upload"},
                    files={"file": ("fit.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200, r.text
    p = r.json()
    assert "/static/uploads/" in p["photo_url"] and p["caption"] == "upload" and p["tagged"]
    assert client.post("/fitcheck", data={"user_id": "u_b"}).status_code == 422


def test_feed_friends_and_order(client):
    a = _post(client, "u_a", caption="a-latest")
    b = _post(client, "u_b", caption="b-latest")
    c = _post(client, "u_c", caption="c-private")
    ids = [p["id"] for p in client.get("/fitcheck/feed", params={"user_id": "u_a"}).json()]
    assert ids[:2] == [b["id"], a["id"]] and c["id"] not in ids
    assert client.get("/fitcheck/feed", params={"user_id": "u_c"}).json()[0]["id"] == c["id"]
    assert all(p["user_id"] == "u_c" for p in client.get("/fitcheck/feed", params={"user_id": "u_c"}).json())
    everyone = client.get("/fitcheck/feed", params={"user_id": "u_nobody", "limit": 2}).json()
    assert [p["id"] for p in everyone] == [c["id"], b["id"]]  # no friends list -> sees all


def test_privacy_404_and_public(client):
    c = _post(client, "u_c")
    assert client.get(f"/fitcheck/{c['id']}", params={"user_id": "u_a"}).status_code == 404
    assert client.get(f"/fitcheck/{c['id']}", params={"user_id": "u_c"}).status_code == 200
    pub = _post(client, "u_c", visibility="public")
    assert client.get(f"/fitcheck/{pub['id']}", params={"user_id": "u_a"}).status_code == 200
    assert client.get("/fitcheck/fc_missing", params={"user_id": "u_a"}).status_code == 404


def test_like_toggle(client):
    p = _post(client, "u_a")
    url = f"/fitcheck/{p['id']}/like"
    assert client.post(url, json={"user_id": "u_b"}).json() == {"post_id": p["id"], "liked": True, "like_count": 1}
    got = client.get(f"/fitcheck/{p['id']}", params={"user_id": "u_b"}).json()
    assert got["liked_by_me"] and got["like_count"] == 1
    assert client.post(url, json={"user_id": "u_b"}).json()["liked"] is False
    assert client.post("/fitcheck/fc_missing/like", json={"user_id": "u_b"}).status_code == 404


def test_comments(client):
    p = _post(client, "u_a")
    r = client.post(f"/fitcheck/{p['id']}/comments", json={"user_id": "u_b", "text": "  obsessed  "})
    assert r.status_code == 200 and r.json()["text"] == "obsessed" and r.json()["comment_count"] == 1
    got = client.get(f"/fitcheck/{p['id']}", params={"user_id": "u_a"}).json()
    assert got["comment_count"] == 1 and got["comments"][0]["user_id"] == "u_b"
    assert client.post(f"/fitcheck/{p['id']}/comments", json={"user_id": "u_b", "text": "x" * 281}).status_code == 422
    assert client.post(f"/fitcheck/{p['id']}/comments", json={"user_id": "u_b", "text": "   "}).status_code == 422


def test_edit_tags_owner_only(client):
    p = _post(client, "u_a")
    url = f"/fitcheck/{p['id']}/tags"
    new = [{"label": "black cargos", "retailer": "zara"}]
    assert client.patch(url, json={"user_id": "u_b", "tagged": new}).status_code == 403
    r = client.patch(url, json={"user_id": "u_a", "tagged": new})
    assert r.status_code == 200 and r.json()["tagged"][0]["label"] == "black cargos"
    assert client.patch("/fitcheck/fc_missing/tags", json={"user_id": "u_a", "tagged": new}).status_code == 404


def test_shop_returns_products(client, monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)  # no live search from tests
    p = _post(client, "u_a", tagged=[{"label": "baggy jeans", "product_id": "hm-demo-1"}])
    r = client.get(f"/fitcheck/{p['id']}/shop", params={"user_id": "u_b"})
    assert r.status_code == 200
    cards = r.json()
    assert cards and cards[0]["id"] == "hm-demo-1"
    assert all({"reason", "pairs_with", "score", "matched_tag"} <= set(c) for c in cards)
    assert client.get("/fitcheck/fc_missing/shop", params={"user_id": "u_demo"}).status_code == 404
