"""scripts/warm_demo.py: warms the feed, Fit Check shops and try-ons the demo touches (mock AI here)."""


def test_warm_demo_fills_feed_fitcheck_and_tryons(tmp_path, monkeypatch):
    from app.store import store
    from scripts import warm_demo

    monkeypatch.setattr(store, "root", tmp_path)
    store.put("users", "u_w", {"id": "u_w", "display_name": "W", "price_ranges": {}, "friends": [],
                            "body_photo_url": "https://img/body.jpg"})
    store.put("closet_items", "ci1", {"id": "ci1", "user_id": "u_w", "image_url": "https://img/c.jpg",
                                      "category": "bottom", "color": "light blue", "pattern": "solid",
                                      "style_tags": ["streetwear"], "formality": 2, "label": "baggy jeans"})
    base = {"retailer": "hm", "brand": "H&M", "category": "top", "price_usd": 20.0, "colors": ["black"],
            "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p", "style_tags": ["streetwear"],
            "sizes": ["S", "M"], "in_stock": True, "label": "black tee", "pattern": "solid", "formality": 2}
    for i in range(5):
        store.put("products", f"p{i}", {**base, "id": f"p{i}", "name": f"Tee {i}"})
    store.put("fitcheck_posts", "fc1", {
        "id": "fc1", "user_id": "u_w", "photo_url": "https://img/f.jpg", "caption": "", "visibility": "public",
        "tagged": [{"category": "top", "label": "black tee", "color": "black", "pattern": "solid",
                    "style_tags": ["streetwear"]}],
        "created_at": "2026-10-24T00:00:00Z", "likes": [], "comments": []})

    lines: list[str] = []
    report = warm_demo.warm("u_w", limit=5, tryons=2, out=lines.append)

    assert report["feed_cards"] >= 1 and report["feed_reasons"] == report["feed_cards"]
    assert report["fitcheck_posts"] == 1
    assert report["tryons_ok"] == 2 and report["tryons_failed"] == 0
    assert len(store.list("tryon_cache")) == 2
    assert report["ai_usd"] == 0.0  # mock AI: free
    assert any(line.startswith("feed again") for line in lines)
