"""pair(): when Claude ranks fewer items than asked, rules-based picks fill the rest (every card has a reason)."""


def test_pair_tops_up_short_claude_answer(tmp_path, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    store.put("closet_items", "ci1", {"id": "ci1", "user_id": "u_p", "image_url": "https://img/c.jpg",
                                      "category": "bottom", "color": "light blue", "pattern": "solid",
                                      "style_tags": ["streetwear"], "formality": 2, "label": "baggy jeans"})
    base = {"retailer": "hm", "brand": "H&M", "category": "top", "price_usd": 20.0, "colors": ["black"],
            "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p", "style_tags": ["streetwear"]}
    ids = [f"p{i}" for i in range(4)]
    for i in ids:
        store.put("products", i, {**base, "id": i, "name": f"Tee {i}"})
    monkeypatch.setattr(service, "ai_json", lambda prompt, **k: [
        {"product_id": "p2", "score": 0.9, "reason": "goes with your baggy jeans", "pairs_with": ["ci1"]},
        {"product_id": "nope", "score": 0.8, "reason": "hallucinated"}])

    out = service.pair("u_p", ids, k=3)
    assert len(out) == 3 and out[0].product_id == "p2" and out[0].reason == "Goes with your baggy jeans"
    assert all(r.reason for r in out) and len({r.product_id for r in out}) == 3
    assert all(r.score < out[0].score for r in out[1:])
    assert "nope" not in {r.product_id for r in out}
