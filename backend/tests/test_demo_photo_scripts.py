"""Morning photo scripts (load_closet, set_body_photo) and the try-on cache following the body photo."""
import pytest

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


@pytest.fixture
def env(tmp_path, monkeypatch):
    from app.store import store

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(store, "root", data)
    monkeypatch.setattr("app.store.DATA_DIR", data)
    monkeypatch.setenv("PUBLIC_BASE", "https://demo.example")
    photos = tmp_path / "photos"
    photos.mkdir()
    return store, data, photos


def test_load_closet_tags_uploads_and_replaces_seed(env):
    from scripts.load_closet import load_closet

    store, data, photos = env
    (photos / "a.jpg").write_bytes(JPEG)
    (photos / "b.JPEG").write_bytes(JPEG)
    (photos / "notes.txt").write_text("ignore me")
    (photos / ".hidden.jpg").write_bytes(JPEG)
    store.put("closet_items", "ci_seed", {"id": "ci_seed", "user_id": "u_l", "source": "seed", "label": "x",
                                          "category": "top", "color": "black", "image_url": "https://picsum.photos/x"})
    store.put("closet_items", "ci_other", {"id": "ci_other", "user_id": "u_other", "source": "seed", "label": "y",
                                           "category": "top", "color": "black", "image_url": "https://picsum.photos/y"})

    assert load_closet(photos, "u_l", dry_run=True)["added"] == []
    assert store.list("closet_items", user_id="u_l") == [store.get("closet_items", "ci_seed")]

    out = load_closet(photos, "u_l", replace_seed=True)
    assert len(out["added"]) == 2 and out["removed_seed"] == ["ci_seed"]
    items = store.list("closet_items", user_id="u_l")
    assert {i["id"] for i in items} == set(out["added"])
    assert all(i["image_url"].startswith("https://demo.example/static/uploads/") for i in items)
    assert len(list((data / "uploads").iterdir())) == 2
    assert store.get("closet_items", "ci_other")                                  # other users untouched
    second = [i for i in items if i["duplicate_of"]]
    assert len(second) == 1                                                       # mock tagger: same tee twice


def test_load_closet_empty_folder(env):
    from scripts.load_closet import load_closet

    _, _, photos = env
    with pytest.raises(SystemExit):
        load_closet(photos, "u_l")


def test_set_body_photo_and_tryon_cache_follows_it(env):
    from app.ai import service
    from scripts.set_body_photo import set_body_photo

    store, data, photos = env
    store.put("products", "p1", {"id": "p1", "retailer": "hm", "brand": "H&M", "name": "Tee", "category": "top",
                                 "price_usd": 10.0, "image_url": "https://img/p1.jpg", "product_url": "https://hm.com/p1"})
    (photos / "body1.png").write_bytes(b"\x89PNG....")
    url1 = set_body_photo(photos / "body1.png", "u_b")
    assert store.get("users", "u_b")["body_photo_url"] == url1 and url1.endswith(".png")

    _, cached, _ = service.try_on("u_b", ["p1"], [])
    assert cached is False
    assert service.try_on("u_b", ["p1"], [])[1] is True
    set_body_photo(photos / "body1.png", "u_b")                                    # new photo (new file name)
    assert service.try_on("u_b", ["p1"], [])[1] is False                           # old body's try-on not reused


def test_tryon_key_ignores_host_but_not_photo():
    from app.ai.service import _tryon_key

    a = _tryon_key("u", ["p"], [], "https://old.trycloudflare.com/static/uploads/b.jpg")
    b = _tryon_key("u", ["p"], [], "https://new.trycloudflare.com/static/uploads/b.jpg")
    c = _tryon_key("u", ["p"], [], "https://new.trycloudflare.com/static/uploads/other.jpg")
    assert a == b != c


def test_rejects_non_photos(env):
    from scripts.demo_photos import save_upload

    _, _, photos = env
    (photos / "x.txt").write_text("no")
    with pytest.raises(ValueError):
        save_upload(photos / "x.txt")
