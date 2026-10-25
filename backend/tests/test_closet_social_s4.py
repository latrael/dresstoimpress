"""Oct 25 (Adam): one outfit per photo (closet upload + Inspo post), reactions, find similar look."""
import io
import os
import random

import pytest

os.environ["MOCK_AI"] = "1"


def _photo(seed: int, w=300, h=400, quality=90) -> bytes:
    """A textured image (dHash needs structure); same seed = same picture."""
    from PIL import Image

    rnd = random.Random(seed)
    im = Image.new("RGB", (12, 16))
    im.putdata([(rnd.randint(0, 255),) * 3 for _ in range(12 * 16)])
    im = im.resize((w, h), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def _garment(label, category, color, box):
    return {"label": label, "category": category, "color": color, "pattern": "solid", "formality": 2,
            "style_tags": [], "brand": None, "box": box}


TWO = [_garment("black cargo pants", "bottom", "black", [0, 0.5, 1, 1]),
       _garment("white baby tee", "top", "white", [0, 0, 1, 0.5])]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.ai import digitize
    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(digitize, "detect", lambda url: [dict(d) for d in TWO])
    for uid in ("u_a", "u_b"):
        store.put("users", uid, {"id": uid, "display_name": uid, "price_ranges": {}, "friends": []})
    return TestClient(app)


def _upload(client, data: bytes, user="u_a"):
    return client.post("/closet/upload", data={"user_id": user, "kind": "outfit"},
                       files=[("files", ("p.jpg", data, "image/jpeg"))]).json()


# ---------- dedupe ----------

def test_dhash_matches_a_resized_recompressed_copy_not_another_photo():
    from app.ai.outfit_dedupe import dhash, distance

    def h(b):
        p = io.BytesIO(b)
        return dhash(p)

    a, a2, b = h(_photo(1)), h(_photo(1, w=600, h=800, quality=60)), h(_photo(2))
    assert distance(a, a2) <= 6 < distance(a, b)


def test_same_photo_uploaded_twice_is_one_outfit(client):
    first = _upload(client, _photo(1))
    again = _upload(client, _photo(1, w=600, h=800, quality=70))
    assert again["added"] == [] and again["outfits"][0]["id"] == first["outfits"][0]["id"]
    assert len(client.get("/closet/u_a/outfits").json()) == 1
    other = _upload(client, _photo(2))
    assert other["outfits"][0]["id"] != first["outfits"][0]["id"]
    assert len(client.get("/closet/u_a/outfits").json()) == 2


def test_closet_upload_then_fitcheck_post_of_the_same_photo_adds_nothing(client):
    from app.ai import closet
    from app.store import store

    first = _upload(client, _photo(3))
    outfit = store.get("outfits", first["outfits"][0]["id"])
    got = closet.add_from_fit("u_a", outfit["photo_url"], None, TWO)
    assert got.get("duplicate") and got["added"] == []
    assert len(store.list("outfits", user_id="u_a")) == 1
    assert store.get("outfits", outfit["id"])["posted"] is True


def test_dedupe_script_merges_old_duplicates_keeping_the_oldest(client):
    from app.ai import outfit_dedupe
    from app.store import store

    first = store.get("outfits", _upload(client, _photo(4))["outfits"][0]["id"])
    # an older-style duplicate made before ingest dedupe existed: another copy of the same photo
    dup = {**first, "id": "of_dup", "photo_url": "http://localhost:8000/static/uploads/dup.jpg",
           "created_at": "2099-01-01T00:00:00+00:00", "source": "fitcheck"}
    store.put("outfits", dup["id"], dup)
    for pid in first["piece_ids"]:
        item = store.get("closet_items", pid)
        item["worn_in"].append({"photo_url": dup["photo_url"], "source": "fitcheck"})
        store.put("closet_items", pid, item)
    assert len(outfit_dedupe.dedupe_user("u_a", dry_run=True)) == 1
    assert len(store.list("outfits", user_id="u_a")) == 2  # dry run changes nothing
    merges = outfit_dedupe.dedupe_user("u_a")
    assert merges == [{"keep": first["id"], "drop": "of_dup", "photo_url": dup["photo_url"]}]
    left = store.list("outfits", user_id="u_a")
    assert [o["id"] for o in left] == [first["id"]] and left[0]["posted"] is True
    for pid in first["piece_ids"]:
        urls = [w["photo_url"] for w in store.get("closet_items", pid)["worn_in"]]
        assert urls == [first["photo_url"]]


# ---------- reactions ----------

def _post(client, user="u_a"):
    return client.post("/fitcheck", json={"user_id": user, "photo_url": "https://x.test/fit.jpg",
                                          "tagged": [{"label": "white baby tee", "category": "top",
                                                      "color": "white"}]}).json()


def test_reactions_one_per_user_and_counts(client):
    post = _post(client)
    pid = post["id"]
    assert post["reactions"] == {} and post["my_reaction"] is None
    r = client.put(f"/fitcheck/{pid}/reaction", json={"user_id": "u_b", "emoji": "🔥"}).json()
    assert r["reactions"] == {"🔥": 1} and r["my_reaction"] == "🔥" and r["like_count"] == 1
    r = client.put(f"/fitcheck/{pid}/reaction", json={"user_id": "u_b", "emoji": "💯"}).json()
    assert r["reactions"] == {"💯": 1}
    client.put(f"/fitcheck/{pid}/reaction", json={"user_id": "u_a", "emoji": "💯"})
    view = client.get(f"/fitcheck/{pid}", params={"user_id": "u_a"}).json()
    assert view["reactions"] == {"💯": 2} and view["my_reaction"] == "💯" and view["like_count"] == 2
    r = client.put(f"/fitcheck/{pid}/reaction", json={"user_id": "u_b", "emoji": None}).json()
    assert r["reactions"] == {"💯": 1} and r["my_reaction"] is None
    assert client.put(f"/fitcheck/{pid}/reaction", json={"user_id": "u_b", "emoji": "🙃"}).status_code == 422


def test_old_like_routes_stay_consistent_with_reactions(client):
    pid = _post(client)["id"]
    client.put(f"/fitcheck/{pid}/like", json={"user_id": "u_b", "liked": True})
    view = client.get(f"/fitcheck/{pid}", params={"user_id": "u_b"}).json()
    assert view["reactions"] == {"😍": 1} and view["my_reaction"] == "😍" and view["liked_by_me"]
    client.put(f"/fitcheck/{pid}/reaction", json={"user_id": "u_b", "emoji": "👀"})
    client.put(f"/fitcheck/{pid}/like", json={"user_id": "u_b", "liked": False})
    view = client.get(f"/fitcheck/{pid}", params={"user_id": "u_b"}).json()
    assert view["reactions"] == {} and view["my_reaction"] is None and view["like_count"] == 0


# ---------- find similar look ----------

def test_similar_puts_own_closet_pieces_first_per_tag(client):
    from app.store import store

    store.put("closet_items", "ci_tee", {"id": "ci_tee", "user_id": "u_b", "image_url": "/static/t.jpg",
                                         "category": "top", "color": "white", "label": "white crew tee"})
    store.put("closet_items", "ci_jeans", {"id": "ci_jeans", "user_id": "u_b", "image_url": "/static/j.jpg",
                                           "category": "bottom", "color": "blue", "label": "blue jeans"})
    store.put("closet_items", "ci_other", {"id": "ci_other", "user_id": "u_a", "image_url": "/static/o.jpg",
                                           "category": "top", "color": "white", "label": "white tee"})
    pid = _post(client)["id"]
    groups = client.get(f"/fitcheck/{pid}/similar", params={"user_id": "u_b"}).json()
    assert len(groups) == 1
    assert groups[0]["tag"]["label"] == "white baby tee"
    assert [c["id"] for c in groups[0]["closet"]] == ["ci_tee"]  # the viewer's own, same type; not jeans
    assert isinstance(groups[0]["products"], list)
    assert client.get("/fitcheck/nope/similar", params={"user_id": "u_b"}).status_code == 404
