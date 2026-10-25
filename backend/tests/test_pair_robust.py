"""Recommendation robustness: rules-first shortlist, clash/same-category validators, deterministic ordering,
and the Claude call surviving an SDK that doesn't take `temperature`."""
import sys
import types


def _seed(store, user="u_r"):
    store.put("users", user, {"id": user, "style_text": "streetwear", "price_ranges": {}})
    store.put("closet_items", "jeans", {"id": "jeans", "user_id": user, "image_url": "", "category": "bottom",
                                        "color": "light blue", "pattern": "solid", "style_tags": ["streetwear"],
                                        "formality": 2, "label": "baggy jeans"})
    store.put("closet_items", "tee", {"id": "tee", "user_id": user, "image_url": "", "category": "top",
                                      "color": "white", "pattern": "solid", "style_tags": ["streetwear"],
                                      "formality": 1, "label": "white tee"})
    store.put("closet_items", "belt", {"id": "belt", "user_id": user, "image_url": "", "category": "accessory",
                                       "color": "black", "pattern": "solid", "style_tags": ["business"],
                                       "formality": 5, "label": "black leather belt"})
    base = {"retailer": "hm", "brand": "H&M", "price_usd": 20.0, "image_url": "https://img/p.jpg",
            "product_url": "https://hm.com/p", "pattern": "solid"}
    store.put("products", "hoodie", {**base, "id": "hoodie", "name": "Oversized hoodie", "category": "top",
                                     "colors": ["black"], "style_tags": ["streetwear"], "formality": 1})
    store.put("products", "runtee", {**base, "id": "runtee", "name": "Athletic running tee", "category": "top",
                                     "colors": ["grey"], "style_tags": ["athleisure"], "formality": 1})
    store.put("products", "cargo", {**base, "id": "cargo", "name": "Cargo pants", "category": "bottom",
                                    "colors": ["olive"], "style_tags": ["streetwear"], "formality": 2})


def test_validators_drop_same_category_and_clashing_pairs(tmp_path, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    _seed(store)
    monkeypatch.setattr(service, "ai_json", lambda prompt, **k: [
        {"product_id": "hoodie", "score": 0.9, "reason": "layers over your white tee", "pairs_with": ["tee", "jeans"]},
        {"product_id": "runtee", "score": 0.8, "reason": "sharp with your black leather belt", "pairs_with": ["belt"]},
        {"product_id": "cargo", "score": 0.7, "reason": "goes with your white tee", "pairs_with": ["tee"]}])
    out = {r.product_id: r for r in service.pair("u_r", ["hoodie", "runtee", "cargo"], k=3)}
    assert out["hoodie"].pairs_with == ["jeans"]            # top-with-top dropped, jeans kept
    assert "belt" not in out["runtee"].pairs_with           # athletic tee <-> formal belt is a clash
    assert "belt" not in out["runtee"].reason.lower()       # and the reason built on it is replaced
    assert out["cargo"].pairs_with == ["tee"]


def test_pair_is_deterministic_and_shortlists_for_claude(tmp_path, monkeypatch):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(service, "PAIR_SHORTLIST", 4)
    monkeypatch.setattr(service, "_remember", lambda *a, **k: None)
    _seed(store)
    base = {"retailer": "hm", "brand": "H&M", "price_usd": 20.0, "image_url": "https://img/p.jpg",
            "product_url": "https://hm.com/p", "category": "bottom", "colors": ["black"], "style_tags": ["streetwear"]}
    for i in range(10):
        store.put("products", f"b{i}", {**base, "id": f"b{i}", "name": f"Pants {i}"})
    seen = []

    def fake(prompt, **k):
        import json
        ids = [p["id"] for p in json.loads(prompt.split("Candidates: ", 1)[1].split("\nHARD RULES", 1)[0])]
        seen.append(ids)
        return [{"product_id": i, "score": 0.9 if n == 0 else 0.6, "reason": "goes with your white tee",
                 "pairs_with": ["tee"]} for n, i in enumerate(ids)]

    monkeypatch.setattr(service, "ai_json", fake)
    ids = [f"b{i}" for i in range(10)]
    a = service.pair("u_r", ids, k=2)
    b = service.pair("u_r", ids, k=2)
    assert len(seen[0]) == 4, "Claude sees the rules shortlist, not all 10"
    assert [r.product_id for r in a] == [r.product_id for r in b] and len(a) == 2
    rules = {r["product_id"]: r["score"] for r in service._rules_rank(
        [store.get("products", i) for i in ids], store.list("closet_items", user_id="u_r"), "streetwear")}
    top = a[0]
    llm = 0.9 if top.product_id == seen[0][0] else 0.6
    assert abs(top.score - (0.5 * llm + 0.5 * rules[top.product_id])) < 1e-3   # half Claude, half rules


def test_claude_create_drops_temperature_when_sdk_rejects_it(monkeypatch):
    from app.ai import llm

    calls = []

    class FakeMessages:
        def create(self, **kw):
            calls.append(kw)
            if "extra_body" in kw:
                raise TypeError("Messages.create() got an unexpected keyword argument 'extra_body'")
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text='{"summary": "A tee."}')],
                                         usage=types.SimpleNamespace(input_tokens=1, output_tokens=1))

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda: types.SimpleNamespace(messages=FakeMessages())
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.delenv("CLAUDE_THINKING", raising=False)
    monkeypatch.setattr(llm, "check_budget", lambda kind="claude": None)
    monkeypatch.setattr(llm, "_record_claude", lambda *a: None)
    out = llm.claude_json("Return JSON {summary}", schema=None)
    assert out == {"summary": "A tee."}
    assert len(calls) == 2 and "extra_body" not in calls[1] and calls[1]["thinking"] == {"type": "disabled"}
