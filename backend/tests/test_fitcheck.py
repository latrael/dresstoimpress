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
                            "closet_item_id": None, "category": None, "color": None, "pattern": None,
                            "style_tags": [], "brand": None, "box": None}]
    assert p["author"] == {"id": "u_a", "display_name": "Ana"}
    assert (p["like_count"], p["liked_by_me"], p["comment_count"]) == (0, False, 0)


def test_create_without_tags_prefills(client):
    p = _post(client, "u_a")
    assert [t["label"] for t in p["tagged"]] == ["light-wash baggy jeans", "white baby tee"]
    t = p["tagged"][0]  # stored as /ai/tag-fit returns it, so shop_fit can match strictly
    assert (t["category"], t["color"], t["pattern"], t["style_tags"]) == ("bottom", "light blue", "solid", ["y2k"])
    assert set(t) == {"label", "retailer", "product_id", "closet_item_id", "category", "color", "pattern",
                      "style_tags", "brand", "box"}


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


def test_feed_is_everyone_newest_first(client):
    a = _post(client, "u_a", caption="a-latest")
    b = _post(client, "u_b", caption="b-latest")
    c = _post(client, "u_c", caption="c-friends-only")  # u_c isn't a friend of u_a: still shown (D4)
    for viewer in ("u_a", "u_c", "u_nobody"):
        ids = [p["id"] for p in client.get("/fitcheck/feed", params={"user_id": viewer}).json()]
        assert ids[:3] == [c["id"], b["id"], a["id"]]
    two = client.get("/fitcheck/feed", params={"user_id": "u_a", "limit": 2}).json()
    assert [p["id"] for p in two] == [c["id"], b["id"]]
    assert two[0]["visibility"] == "friends" and two[0]["author"] == {"id": "u_c", "display_name": "Cy"}


def test_feed_author_filter(client):
    c = _post(client, "u_c", caption="c-own")
    mine = client.get("/fitcheck/feed", params={"user_id": "u_a", "author": "u_c"}).json()
    assert mine[0]["id"] == c["id"] and mine and all(p["user_id"] == "u_c" for p in mine)
    assert client.get("/fitcheck/feed", params={"user_id": "u_a", "author": "u_nobody"}).json() == []


def test_any_post_opens_for_anyone(client):
    c = _post(client, "u_c")  # friends-only, viewer u_a isn't a friend: detail, like, comment all work
    assert client.get(f"/fitcheck/{c['id']}", params={"user_id": "u_a"}).status_code == 200
    assert client.post(f"/fitcheck/{c['id']}/like", json={"user_id": "u_a"}).json()["liked"] is True
    assert client.post(f"/fitcheck/{c['id']}/comments", json={"user_id": "u_a", "text": "fire"}).status_code == 200
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
    assert got["comment_count"] == 1 and [c["text"] for c in got["comments"]] == ["obsessed"]
    assert got["comments"][0]["author"] == {"id": "u_b", "display_name": "Ben"}
    assert client.post(f"/fitcheck/{p['id']}/comments", json={"user_id": "u_b", "text": "x" * 281}).status_code == 422
    assert client.post(f"/fitcheck/{p['id']}/comments", json={"user_id": "u_b", "text": "   "}).status_code == 422


def test_edit_tags_owner_only(client):
    p = _post(client, "u_a")
    url = f"/fitcheck/{p['id']}/tags"
    new = [{"label": "black cargos", "retailer": "zara", "category": "bottom", "color": "black",
            "style_tags": ["streetwear"]}]
    assert client.patch(url, json={"user_id": "u_b", "tagged": new}).status_code == 403
    r = client.patch(url, json={"user_id": "u_a", "tagged": new})
    t = r.json()["tagged"][0]
    assert r.status_code == 200 and (t["label"], t["category"], t["color"]) == ("black cargos", "bottom", "black")
    assert t["style_tags"] == ["streetwear"]
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


