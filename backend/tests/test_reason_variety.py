"""Feed reasons should not read like one template: the PAIR prompt asks for variety, and the
quality check flags repeated openings and one closet item named on most cards."""


def test_pair_prompt_has_no_copyable_example_and_asks_for_variety():
    from app.ai import prompts

    text = prompts.PAIR.format(style_text="y2k", price_ranges="{}", closet_json="[]", memory="",
                               products_json="[]", k=10)
    assert "black cargo pants" not in text  # the old example Claude copied onto every card
    assert "never start two reasons with the same words" in text
    assert "different closet items" in text
    assert prompts.PAIR_VERSION


def test_variety_warnings_flags_template_reasons():
    from scripts.ai_quality_check import variety_warnings

    same = ["goes with your black cargo pants"] * 6 + ["pairs with your baggy jeans", "layer it over your tee"]
    msgs = variety_warnings(same, ["black cargo pants", "baggy jeans", "white sneakers"])
    assert any("start with 'goes with your'" in m for m in msgs)
    assert any("same closet item ('black cargo pants')" in m for m in msgs)


def test_variety_warnings_quiet_for_varied_reasons():
    from scripts.ai_quality_check import variety_warnings

    varied = ["black on black with your cargo pants", "layer it over your baggy jeans",
              "gives your white sneakers a y2k edge", "only $13 and it works with your jeans",
              "the boxy fit balances your baggy jeans", "date-night ready with your black cargo pants"]
    assert variety_warnings(varied, ["black cargo pants", "baggy jeans", "white sneakers"]) == []


def test_changing_the_prompt_version_starts_a_fresh_ranking(tmp_path, monkeypatch):
    from app.ai import prompts, service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    store.put("closet_items", "ci1", {"id": "ci1", "user_id": "u_v", "image_url": "https://img/c.jpg",
                                      "category": "bottom", "color": "light blue", "pattern": "solid",
                                      "style_tags": ["streetwear"], "formality": 2, "label": "baggy jeans"})
    store.put("products", "p1", {"id": "p1", "retailer": "hm", "brand": "H&M", "name": "Tee", "category": "top",
                                 "price_usd": 20.0, "colors": ["black"], "image_url": "https://img/p.jpg",
                                 "product_url": "https://hm.com/p", "style_tags": ["streetwear"]})
    calls = []
    monkeypatch.setattr(service, "ai_json", lambda prompt, **k: calls.append(1) or [
        {"product_id": "p1", "score": 0.9, "reason": "layer it over your baggy jeans", "pairs_with": ["ci1"]}])
    service.pair("u_v", ["p1"], k=1)
    service.pair("u_v", ["p1"], k=1)
    assert len(calls) == 1  # cached
    monkeypatch.setattr(prompts, "PAIR_VERSION", "test-next")
    service.pair("u_v", ["p1"], k=1)
    assert len(calls) == 2  # new prompt version: no stale reasons from the old one
