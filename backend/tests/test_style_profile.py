"""Style DNA (style_profile.py) and GET/POST /users/{id}/style."""
import pytest

from app.ai.style_profile import style_profile


def P(cat, price, color, tags, label, pattern="solid", formality=2, retailer="hm", sale=None):
    return {"category": cat, "price_usd": price, "sale_price_usd": sale, "colors": [color], "style_tags": tags,
            "pattern": pattern, "formality": formality, "retailer": retailer, "label": label}


LIKED = [P("top", 18, "white", ["streetwear", "minimalist"], "white tee", retailer="uniqlo", sale=12),
         P("top", 45, "mustard", ["streetwear"], "mustard hoodie", pattern="graphic", formality=1),
         P("top", 28, "black", ["minimalist"], "black mock neck", retailer="uniqlo"),
         P("top", 35, "grey", ["streetwear", "minimalist"], "grey sweatshirt"),
         P("bottom", 50, "light blue", ["streetwear"], "light blue jeans"),
         P("bottom", 60, "charcoal", ["streetwear", "minimalist"], "charcoal jeans", retailer="uniqlo")]
DISCARDED = [P("dress", 55, "pink", ["boho"], "pink floral dress", pattern="floral", formality=3),
             P("dress", 65, "pink", ["boho"], "pink wrap dress", pattern="floral", formality=3),
             P("top", 20, "neon green", ["y2k"], "neon tank", formality=1)]
CLOSET = [{"category": "bottom", "color": "black", "style_tags": ["streetwear"], "label": "black cargos"},
          {"category": "shoes", "color": "white", "style_tags": ["minimalist"], "label": "white sneakers"}]


def test_profile_from_swipes_and_closet():
    r = style_profile(LIKED, DISCARDED, CLOSET)
    assert [s["tag"] for s in r["styles"]] == ["streetwear", "minimalist"]   # boho/y2k pushed to 0
    assert r["headline"] == "Streetwear minimalist in clean neutrals"    # mustard is 1/7 < 0.15
    more = style_profile(LIKED + [P("top", 30, "mustard", ["streetwear"], "mustard tee")], DISCARDED, CLOSET)
    assert more["headline"] == "Streetwear minimalist with a mustard streak"  # 2/8 = 0.25
    assert r["palette"][0]["name"] in {"white", "black"} and all(c["family"] != "unknown" for c in r["palette"])
    assert r["formality"] == {"avg": 1.8, "label": "casual"}                  # liked 2,1,2,2,2,2; closet has none
    assert r["price_ranges"]["top"] == [20, 40]      # tops 12 (sale), 28, 35, 45: p20 21.6 -> 20, p80 39 -> 40
    assert r["price_ranges"]["bottom"] == [50, 60]
    assert "dress" not in r["price_ranges"]                                     # discarded never sets budget
    assert r["favorite_retailers"][0] == {"retailer": "hm", "share": 0.5}
    assert r["avoid"] == ["boho", "pink"]
    assert r["sample_size"] == {"liked": 6, "discarded": 3, "closet": 2} and r["confidence"] == "medium"
    assert abs(sum(r["patterns"].values()) - 1) < 0.02


def test_neutral_headline_and_y2k_display():
    liked = [P("top", 20, "black", ["y2k"], "black baby tee"), P("bottom", 30, "white", ["y2k"], "white skirt")]
    assert style_profile(liked)["headline"] == "Y2K in clean neutrals"


@pytest.mark.parametrize("bad", [None, [], "x", [None, 3, {}], [{"price_usd": "12", "colors": 5, "formality": 9.5}]])
def test_empty_or_garbage(bad):
    r = style_profile(bad, bad, bad)
    assert r["headline"] == "Swipe more to find your style" and r["styles"] == [] and r["price_ranges"] == {}
    assert r["formality"] == {"avg": None, "label": "unknown"} and r["confidence"] == "low"


def test_style_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    c = TestClient(app)
    base = {"retailer": "hm", "brand": "H&M", "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p"}
    for i, p in enumerate(LIKED):
        store.put("products", f"p{i}", {**base, **p, "id": f"p{i}", "name": p["label"]})
        store.put("swipes", f"u_s:p{i}", {"user_id": "u_s", "product_id": f"p{i}", "action": "cart",
                                          "at": f"2026-10-24T01:0{i}:00Z"})
    assert c.post("/users/u_s/style/apply").status_code == 200
    r = c.get("/users/u_s/style").json()
    assert r["sample_size"]["liked"] == 6 and r["styles"][0]["tag"] == "streetwear"
    user = store.get("users", "u_s")
    assert user["price_ranges"]["bottom"] == [50, 60] and user["style_text"] == r["headline"]
    assert c.post("/users/nobody/style/apply").status_code == 409
    assert c.get("/users/nobody/style").json()["confidence"] == "low"