def test_seed_tags_carry_product_fields(tmp_path):
    from app.store import JsonStore  # own instance on its own dir: the shared store is untouched
    backend = os.path.dirname(os.path.dirname(__file__))
    env = {**os.environ, "DATA_DIR": str(tmp_path)}
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=backend, check=True, env=env)
    s = JsonStore(tmp_path)
    s.put("products", "hm:1:blue", {"id": "hm:1:blue", "retailer": "hm", "name": "Baggy Jeans", "brand": "H&M",
                                    "category": "bottom", "colors": ["light blue", "blue"], "pattern": "solid",
                                    "style_tags": ["y2k"], "in_stock": True, "source": "ingest"})
    seed = lambda: subprocess.run([sys.executable, "-m", "scripts.seed_fitcheck"], cwd=backend, check=True,
                                  env=env, capture_output=True)
    seed()
    post = s.get("fitcheck_posts", "fc_seed_1")
    s.put("fitcheck_posts", "fc_seed_1", {**post, "likes": ["u_b"], "comments": [{"id": "c1", "text": "hi"}]})
    seed()  # re-run keeps likes and comments
    post = s.get("fitcheck_posts", "fc_seed_1")
    assert post["likes"] == ["u_b"] and post["comments"][0]["id"] == "c1"
    jeans = post["tagged"][0]
    assert (jeans["product_id"], jeans["category"], jeans["color"], jeans["pattern"], jeans["style_tags"],
            jeans["brand"]) == ("hm:1:blue", "bottom", "light blue", "solid", ["y2k"], "H&M")
    assert all(t["category"] for t in post["tagged"])
    assert post["tagged"][1]["color"] is None  # seed products have no colours


def _img(w, h, fmt="PNG", orientation=None):
    import io

    from PIL import Image
    buf, im = io.BytesIO(), Image.new("RGB", (w, h), (200, 80, 120))
    if orientation:
        exif = im.getexif()
        exif[0x0112] = orientation
        im.save(buf, fmt, exif=exif)
    else:
        im.save(buf, fmt)
    return buf.getvalue()


def test_put_like_is_idempotent(client):
    p = _post(client, "u_a")
    url = f"/fitcheck/{p['id']}/like"
    on = {"post_id": p["id"], "liked": True, "like_count": 1}
    assert client.put(url, json={"user_id": "u_b", "liked": True}).json() == on
    assert client.put(url, json={"user_id": "u_b", "liked": True}).json() == on  # retry: no double like
    assert client.put(url, json={"user_id": "u_c", "liked": True}).json()["like_count"] == 2
    got = client.get(f"/fitcheck/{p['id']}", params={"user_id": "u_b"}).json()
    assert got["liked_by_me"] and got["like_count"] == 2 and got["likes"] == ["u_b", "u_c"]
    off = {"post_id": p["id"], "liked": False, "like_count": 1}
    assert client.put(url, json={"user_id": "u_b", "liked": False}).json() == off
    assert client.put(url, json={"user_id": "u_b", "liked": False}).json() == off  # retry: no double unlike
    assert client.put(url, json={"user_id": "u_a", "liked": False}).json()["like_count"] == 1  # never liked
    assert client.post(url, json={"user_id": "u_b"}).json()["liked"] is True  # old toggle still works
    assert client.put(url, json={"user_id": "u_b"}).status_code == 422
    assert client.put("/fitcheck/fc_missing/like", json={"user_id": "u_b", "liked": True}).status_code == 404


