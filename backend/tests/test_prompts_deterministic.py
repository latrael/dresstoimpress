"""Deterministic prompts: temperature 0 + seed for Gemini (Claude: default sampling only), every structured prompt has a
schema that its own EXAMPLE satisfies, bad replies are rejected, and feed reasons never name closet items
the user doesn't own. No network: the SDK clients are faked."""
import json
import re
import sys
import types

import pytest

# app modules are imported lazily: importing app.ai.service at collection time binds the real data dir
# before conftest points the store at a temp one, which breaks the API tests that run after this file.
from app.ai import prompts  # noqa: E402  (prompts has no store side effects)

_FORMATS = {
    "pair": dict(style_text="s", price_ranges="{}", closet_json="[]", memory="", products_json="[]", k=3),
    "vibe": dict(q="rooftop party"),
    "style_from_closet": dict(items_json="[]"),
    "body_scan": dict(height_cm=180, weight_part=""),
    "fit_creator": dict(body="b", fit="f", style_text="s", occasion="o", season="mid", budget=100, must_include="[]",
                        closet_json="[]", products_json="[]", count=2),
    "summary": dict(name="n", category="top", color="c", style="s", label_part="", description="none"),
    "fit_critic": dict(items_json="[]", occasion="none", styles="streetwear"),
}
_TEMPLATES = {"tagger": prompts.TAGGER, "pair": prompts.PAIR, "fit_tagger": prompts.FIT_TAGGER,
              "vibe": prompts.VIBE, "digitize": prompts.DIGITIZE, "style_from_closet": prompts.STYLE_FROM_CLOSET,
              "body_scan": prompts.BODY_SCAN, "fit_creator": prompts.FIT_CREATOR, "summary": prompts.SUMMARY,
              "fit_critic": prompts.FIT_CRITIC}


def _formatted(name: str) -> str:
    t = _TEMPLATES[name]
    return t.format(**_FORMATS[name]) if name in _FORMATS else t


@pytest.mark.parametrize("name", sorted(_TEMPLATES))
def test_every_prompt_formats_and_resolves_its_schema(name):
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    p = _formatted(name)
    assert "{{" not in p, "unbalanced braces after format"
    assert prompts.schema_for(p) is prompts.SCHEMAS[name]
    for line in ("HARD RULES:", "OUTPUT"):
        assert line in p


@pytest.mark.parametrize("name", [n for n in _TEMPLATES if "EXAMPLE:" in _TEMPLATES[n]])
def test_example_in_prompt_satisfies_schema(name):
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    p = _formatted(name)
    example = re.search(r"EXAMPLE: (.*)$", p, re.S).group(1).strip()
    llm.validate_schema(json.loads(example), prompts.SCHEMAS[name])


def test_schema_rejects_bad_enum_missing_key_and_too_many():
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    with pytest.raises(llm.BadModelOutput):
        llm.validate_schema({"label": "x", "category": "hat", "color": "red"}, prompts.SCHEMAS["tagger"])
    with pytest.raises(llm.BadModelOutput):
        llm.validate_schema([{"score": 0.5}], prompts.SCHEMAS["pair"])  # no product_id
    with pytest.raises(llm.BadModelOutput):
        llm.validate_schema({"styles": prompts.STYLES[:4]}, prompts.SCHEMAS["vibe"])
    llm.validate_schema({"error": "not_clothing"}, prompts.SCHEMAS["tagger"])  # the anyOf branch
    llm.validate_schema({"full_body_visible": False, "build": None, "chest_in": None}, prompts.SCHEMAS["body_scan"])


def test_unknown_prompt_has_no_schema_and_passes():
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    assert prompts.schema_for("free text") is None
    llm.validate_schema({"anything": 1}, None)


def test_tryon_v7_and_clean_shot_are_fixed_spec():
    assert prompts.TRYON_VERSION == "v8"
    p = prompts.tryon_prompt(["top"], ["white tee"], build="slim", size="M", boxes=[[0.2, 0.2, 0.8, 0.6]])
    for word in ("PRESERVE EXACTLY", "ORIGINAL", "NEGATIVE", "size M", "20%-80%"):
        assert word in p
    for word in ("#FFFFFF", "NEGATIVE", "no person", "ITEM FIDELITY"):
        assert word in prompts.CLEAN_SHOT
    from app.ai import closet
    assert closet.CLEAN_SHOT is prompts.CLEAN_SHOT


class _Msg:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.usage = types.SimpleNamespace(input_tokens=1, output_tokens=1)


def test_claude_json_sends_no_sampling_params_and_validates(monkeypatch):
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    calls = []
    replies = iter(['{"summary": 5}', '{"summary": "A tee."}'])  # first fails the schema, second passes

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            return _Msg(next(replies))

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda: types.SimpleNamespace(messages=FakeMessages())
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.delenv("CLAUDE_THINKING", raising=False)
    monkeypatch.setattr(llm, "check_budget", lambda kind="claude": None)
    monkeypatch.setattr(llm, "_record_claude", lambda *a: None)
    out = llm.claude_json(_formatted("summary"))
    assert out == {"summary": "A tee."}
    assert len(calls) == 2  # Haiku 5.5 400s on a non-default temperature; the 2026-10-21 API drops all three
    assert not any(k in c for c in calls for k in ("temperature", "top_p", "top_k"))
    assert all(c["thinking"] == {"type": "disabled"} for c in calls)


def test_gemini_json_passes_temperature_and_seed(monkeypatch):
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    cfgs = []

    class Cfg:
        def __init__(self, **kw):
            self.kw = kw
            cfgs.append(kw)

    class FakeModels:
        def generate_content(self, model, contents, config):
            return types.SimpleNamespace(text='{"summary": "A tee."}', usage_metadata=None)

    genai = types.ModuleType("google.genai")
    genai.Client = lambda: types.SimpleNamespace(models=FakeModels())
    gtypes = types.ModuleType("google.genai.types")
    gtypes.GenerateContentConfig = Cfg
    gtypes.ThinkingConfig = lambda **kw: kw
    gtypes.Part = types.SimpleNamespace(from_bytes=lambda **kw: kw)
    google = types.ModuleType("google")
    google.genai = genai
    genai.types = gtypes
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", gtypes)
    monkeypatch.setattr(llm, "_record_gemini_text", lambda *a: None)
    assert llm.gemini_json(_formatted("summary")) == {"summary": "A tee."}
    assert cfgs[0]["temperature"] == 0.0 and cfgs[0]["seed"] == llm.SEED
    assert cfgs[0]["response_mime_type"] == "application/json"


def test_pair_reason_naming_unknown_closet_item_is_replaced():
    from app.ai import llm, service  # noqa: F401
    from app.models import PairResult  # noqa: F401
    closet = [{"id": "c1", "label": "white baby tee", "category": "top", "color": "white"},
              {"id": "c2", "label": "black cargo pants", "category": "bottom", "color": "black"}]
    product = {"id": "p1", "category": "shoes"}
    bad = PairResult(product_id="p1", id="p1", score=0.9, reason="pairs with your black tee", pairs_with=[])
    fixed = service._safe_reason(bad, product, closet)
    assert "black tee" not in fixed.reason and fixed.pairs_with and fixed.pairs_with[0] in {"c1", "c2"}
    good = PairResult(product_id="p1", id="p1", score=0.9, reason="layer it over your white baby tee", pairs_with=["c1"])
    assert service._safe_reason(good, product, closet) is good
    assert "ONLY items they own" in prompts.PAIR and prompts.PAIR_VERSION == "v5"
