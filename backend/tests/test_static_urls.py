"""Stored /static image URLs survive a tunnel change (rebase at startup; fetch from disk for any host)."""
from pathlib import Path


def test_rebase_rewrites_only_our_static_urls(tmp_path, monkeypatch):
    from app.static_urls import rebase_static_urls
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("users", "u1", {"id": "u1", "body_photo_url": "http://localhost:8000/static/uploads/body.jpg"})
    store.put("users", "u2", {"id": "u2", "body_photo_url": None})
    store.put("closet_items", "c1", {"id": "c1", "image_url": "https://old-words.trycloudflare.com/static/uploads/a.png"})
    store.put("closet_items", "c2", {"id": "c2", "image_url": "https://picsum.photos/seed/x/600/800"})
    store.put("tryon_cache", "t1", {"image_url": "https://old.trycloudflare.com/static/tryon/abc.png", "mode": "ai"})
    store.put("fitcheck_posts", "f1", {"id": "f1", "photo_url": "https://image.hm.com/static/uploads/x.jpg?w=1"})

    n = rebase_static_urls("https://new-words.trycloudflare.com/")
    assert n == 3
    assert store.get("users", "u1")["body_photo_url"] == "https://new-words.trycloudflare.com/static/uploads/body.jpg"
    assert store.get("closet_items", "c1")["image_url"] == "https://new-words.trycloudflare.com/static/uploads/a.png"
    assert store.get("tryon_cache", "t1")["image_url"] == "https://new-words.trycloudflare.com/static/tryon/abc.png"
    assert store.get("closet_items", "c2")["image_url"].startswith("https://picsum.photos")   # not ours
    assert store.get("fitcheck_posts", "f1")["photo_url"].startswith("https://image.hm.com")   # query string: not ours
    assert store.get("users", "u2")["body_photo_url"] is None
    assert rebase_static_urls("https://new-words.trycloudflare.com") == 0                    # idempotent


def test_fetch_image_reads_our_files_from_disk_for_any_host(tmp_path, monkeypatch):
    import httpx

    from app.ai import llm
    from app.static_urls import local_static_path

    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "body.jpg").write_bytes(b"\xff\xd8body")
    monkeypatch.setattr("app.store.DATA_DIR", tmp_path)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")))
    for url in ("https://dead-old-tunnel.trycloudflare.com/static/uploads/body.jpg",
                "http://localhost:8000/static/uploads/body.jpg", "/static/uploads/body.jpg"):
        data, mime = llm.fetch_image(url)
        assert data == b"\xff\xd8body" and mime == "image/jpeg"
    assert local_static_path("https://x.com/static/uploads/missing.jpg", tmp_path) is None
    assert local_static_path("https://x.com/static/uploads/../../etc/passwd", tmp_path) is None
    assert local_static_path("https://x.com/other/body.jpg", tmp_path) is None
