"""Outfit nicknames: automatic from the pieces, editable via PATCH, kept through dedupe."""
import pytest


@pytest.fixture
def names_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    return TestClient(app)




def _p(label, category, color=""):
    return {"id": label.replace(" ", "_"), "label": label, "category": category, "color": color}


def test_auto_name_uses_the_two_defining_pieces_and_stays_short():
    from app.ai.closet import OUTFIT_NAME_MAX, auto_outfit_name

    name = auto_outfit_name([_p("black leather loafers", "shoes", "black"),
                             _p("camel wool overcoat", "outerwear", "camel"),
                             _p("white button-up dress shirt", "top", "white")])
    assert name == "Camel overcoat & shirt"  # statement layer, then the base
    assert len(name) <= OUTFIT_NAME_MAX


def test_auto_name_single_piece_and_empty():
    from app.ai.closet import auto_outfit_name

    assert auto_outfit_name([_p("cream graphic t-shirt", "top", "cream")]) == "Cream t-shirt"
    assert auto_outfit_name([]) == "Outfit"


def test_outfit_view_and_rename(monkeypatch):
    from app.ai import closet as c

    items = {"a": _p("black zip jacket", "outerwear", "black") | {"user_id": "u_n"},
             "b": _p("light blue wide jeans", "bottom", "light blue") | {"user_id": "u_n"}}
    outfits = {"of_1": {"id": "of_1", "user_id": "u_n", "photo_url": "p.jpg", "created_at": "2026",
                        "piece_ids": ["a", "b"], "source": "closet"}}

    class S:
        def get(self, coll, key):
            return (items if coll == "closet_items" else outfits).get(key)

        def put(self, coll, key, doc):
            (items if coll == "closet_items" else outfits)[key] = doc

        def list(self, coll, **w):
            return [o for o in outfits.values() if all(o.get(k) == v for k, v in w.items())]

    monkeypatch.setattr(c, "store", S())
    assert c.outfit_view(outfits["of_1"])["name"] == "Black jacket & jeans"
    assert c.rename_outfit("u_n", "of_1", "  Date   night ")["name"] == "Date night"
    assert c.list_outfits("u_n")[0]["name"] == "Date night"
    assert c.rename_outfit("u_n", "of_1", "")["name"] == "Black jacket & jeans"  # blank restores auto
    assert c.rename_outfit("u_other", "of_1", "x") is None


def test_rename_route(names_client, monkeypatch):
    from app.ai import closet as c

    monkeypatch.setattr(c, "rename_outfit", lambda u, o, n: {"id": o, "user_id": u, "photo_url": "p",
                                                             "created_at": "t", "name": n} if u == "u_n" else None)
    r = names_client.patch("/closet/u_n/outfits/of_1", json={"name": "Gallery day"})
    assert r.status_code == 200 and r.json()["name"] == "Gallery day"
    assert names_client.patch("/closet/u_x/outfits/of_1", json={"name": "y"}).status_code == 404
