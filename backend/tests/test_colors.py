"""colors.py (normalize + duplicate check), its use in finder and closet upload, closet list/delete,
and wishlist saves in style memory."""
import pytest

from app.ai.colors import find_duplicate, is_neutral, normalize_color, same_color


@pytest.mark.parametrize("text,name,family", [
    ("Black", "black", "neutral"),
    ("light wash blue", "light blue", "neutral"),
    ("acid wash", "light blue", "neutral"),
    ("dark wash", "denim", "neutral"),
    ("black wash", "black", "neutral"),      # not denim
    ("washed black", "black", "neutral"),
    ("Ivory", "off-white", "neutral"),
    ("off white", "off-white", "neutral"),
    ("navy blue", "navy", "neutral"),
    ("Dark Grey Melange", "charcoal", "neutral"),
    ("heather grey", "grey", "neutral"),
    ("olive green", "olive", "earth"),
    ("khaki green", "olive", "earth"),
    ("mustard yellow", "mustard", "warm"),
    ("blue green", "teal", "cool"),
    ("Black/Nirvana", "black", "neutral"),   # H&M print names: one real color
    ("black and white stripe", "multicolor", "unknown"),
    ("Tie-Dye", "multicolor", "unknown"),
    ("zzz weird", "zzz weird", "unknown"),
])
def test_normalize(text, name, family):
    c = normalize_color(text)
    assert (c["name"], c["family"]) == (name, family)
    assert c["hex"].startswith("#") and len(c["hex"]) == 7


@pytest.mark.parametrize("bad", ["", "   ", None, 3, ["black"]])
def test_normalize_never_raises(bad):
    assert normalize_color(bad) == {"name": "", "family": "unknown", "hex": "#9E9E9E"}


def test_same_color_and_neutral():
    assert same_color("ivory", "Off White") and same_color("navy", "dark blue")
    assert not same_color("zzz", "zzz")      # unknown colors never count as a match
    assert not same_color("", "")
    assert is_neutral("light wash") and not is_neutral("mustard")


CLOSET = [
    {"id": "a", "category": "bottom", "color": "black", "pattern": "solid", "label": "black wide leg pants"},
    {"id": "b", "category": "top", "color": "white", "label": "white t-shirt"},
    {"id": "c", "category": "top", "color": "white", "label": "white tank"},
]


@pytest.mark.parametrize("item,want", [
    ({"category": "bottom", "color": "black", "label": "wide leg trousers"}, "a"),  # same kind, color via words
    ({"category": "bottom", "color": "jet black", "label": "black wide leg jeans"}, None),  # jeans != pants
    ({"category": "top", "color": "white", "label": "white tee"}, "b"),           # tee == t-shirt
    ({"id": "b", "category": "top", "color": "white", "label": "white tee"}, None),  # itself
    ({"category": "top", "color": "cream", "label": "white tee"}, None),          # different color
    ({"category": "top", "color": "white", "pattern": "striped", "label": "white tee"}, None),
    ({"category": "bottom", "color": "white", "label": "white tee"}, None),       # different category
    ({"category": "top", "color": "white", "label": "white"}, None),              # label is only a color
    ({"category": "top", "color": "white"}, None),
])
def test_find_duplicate(item, want):
    assert find_duplicate(item, CLOSET) == want


def test_find_duplicate_bad_input():
    assert find_duplicate(None, CLOSET) is None
    assert find_duplicate({"category": "top", "color": "white", "label": "tee"}, None) is None
    assert find_duplicate({"category": "top", "color": "white", "label": "tee"}, [None, 3, {}]) is None


def test_finder_matches_normalized_color():
    from app.ai.finder import MIN_SCORE, _query, match_score

    tee = {"name": "Cotton crew tee", "category": "top", "colors": ["off white"]}
    assert match_score({"label": "white tee", "color": "ivory", "category": "top"}, tee) >= MIN_SCORE
    assert match_score({"label": "tee", "color": "mustard", "category": "top"}, tee) < MIN_SCORE
    assert _query({"label": "black hoodie", "color": "Black"}) == "black hoodie"
    assert _query({"label": "hoodie", "color": "black"}) == "black hoodie"


# ---- endpoints: own tmp store per test, no seed, no uploads on disk ----

@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    return TestClient(app)


def test_closet_duplicate_list_delete(client):
    body = {"user_id": "u_dup", "image_url": "https://x/tee1.jpg"}
    first = client.post("/closet/tag", json=body).json()          # mock tagger: always "black tee"
    second = client.post("/closet/tag", json={**body, "image_url": "https://x/tee2.jpg"}).json()
    assert first["duplicate_of"] is None
    assert second["duplicate_of"] == first["id"]
    assert {i["id"] for i in client.get("/closet/u_dup").json()} == {first["id"], second["id"]}
    assert client.delete(f"/closet/someone_else/{second['id']}").status_code == 404
    assert client.delete(f"/closet/u_dup/{second['id']}").json() == {"deleted": second["id"]}
    assert client.delete(f"/closet/u_dup/{second['id']}").status_code == 404
    assert [i["id"] for i in client.get("/closet/u_dup").json()] == [first["id"]]
    assert client.get("/closet/nobody").json() == []


def test_wishlist_saves_reach_style_memory(client):
    from app.ai.memory import style_memory
    from app.store import store

    base = {"retailer": "hm", "brand": "H&M", "category": "top", "price_usd": 20.0,
            "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p"}
    store.put("products", "p1", {**base, "id": "p1", "name": "Saved Corduroy Shirt"})
    store.put("products", "p2", {**base, "id": "p2", "name": "Skipped Neon Tank"})
    store.put("products", "p3", {**base, "id": "p3", "name": "Liked Then Discarded Tee"})
    store.put("wishlist", "u_mem:p1", {"user_id": "u_mem", "product_id": "p1", "saved_at": "2026-10-24T01:00:00Z"})
    store.put("swipes", "u_mem:p2", {"user_id": "u_mem", "product_id": "p2", "action": "discard",
                                     "at": "2026-10-24T01:01:00Z"})
    store.put("wishlist", "u_mem:p3", {"user_id": "u_mem", "product_id": "p3", "saved_at": "2026-10-24T01:02:00Z"})
    store.put("swipes", "u_mem:p3", {"user_id": "u_mem", "product_id": "p3", "action": "discard",
                                     "at": "2026-10-24T01:03:00Z"})   # newest action wins
    text = style_memory("u_mem")
    liked, discarded = text.split("\n")
    assert "Saved Corduroy Shirt" in liked
    assert "Skipped Neon Tank" in discarded and "Liked Then Discarded Tee" in discarded
    assert "Liked Then Discarded Tee" not in liked
