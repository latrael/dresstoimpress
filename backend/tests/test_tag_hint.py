"""Product-name hint for the tagger (retailer photos of a model in a full outfit)."""


def test_tag_hint_reaches_prompt_and_cache(monkeypatch, tmp_path):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    prompts_sent = []

    def fake_ai_json(prompt, **kwargs):
        prompts_sent.append(prompt)
        return {"label": "white tee", "category": "top", "color": "white", "pattern": "solid",
                "style_tags": ["minimalist"], "formality": 2}

    monkeypatch.setattr(service, "ai_json", fake_ai_json)
    t = service.tag_product("https://img/a.jpg", hint="Regular Fit  T-shirt")
    service.tag_product("https://img/a.jpg", hint="Regular Fit T-shirt")  # same key: cached
    service.tag_product("https://img/a.jpg")                              # no hint: its own key
    assert len(prompts_sent) == 2
    assert 'product "Regular Fit T-shirt"' in prompts_sent[0]
    assert "Regular Fit" not in prompts_sent[1]
    assert t["label"] == "white tee" and t["tags"]


def test_style_tags_limited_to_vocabulary(monkeypatch, tmp_path):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(service, "ai_json", lambda prompt, **k: {
        "label": "black tee", "category": "top", "color": "black", "pattern": "solid", "formality": 2,
        "style_tags": ["Casual", "streetwear", "retro", "Streetwear", "y2k", 7]})
    assert service.tag_product("https://img/v.jpg")["style_tags"] == ["streetwear", "y2k"]
    assert service.tag_closet_item("u_v", "https://img/v2.jpg").style_tags == ["streetwear", "y2k"]
