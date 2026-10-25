"""Friends: handle + friend code per user, mutual add by handle or code, remove, 404 on a bad code."""
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    for uid, name in (("u_adam", "Adam"), ("u_nabil", "Nabil"), ("u_ryan", "Ryan W")):
        store.put("users", uid, {"id": uid, "display_name": name, "price_ranges": {}, "friends": []})
    return TestClient(app)


def test_code_and_handle_are_generated_once(client):
    a = client.get("/users/u_adam/code").json()
    assert a["handle"] == "adam" and a["friend_code"].startswith("NCH-") and len(a["friend_code"]) == 8
    assert a["friends_count"] == 0
    assert client.get("/users/u_adam/code").json()["friend_code"] == a["friend_code"]  # stable
    assert client.get("/users/u_ryan/code").json()["handle"] == "ryan_w"


def test_add_by_handle_is_mutual(client):
    r = client.post("/users/u_adam/friends", json={"handle_or_code": "@Nabil"})
    assert r.status_code == 200 and [f["id"] for f in r.json()] == ["u_nabil"]
    assert [f["id"] for f in client.get("/users/u_nabil/friends").json()] == ["u_adam"]
    assert client.get("/users/u_adam/code").json()["friends_count"] == 1


def test_add_by_code_and_idempotent(client):
    code = client.get("/users/u_ryan/code").json()["friend_code"]
    client.post("/users/u_adam/friends", json={"handle_or_code": code.lower()})
    r = client.post("/users/u_adam/friends", json={"handle_or_code": code[4:]})  # without the NCH- prefix
    assert [f["id"] for f in r.json()] == ["u_ryan"]  # no duplicate
    assert r.json()[0]["handle"] == "ryan_w"


def test_remove_is_mutual(client):
    client.post("/users/u_adam/friends", json={"handle_or_code": "nabil"})
    r = client.delete("/users/u_adam/friends/u_nabil")
    assert r.status_code == 200 and r.json() == []
    assert client.get("/users/u_nabil/friends").json() == []


def test_bad_code_404_and_self_422(client):
    assert client.post("/users/u_adam/friends", json={"handle_or_code": "NCH-ZZZZ"}).status_code == 404
    assert client.post("/users/u_adam/friends", json={"handle_or_code": "adam"}).status_code == 422


def _post(client, uid, visibility):
    r = client.post("/fitcheck", json={"user_id": uid, "photo_url": "https://example.com/p.jpg",
                                       "caption": visibility, "visibility": visibility})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_post_visibility_defaults_to_public(client):
    r = client.post("/fitcheck", json={"user_id": "u_adam", "photo_url": "https://example.com/p.jpg"})
    assert r.json()["visibility"] == "public"


def test_everyone_scope_hides_friends_only_posts_from_non_friends(client):
    _post(client, "u_nabil", "friends")
    _post(client, "u_nabil", "public")
    ids = [p["caption"] for p in client.get("/fitcheck/feed", params={"user_id": "u_ryan"}).json()]
    assert ids == ["public"]  # ryan is not nabil's friend
    assert client.get("/fitcheck/feed", params={"user_id": "u_ryan", "scope": "friends"}).json() == []


def test_friends_see_friends_only_posts_and_own_posts_always_show(client):
    client.post("/users/u_adam/friends", json={"handle_or_code": "nabil"})
    _post(client, "u_nabil", "friends")
    _post(client, "u_adam", "friends")
    caps = {p["user_id"] for p in client.get("/fitcheck/feed", params={"user_id": "u_adam"}).json()}
    assert caps == {"u_nabil", "u_adam"}
    caps = {p["user_id"] for p in client.get("/fitcheck/feed", params={"user_id": "u_adam", "scope": "friends"}).json()}
    assert caps == {"u_nabil", "u_adam"}
    own = {p["user_id"] for p in client.get("/fitcheck/feed", params={"user_id": "u_ryan"}).json()}
    assert own == set()  # ryan: not a friend, sees neither friends-only post
