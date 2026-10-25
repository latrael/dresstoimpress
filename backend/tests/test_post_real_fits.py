import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

def _png() -> bytes:
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(out, "PNG")
    return out.getvalue()


PNG = _png()


@pytest.fixture()
def client(tmp_path_factory):
    data = tmp_path_factory.mktemp("realfits")
    backend = os.path.dirname(os.path.dirname(__file__))
    env = {**os.environ, "DATA_DIR": str(data)}
    for script in ("scripts.seed_demo", "scripts.seed_fitcheck"):
        subprocess.run([sys.executable, "-m", script], cwd=backend, check=True, env=env, capture_output=True)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import store
    if hasattr(store, "root"):
        store.root = Path(data)
    return TestClient(app)


@pytest.fixture()
def photos(tmp_path):
    for name in ("b.png", "a.jpg", "c.png", "notes.txt"):
        (tmp_path / name).write_bytes(PNG if name != "notes.txt" else b"x")
    (tmp_path / "captions.txt").write_text("first fit\nsecond fit\n")
    return tmp_path


def _feed(client):
    return client.get("/fitcheck/feed", params={"user_id": "u_demo", "limit": 50}).json()


def test_plan_orders_photos_rotates_users_and_reads_captions(photos):
    from scripts.post_real_fits import plan
    jobs = plan(photos, ["u_adam", "u_nabil", "u_ryan"])
    assert [(p.name, u, c) for p, u, c in jobs] == [
        ("a.jpg", "u_adam", "first fit"), ("b.png", "u_nabil", "second fit"), ("c.png", "u_ryan", "")]


def test_posts_photos_with_ai_tags_then_removes_seeds(client, photos):
    from scripts.post_real_fits import run
    assert {p["id"] for p in _feed(client)} >= {"fc_seed_1", "fc_seed_2", "fc_seed_3"}
    assert run(client, photos, ["u_adam", "u_nabil", "u_ryan"]) == 0
    feed = _feed(client)
    assert not any(p["id"].startswith("fc_seed_") for p in feed)
    assert sorted(p["user_id"] for p in feed) == ["u_adam", "u_nabil", "u_ryan"]
    assert all(p["tagged"] and "/static/uploads/" in p["photo_url"] for p in feed)  # AI pre-filled tags
    assert {p["caption"] for p in feed} == {"first fit", "second fit", ""}


def test_dry_run_and_keep_seeds_post_or_delete_nothing(client, photos):
    from scripts.post_real_fits import run
    before = {p["id"] for p in _feed(client)}
    assert run(client, photos, ["u_adam"], dry_run=True) == 0
    assert {p["id"] for p in _feed(client)} == before
    assert run(client, photos, ["u_adam"], keep_seeds=True) == 0
    assert {p["id"] for p in _feed(client)} >= before


def test_failed_upload_keeps_seeds(client, photos):
    from scripts.post_real_fits import run
    (photos / "d.png").write_bytes(b"x" * (10 * 1024 * 1024 + 1))  # over the 10 MB limit -> 413
    assert run(client, photos, ["u_adam"]) == 1
    assert {"fc_seed_1", "fc_seed_2", "fc_seed_3"} <= {p["id"] for p in _feed(client)}


def test_empty_folder(client, tmp_path):
    from scripts.post_real_fits import run
    assert run(client, tmp_path, ["u_adam"]) == 1


def test_delete_post_owner_only(client):
    assert client.delete("/fitcheck/fc_seed_1", params={"user_id": "u_nabil"}).status_code == 403
    r = client.delete("/fitcheck/fc_seed_1", params={"user_id": "u_adam"})
    assert r.status_code == 200 and r.json() == {"post_id": "fc_seed_1", "deleted": True}
    assert client.delete("/fitcheck/fc_seed_1", params={"user_id": "u_adam"}).status_code == 404


def test_clean_strips_exif_gps_and_shrinks(tmp_path):
    from PIL import Image
    from scripts.post_real_fits import MAX_SIDE, clean
    exif = Image.Exif()
    exif[0x8825] = {2: (37.0, 46.0, 30.0)}  # GPSLatitude
    src = tmp_path / "fit.jpg"
    Image.new("RGB", (3000, 2000), "red").save(src, exif=exif)
    assert Image.open(src).getexif().get_ifd(0x8825)
    out = tmp_path / "out.jpg"
    out.write_bytes(clean(src))
    img = Image.open(out)
    assert img.format == "JPEG" and max(img.size) == MAX_SIDE
    assert not img.getexif()


def test_unreadable_photo_is_not_uploaded(client, tmp_path):
    from scripts.post_real_fits import run
    (tmp_path / "fit.heic").write_bytes(b"not an image")
    before = len(_feed(client))
    assert run(client, tmp_path, ["u_nabil"]) == 1
    assert len(_feed(client)) == before
