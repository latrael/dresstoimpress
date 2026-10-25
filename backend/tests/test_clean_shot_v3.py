"""Clean shot v3: the prompt names the piece, the result is checked, a wrong item never ships; piece dedupe
understands synonyms."""
from __future__ import annotations



def test_prompt_names_the_piece():
    from app.ai import closet, prompts  # noqa: F401
    from app.ai.colors import find_duplicate, label_noun  # noqa: F401

    p = prompts.clean_shot_prompt({"label": "white wired earbuds", "color": "white", "category": "accessory"})
    assert "white wired earbuds" in p and "accessory" in p and "ONLY" in p
    r = prompts.clean_shot_prompt({"label": "white wired earbuds"}, retry=True)
    assert r.startswith("You rendered the wrong item") and "white wired earbuds" in r
    assert prompts.CLEAN_SHOT_VERSION == "v3"
    assert prompts.schema_for(prompts.CLEAN_SHOT_CHECK) == prompts.SCHEMAS["clean_shot_check"]


def test_wrong_item_is_retried_then_dropped(monkeypatch, tmp_path):
    from app.ai import closet, prompts  # noqa: F401
    from app.ai.colors import find_duplicate, label_noun  # noqa: F401

    calls: list[str] = []
    monkeypatch.setattr(closet, "clean_shots_on", lambda: True)
    monkeypatch.setattr(closet, "DATA_DIR", tmp_path)
    monkeypatch.setattr(closet, "gemini_image", lambda prompt, urls: calls.append(prompt) or b"png")
    monkeypatch.setattr(closet, "clean_shot_matches", lambda url, piece: False)
    assert closet.clean_shot("http://x/src.jpg", {"label": "white wired earbuds", "category": "accessory"}) is None
    assert len(calls) == 2 and calls[1].startswith("You rendered the wrong item")
    assert not list((tmp_path / "uploads").glob("*-clean.png"))  # rejected renders are deleted


def test_good_item_passes_first_time(monkeypatch, tmp_path):
    from app.ai import closet, prompts  # noqa: F401
    from app.ai.colors import find_duplicate, label_noun  # noqa: F401

    monkeypatch.setattr(closet, "clean_shots_on", lambda: True)
    monkeypatch.setattr(closet, "DATA_DIR", tmp_path)
    monkeypatch.setattr(closet, "gemini_image", lambda prompt, urls: b"png")
    monkeypatch.setattr(closet, "clean_shot_matches", lambda url, piece: True)
    url = closet.clean_shot("http://x/src.jpg", {"label": "camel wool overcoat", "category": "outerwear"})
    assert url and url.endswith("-clean.png")


def test_check_parses_match(monkeypatch):
    from app.ai import closet, prompts  # noqa: F401
    from app.ai.colors import find_duplicate, label_noun  # noqa: F401

    monkeypatch.setattr("app.ai.llm.ai_json", lambda *a, **k: {"match": False, "seen": "camel wool overcoat"})
    assert closet.clean_shot_matches("http://x/a.png", {"label": "white wired earbuds"}) is False
    monkeypatch.setattr("app.ai.llm.ai_json", lambda *a, **k: {"match": True, "seen": "white earbuds"})
    assert closet.clean_shot_matches("http://x/a.png", {"label": "white wired earbuds"}) is True


def test_synonym_dedupe():
    from app.ai import closet, prompts  # noqa: F401
    from app.ai.colors import find_duplicate, label_noun  # noqa: F401

    assert label_noun("white earbuds with cord") == "earbuds"
    assert label_noun("white wired earphones") == "earbuds"
    kept = [{"id": "a", "category": "accessory", "color": "white", "label": "white wired earbuds"}]
    assert find_duplicate({"id": "b", "category": "accessory", "color": "white",
                           "label": "white earbuds with cord"}, kept) == "a"
    assert find_duplicate({"id": "c", "category": "accessory", "color": "white",
                           "label": "white wired earphones"}, kept) == "a"
    # a different accessory of the same colour is not a duplicate
    assert find_duplicate({"id": "d", "category": "accessory", "color": "white",
                           "label": "white wristwatch"}, kept) is None
