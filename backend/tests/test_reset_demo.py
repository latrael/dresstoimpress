"""scripts/reset_demo.py: clears one user's cart, swipes, wishlist (and optionally orders); keeps everything else."""


def test_reset_demo_only_touches_that_user(tmp_path, monkeypatch):
    from app.store import store
    from scripts import reset_demo

    monkeypatch.setattr(store, "root", tmp_path)
    for u in ("u_demo", "u_other"):
        store.put("swipes", f"{u}:p1", {"user_id": u, "product_id": "p1", "action": "discard"})
        store.put("wishlist", f"{u}:p2", {"user_id": u, "product_id": "p2"})
        store.put("orders", f"o_{u}", {"id": f"o_{u}", "user_id": u})
        store.put("carts", u, {"user_id": u, "items": [{"product_id": "p3", "size": "M", "qty": 1}]})
        store.put("closet_items", f"ci_{u}", {"id": f"ci_{u}", "user_id": u})
    store.put("fitcheck_posts", "fc1", {"id": "fc1", "user_id": "u_other", "likes": ["u_demo", "u_other"],
                                        "comments": [{"user_id": "u_demo", "text": "fire"},
                                                     {"user_id": "u_other", "text": "thx"}]})
    store.put("pair_cache", "abc", {"at": 0, "raw": []})
    store.put("tryon_cache", "t1", {"url": "x"})

    counts = reset_demo.reset("u_demo")
    assert counts == {"swipes": 1, "wishlist": 1, "fitcheck_likes": 1, "fitcheck_comments": 1, "cart_items": 1}
    post = store.get("fitcheck_posts", "fc1")
    assert post["likes"] == ["u_other"] and [c["text"] for c in post["comments"]] == ["thx"]
    assert store.list("swipes", user_id="u_demo") == [] and store.list("wishlist", user_id="u_demo") == []
    assert store.get("carts", "u_demo")["items"] == []
    assert store.get("orders", "o_u_demo") and store.get("closet_items", "ci_u_demo")  # kept
    assert store.get("tryon_cache", "t1") and not store.get("pair_cache", "abc")
    # other users untouched
    assert len(store.list("swipes", user_id="u_other")) == 1 and store.get("carts", "u_other")["items"]

    assert reset_demo.reset("u_demo", orders=True)["orders"] == 1
    assert store.get("orders", "o_u_demo") is None and store.get("orders", "o_u_other")
