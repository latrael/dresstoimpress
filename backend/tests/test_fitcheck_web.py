from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CODE = "table42"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
TAGS = [{"label": "baggy jeans", "category": "bottom", "color": "light blue"},
        {"label": "baby tee", "color": "white"}, {"label": "sneakers", "color": "white"}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.ai import service
    from app.commerce import fitcheck_web
    from app.store import store
    if hasattr(store, "root"):
        monkeypatch.setattr(store, "root", Path(tmp_path))
    monkeypatch.setenv("FITCHECK_EVENT_CODE", CODE)
    monkeypatch.setattr(service, "tag_fit", lambda url: TAGS)
    fitcheck_web._hits.clear()
    store.put("users", "u_secret", {"id": "u_secret", "display_name": "Ana", "friends": []})
    store.put("fitcheck_posts", "fc_app", {"id": "fc_app", "user_id": "u_secret", "photo_url": "https://x.test/a.jpg",
                                           "caption": "app post", "tagged": [], "created_at": "2026-01-01T00:00:00",
                                           "visibility": "public"})
    store.put("fitcheck_posts", "fc_priv", {"id": "fc_priv", "user_id": "u_secret", "photo_url": "https://x.test/b.jpg",
                                            "caption": "friends only", "tagged": [], "created_at": "2026-01-02",
                                            "visibility": "friends"})
    app = FastAPI()
    app.include_router(fitcheck_web.router)
    return TestClient(app)


def _up(c, data=JPEG, ctype="image/jpeg", name="Sam", caption="drip", code=CODE, **kw):
    return c.post(f"/fit/post?code={code}", data={"name": name, "caption": caption},
                  files={"file": ("fit.jpg", data, ctype)}, **kw)


def test_disabled_without_env(client, monkeypatch):
    monkeypatch.delenv("FITCHECK_EVENT_CODE")
    for path in ("/fit", "/fit/wall", "/fit/qr"):
        assert client.get(f"{path}?code={CODE}").status_code == 404
    assert _up(client).status_code == 404


def test_wrong_code(client):
    assert client.get("/fit?code=nope").status_code in (403, 404)
    assert client.get("/fit").status_code in (403, 404)
    assert client.get("/fit/wall?code=nope").status_code in (403, 404)
    assert _up(client, code="nope").status_code in (403, 404)


def test_page_and_qr(client, monkeypatch):
    r = client.get(f"/fit?code={CODE}")
    assert r.status_code == 200 and "Fit Check · dresstoimpress" in r.text
    assert CODE not in r.text and "X-DTI-Key" not in r.text  # page never embeds secrets
    assert "no-referrer" in r.headers["referrer-policy"] and "content-security-policy" in r.headers
    monkeypatch.setenv("PUBLIC_BASE", "https://demo.example.com/")
    q = client.get(f"/fit/qr?code={CODE}")
    assert q.status_code == 200 and f"https://demo.example.com/fit?code={CODE}" in q.text


def test_upload_creates_public_guest_post(client):
    from app.store import store
    r = _up(client)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["photo_url"].startswith("http://localhost:8000/static/uploads/") and j["photo_url"].endswith(".jpg")
    assert j["tagged"][0] == {"label": "baggy jeans", "color": "light blue"}
    gid = r.cookies.get("dti_guest")
    assert gid and gid.startswith("g_") and len(gid) == 10
    post = store.get("fitcheck_posts", j["post_id"])
    assert post["user_id"] == gid and post["visibility"] == "public" and post["tagged"][0]["category"] == "bottom"
    assert store.get("users", gid) == {"id": gid, "display_name": "Sam", "friends": []}
    # same phone keeps its guest id; the name is prefilled on the page
    client.cookies.set("dti_guest", gid, path="/fit")
    r2 = _up(client, name="Sammy")
    assert store.get("fitcheck_posts", r2.json()["post_id"])["user_id"] == gid
    assert 'value="Sammy"' in client.get(f"/fit?code={CODE}").text


def test_tag_failure_still_posts(client, monkeypatch):
    from app.ai import service

    def boom(url):
        raise RuntimeError("model down")
    monkeypatch.setattr(service, "tag_fit", boom)
    r = _up(client)
    assert r.status_code == 200 and r.json()["tagged"] == []


def test_rejects_bad_uploads(client):
    assert _up(client, data=b"%PDF-1.4 not a photo", ctype="image/jpeg").status_code == 415  # magic bytes
    assert _up(client, data=JPEG, ctype="application/pdf").status_code == 415  # content-type
    assert _up(client, data=JPEG + b"\x00" * (8 * 1024 * 1024)).status_code == 413
    assert _up(client, caption="x" * 141).status_code == 422
    assert _up(client, name="n" * 31).status_code == 422


def test_rate_limit_sixth_post(client):
    for _ in range(5):
        assert _up(client, headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}).status_code == 200
    assert _up(client, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
    assert _up(client, headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 200  # other phones unaffected


def test_guest_total_cap(client, monkeypatch):
    monkeypatch.setenv("FITCHECK_GUEST_MAX", "1")
    assert _up(client).status_code == 200
    assert _up(client, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 429


def test_wall_lists_public_without_ids(client):
    pid = _up(client).json()["post_id"]
    r = client.get(f"/fit/wall?code={CODE}&limit=12")
    assert r.status_code == 200
    posts = r.json()
    ids = [p["id"] for p in posts]
    assert ids[0] == pid and "fc_app" in ids and "fc_priv" not in ids
    assert set(posts[0]) == {"id", "photo_url", "caption", "author_name", "tags", "created_at", "photo_w", "photo_h"}
    assert posts[0]["author_name"] == "Sam" and posts[0]["tags"][1] == {"label": "baby tee", "color": "white"}
    assert next(p for p in posts if p["id"] == "fc_app")["author_name"] == "Ana"
    assert "u_secret" not in r.text and "g_" not in r.text


def test_html_stripped_and_escaped(client):
    from app.store import store
    r = _up(client, name='A&B "x" <script>alert(1)</script>', caption="<img src=x onerror=alert(1)>nice a<b")
    j = r.json()
    assert j["author_name"] == 'A&B "x" alert(1)' and j["caption"] == "nice a<b"
    gid = r.cookies.get("dti_guest")
    assert store.get("users", gid)["display_name"] == 'A&B "x" alert(1)'
    client.cookies.set("dti_guest", gid, path="/fit")
    page = client.get(f"/fit?code={CODE}").text
    assert 'value="A&amp;B &quot;x&quot; alert(1)"' in page and "<script>alert" not in page


def test_open_fit_paths_do_not_open_fitcheck():
    from app.main import _is_open
    assert _is_open("/fit") and _is_open("/fit/post") and _is_open("/fit/wall")
    assert not _is_open("/fitcheck/feed") and not _is_open("/fitcheck") and not _is_open("/fitness")


def test_upload_records_photo_size(client):
    import io

    from PIL import Image

    from app.store import store
    buf = io.BytesIO()
    Image.new("RGB", (300, 500), (10, 20, 30)).save(buf, "JPEG")
    j = _up(client, data=buf.getvalue()).json()
    assert (j["photo_w"], j["photo_h"]) == (300, 500)
    post = store.get("fitcheck_posts", j["post_id"])
    assert (post["photo_w"], post["photo_h"]) == (300, 500)
    wall = client.get(f"/fit/wall?code={CODE}").json()
    assert (wall[0]["photo_w"], wall[0]["photo_h"]) == (300, 500)
    assert next(p for p in wall if p["id"] == "fc_app")["photo_w"] is None  # old post: null