def test_comments_paged(client):
    p = _post(client, "u_a")
    url = f"/fitcheck/{p['id']}/comments"
    ids = []
    for i in range(5):
        r = client.post(url, json={"user_id": "u_b" if i % 2 else "u_c", "text": f"c{i}"}).json()
        assert r["author"] == ({"id": "u_b", "display_name": "Ben"} if i % 2 else {"id": "u_c", "display_name": "Cy"})
        ids.append(r["id"])
    page = client.get(url, params={"user_id": "u_a", "limit": 2}).json()
    assert [c["text"] for c in page["comments"]] == ["c3", "c4"]  # newest page, oldest -> newest
    assert page["next_before"] == ids[3] and page["comment_count"] == 5 and page["post_id"] == p["id"]
    c = page["comments"][0]
    assert set(c) == {"id", "user_id", "author", "text", "created_at"}
    assert c["author"] == {"id": "u_b", "display_name": "Ben"} and c["id"] == ids[3]
    page = client.get(url, params={"user_id": "u_a", "limit": 2, "before": page["next_before"]}).json()
    assert [c["text"] for c in page["comments"]] == ["c1", "c2"] and page["next_before"] == ids[1]
    page = client.get(url, params={"user_id": "u_a", "limit": 2, "before": page["next_before"]}).json()
    assert [c["text"] for c in page["comments"]] == ["c0"] and page["next_before"] is None  # the end
    full = client.get(url, params={"user_id": "u_a"}).json()  # default 20: all 5, nothing older
    assert [c["id"] for c in full["comments"]] == ids and full["next_before"] is None
    assert client.get(url, params={"user_id": "u_a", "before": ids[0]}).json()["comments"] == []
    # limit is kept to 1..100
    assert len(client.get(url, params={"user_id": "u_a", "limit": 0}).json()["comments"]) == 1
    assert len(client.get(url, params={"user_id": "u_a", "limit": 500}).json()["comments"]) == 5
    assert client.get(url, params={"user_id": "u_a", "before": "c_nope"}).status_code == 422
    assert client.get("/fitcheck/fc_missing/comments", params={"user_id": "u_a"}).status_code == 404


def test_post_view_comment_preview(client):
    from app.store import store

    def views(pid):  # feed + detail views of one post
        feed = client.get("/fitcheck/feed", params={"user_id": "u_a", "limit": 100}).json()
        return [next(v for v in feed if v["id"] == pid), client.get(f"/fitcheck/{pid}", params={"user_id": "u_a"}).json()]

    p = _post(client, "u_a")
    assert p["comments"] == [] and p["comment_count"] == 0  # create
    assert all(v["comments"] == [] and v["comment_count"] == 0 for v in views(p["id"]))
    url = f"/fitcheck/{p['id']}/comments"
    ids = [client.post(url, json={"user_id": "u_b" if i % 2 else "u_c", "text": f"c{i}"}).json()["id"] for i in range(5)]
    for v in views(p["id"]):
        assert v["comment_count"] == 5 and [c["id"] for c in v["comments"]] == ids[3:]  # 2 newest, oldest -> newest
        assert v["comments"] == client.get(url, params={"user_id": "u_a", "limit": 2}).json()["comments"]  # same shape as the page
        assert [c["author"]["display_name"] for c in v["comments"]] == ["Ben", "Cy"]
    tags = client.patch(f"/fitcheck/{p['id']}/tags", json={"user_id": "u_a", "tagged": []}).json()
    assert tags["comment_count"] == 5 and [c["id"] for c in tags["comments"]] == ids[3:]
    assert len(store.get("fitcheck_posts", p["id"])["comments"]) == 5  # stored list untouched
    assert len(client.get(url, params={"user_id": "u_a"}).json()["comments"]) == 5  # paged route still has all

    one = _post(client, "u_a")
    client.post(f"/fitcheck/{one['id']}/comments", json={"user_id": "u_b", "text": "solo"})
    for v in views(one["id"]):
        assert v["comment_count"] == 1 and [(c["text"], c["author"]["id"]) for c in v["comments"]] == [("solo", "u_b")]


def test_comments_page_over_100(client):
    from app.store import store
    p = _post(client, "u_a")
    post = store.get("fitcheck_posts", p["id"])
    post["comments"] = [{"id": f"c{i}", "user_id": "u_gone", "text": str(i), "created_at": f"t{i:03d}"}
                        for i in range(150)]
    store.put("fitcheck_posts", p["id"], post)
    page = client.get(f"/fitcheck/{p['id']}/comments", params={"user_id": "u_a", "limit": 1000}).json()
    assert len(page["comments"]) == 100 and page["comments"][0]["id"] == "c50" and page["next_before"] == "c50"
    assert page["comments"][0]["author"] == {"id": "u_gone", "display_name": "u_gone"}  # unknown user: id as name


