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
