"""reason_polish (Gemini draft, reviewed): every feed reason reads the same way, and pair() applies it."""
import pytest

from app.ai.reason_polish import polish_page, polish_reason


@pytest.mark.parametrize("raw, want", [
    ('  "goes with your black cargo pants."  ', "Goes with your black cargo pants"),
    ("reason: y2k tee that pairs with your your baggy jeans!", "Y2K tee that pairs with your baggy jeans"),
    ("Oversized NASCAR tee pushes your baggy jeans into full Y2K energy for weekends with your",
     "Oversized NASCAR tee pushes your baggy jeans into full Y2K energy"),
    ("only $13 & it works with your jeans...", "Only $13 and it works with your jeans"),
    ("“Pink Floyd tee gives your jeans a vintage kick”", "Pink Floyd tee gives your jeans a vintage kick"),
    ("white t-shirt under your\n\tblack   cargos", "White tee under your black cargos"),
    ("Reason – layers over your baggy jeans", "Layers over your baggy jeans"),
    ("reasonably priced, goes with your jeans", "Reasonably priced, goes with your jeans"),
    ("H&M basics that match your NASCAR tee", "H&M basics that match your NASCAR tee"),
    (None, ""), (12, ""), ("   ", ""), ('""', ""),
])
def test_polish_reason(raw, want):
    assert polish_reason(raw) == want


def test_cut_keeps_uncut_words_when_dropping_would_leave_too_few():
    # 3-word cap: "with your" drop would leave 1 word, so the plain cut is kept
    assert polish_reason("pairs with your jeans", max_words=3) == "Pairs with your"


def test_polish_is_idempotent_and_never_lowercases():
    once = polish_reason("NASCAR tee for your Y2K closet.")
    assert once == "NASCAR tee for your Y2K closet" and polish_reason(once) == once


def test_polish_page_keeps_length_and_rejects_non_lists():
    assert polish_page(["goes with your tee.", 5, None]) == ["Goes with your tee", "", ""]
    assert polish_page("nope") == [] and polish_page(None) == []


def test_pair_reasons_come_out_polished(tmp_path, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    store.put("closet_items", "ci1", {"id": "ci1", "user_id": "u_r", "image_url": "https://img/c.jpg",
                                      "category": "bottom", "color": "light blue", "pattern": "solid",
                                      "style_tags": ["streetwear"], "formality": 2, "label": "baggy jeans"})
    base = {"retailer": "hm", "brand": "H&M", "category": "top", "price_usd": 20.0, "colors": ["black"],
            "image_url": "https://img/p.jpg", "product_url": "https://hm.com/p", "style_tags": ["streetwear"]}
    for i in ("p1", "p2", "p3"):
        store.put("products", i, {**base, "id": i, "name": f"Tee {i}"})
    monkeypatch.setattr(service, "ai_json", lambda prompt, **k: [
        {"product_id": "p1", "score": 0.9, "reason": '"y2k tee that layers over your your baggy jeans."',
         "pairs_with": ["ci1"]},
        {"product_id": "p2", "score": 0.8,
         "reason": "black tee that goes well with your baggy jeans for class and weekends",
         "pairs_with": ["ci1"]}])

    out = service.pair("u_r", ["p1", "p2", "p3"], k=3)
    by_id = {r.product_id: r.reason for r in out}
    assert by_id["p1"] == "Y2K tee that layers over your baggy jeans"
    assert by_id["p2"] == "Black tee that goes well with your baggy jeans for class"  # cut at 12, "and" dropped
    assert by_id["p3"] and by_id["p3"][0].isupper()  # rules top-up is polished too