def test_photo_size_on_upload(client):
    r = client.post("/fitcheck", data={"user_id": "u_b"}, files={"file": ("fit.png", _img(300, 500), "image/png")})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["photo_w"], p["photo_h"]) == (300, 500)
    got = client.get(f"/fitcheck/{p['id']}", params={"user_id": "u_a"}).json()
    assert (got["photo_w"], got["photo_h"]) == (300, 500)
    feed = client.get("/fitcheck/feed", params={"user_id": "u_a"}).json()
    assert (feed[0]["id"], feed[0]["photo_w"], feed[0]["photo_h"]) == (p["id"], 300, 500)
    # a phone JPEG stored sideways with EXIF "rotate 90": sized as it displays (upright)
    r = client.post("/fitcheck", data={"user_id": "u_b"},
                    files={"file": ("fit.jpg", _img(500, 300, "JPEG", orientation=6), "image/jpeg")})
    assert (r.json()["photo_w"], r.json()["photo_h"]) == (300, 500)


def test_photo_size_null_for_urls_and_old_posts(client):
    from app.store import store
    p = _post(client, "u_a")
    assert (p["photo_w"], p["photo_h"]) == (None, None)  # external URL: never downloaded
    bad = client.post("/fitcheck", data={"user_id": "u_b"}, files={"file": ("fit.png", b"\x89PNG fake", "image/png")})
    assert (bad.json()["photo_w"], bad.json()["photo_h"]) == (None, None)  # unreadable upload still posts
    old = {"id": "fc_old", "user_id": "u_a", "photo_url": PHOTO, "caption": "", "tagged": [],
           "created_at": "2026-01-01T00:00:00", "likes": [], "comments": [], "visibility": "friends"}
    store.put("fitcheck_posts", "fc_old", old)
    got = client.get("/fitcheck/fc_old", params={"user_id": "u_a"}).json()
    assert (got["photo_w"], got["photo_h"]) == (None, None)
    store.delete("fitcheck_posts", "fc_old")


def test_json_post_can_send_its_photo_size(client):
    body = {"user_id": "u_a", "photo_url": PHOTO, "caption": "", "tagged": [{"label": "tee"}]}
    p = client.post("/fitcheck", json={**body, "photo_w": 1080, "photo_h": 1350}).json()
    assert (p["photo_w"], p["photo_h"]) == (1080, 1350)
    half = client.post("/fitcheck", json={**body, "photo_w": 1080}).json()
    assert (half["photo_w"], half["photo_h"]) == (None, None)  # both or neither
    assert client.post("/fitcheck", json={**body, "photo_w": 0, "photo_h": 10}).status_code == 422


def test_feed_scope_friends(client):
    """scope=friends: the viewer's friends' posts + their own; everyone (default) is unchanged (Adam's #99 ask)."""
    a, b, c = _post(client, "u_a"), _post(client, "u_b"), _post(client, "u_c")
    ids = lambda r: {p["id"] for p in r.json()}  # noqa: E731
    everyone = ids(client.get("/fitcheck/feed", params={"user_id": "u_a", "limit": 100}))
    assert {a["id"], b["id"], c["id"]} <= everyone
    friends = ids(client.get("/fitcheck/feed", params={"user_id": "u_a", "scope": "friends", "limit": 100}))
    assert {a["id"], b["id"]} <= friends and c["id"] not in friends  # Ben is a friend, Cy isn't
    assert all(p["user_id"] in ("u_a", "u_b") for p in
               client.get("/fitcheck/feed", params={"user_id": "u_a", "scope": "friends", "limit": 100}).json())
    lone = client.get("/fitcheck/feed", params={"user_id": "u_nobody", "scope": "friends", "limit": 100}).json()
    assert lone == []  # no friends, no posts of your own
    assert client.get("/fitcheck/feed", params={"user_id": "u_a", "scope": "mutuals"}).status_code == 422
