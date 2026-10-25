"""Catalog stage 2 extras (sprint-2 A7/B4/B5): Product.summary + the department fallback in tag_catalog."""
import pytest


def _p(pid="hm:1:blue", **kw) -> dict:
    base = {"id": pid, "retailer": "hm", "name": "Baggy Jeans", "brand": "H&M", "category": "bottom",
            "price_usd": 29.99, "colors": ["light denim blue"], "sizes": [{"name": "32", "in_stock": True}],
            "image_url": "https://img/j.jpg", "product_url": "https://www2.hm.com/en_us/productpage.1.html",
            "style_tags": ["streetwear"], "label": "light-wash baggy jeans", "source": "ingest"}
    return {**base, **kw}


@pytest.fixture
def ai(monkeypatch, tmp_path):
    """Store in tmp, AI "on" but answered by a fake; returns the list of prompts sent."""
    from app.ai import service
    from app.store import store

    from scripts import tag_catalog

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "text_mock", lambda: False)
    monkeypatch.setattr(tag_catalog, "text_mock", lambda: False)
    sent = []

    def fake_ai_json(prompt, **kwargs):
        sent.append(prompt)
        if "fashion cataloguer" in prompt:
            return {"label": "baggy jeans", "category": "bottom", "color": "blue", "pattern": "solid",
                    "style_tags": ["streetwear"], "formality": 2, "department": "men"}
        if 'Retailer description: none' in prompt:
            return {"summary": "A light-wash baggy jean with a relaxed, streetwear fit."}
        return {"summary": "Loose-fit jeans in soft cotton denim. Sits low with a wide leg. Machine wash cold."}

    monkeypatch.setattr(service, "ai_json", fake_ai_json)
    return sent


# ---------- summary ----------

def test_summary_condenses_description_to_two_sentences(ai):
    from app.ai.service import summarize_product

    s = summarize_product(_p(description="Loose-fit jeans in soft cotton denim. Sits low on the waist. Wide leg."))
    assert s == "Loose-fit jeans in soft cotton denim. Sits low with a wide leg."
    assert len(s) <= 160 and "Loose-fit jeans in soft cotton denim" in ai[-1]


def test_summary_without_description_is_a_one_liner_from_attributes(ai):
    from app.ai.service import summarize_product

    s = summarize_product(_p(description=None))
    assert s == "A light-wash baggy jean with a relaxed, streetwear fit."
    assert "Retailer description: none" in ai[-1] and "streetwear" in ai[-1] and "Baggy Jeans" in ai[-1]


def test_summary_cached_per_product_and_version(ai):
    from app.ai import prompts
    from app.ai.service import summarize_product
    from app.store import store

    p = _p()
    summarize_product(p)
    summarize_product(p)
    assert len(ai) == 1                              # second call is a cache hit
    assert store.get("summary_cache", f"sum{prompts.SUMMARY_VERSION}-{p['id']}")
    summarize_product(_p(pid="hm:2:black"))
    assert len(ai) == 2                              # another product: its own call


def test_summary_rules_fallback_when_ai_off(monkeypatch, tmp_path):
    from app.ai import service
    from app.store import store

    monkeypatch.setattr(store, "root", tmp_path)
    monkeypatch.setattr(service, "ai_json", lambda *a, **k: pytest.fail("AI must not be called"))
    s = service.summarize_product(_p())  # conftest: MOCK_AI=1
    assert s == "A light denim blue light-wash baggy jeans with a streetwear feel."
    assert service.rules_summary(_p(label="", style_tags=[], colors=[])) == "A baggy jeans for everyday bottom wear."
    assert service.summarize_product(_p()) == service.rules_summary(_p())


def test_summary_clipped_to_two_sentences_and_160_chars(ai, monkeypatch):
    from app.ai import service

    long = "This oversized hoodie is made from a heavy brushed cotton blend with a double layer hood and a " \
           "kangaroo pocket for a warm relaxed layered look all winter long and then some more words here"
    monkeypatch.setattr(service, "ai_json", lambda *a, **k: {"summary": long + ". Two. Three. Four."})
    s = service.summarize_product(_p(pid="hm:9:x"))
    assert len(s) <= 160 and s.endswith("…") and "Three" not in s
    assert service._clip_summary("One. Two. Three.") == "One. Two."
    from app.models import Product
    assert Product(**{k: v for k, v in _p(summary=s).items()}).summary == s


# ---------- department ----------

def test_department_rules_from_name_and_url():
    from app.ai.service import department_from_text as d

    assert d("Women's Ribbed Tank") == "women"
    assert d("Ladies slim jeans") == "women"
    assert d("Floral midi dress") == "women"
    assert d("Men's Regular Fit T-shirt") == "men"
    assert d("Mens Oversized Hoodie") == "men"
    assert d("Hoodie", "https://www.uniqlo.com/us/en/men/tops/hoodie") == "men"
    assert d("Tank", None, "ladies_tops_tanks") == "women"
    assert d("Tank", None, "men_tshirtstanks") == "men"
    assert d("Women's wrap blouse", "https://x/men/") == "women"   # women's words win
    assert d("Oversized Hoodie", "https://www2.hm.com/en_us/productpage.1.html") is None
    assert d("Slim Fit Dress Shirt") is None                        # men's "dress shirt" isn't a dress


def test_tagger_department_used_only_when_null(ai):
    from scripts.tag_catalog import tag_one

    q, err = tag_one(_p(label="", department=None, name="Baggy Jeans"))
    assert err is None and q["department"] == "men" and q["label"] == "baggy jeans"   # from the tagger
    q, _ = tag_one(_p(label="", department="women"))
    assert q["department"] == "women"                                                  # never overwritten
    q, _ = tag_one(_p(label="", department=None, name="Ladies Baggy Jeans"))
    assert q["department"] == "women"                                                  # rules beat the tagger
    q, _ = tag_one(_p(department="unisex"))
    assert q["department"] == "unisex" and q["label"] == "light-wash baggy jeans"      # already tagged: no re-tag
    assert q["summary"]


def test_tag_product_validates_department(ai, monkeypatch):
    from app.ai import service

    assert service.tag_product("https://img/a.jpg")["department"] == "men"
    monkeypatch.setattr(service, "ai_json", lambda *a, **k: {"label": "tee", "category": "top", "department": "kids"})
    assert service.tag_product("https://img/b.jpg")["department"] is None


# ---------- script paths ----------

def _seed(store, *ps):
    for p in ps:
        store.put("products", p["id"], p)


def test_summaries_only_fills_missing_summaries(ai, capsys):
    from app.store import store
    from scripts import tag_catalog

    _seed(store, _p(pid="hm:1:a", description="Soft tee. Regular fit. Cotton."), _p(pid="hm:2:b", summary="Done."),
          _p(pid="hm:3:c", description=None, label="", department=None))
    tag_catalog.main(["--summaries-only"])
    a, b, c = (store.get("products", f"hm:{i}:{k}") for i, k in ((1, "a"), (2, "b"), (3, "c")))
    assert a["summary"].startswith("Loose-fit jeans") and b["summary"] == "Done."
    assert c["summary"] == "A light-wash baggy jean with a relaxed, streetwear fit."
    assert c["label"] == "" and c["department"] is None                 # no tagging, no department
    assert all("fashion cataloguer" not in s for s in ai) and len(ai) == 2
    assert "summarizing 2 products" in capsys.readouterr().out


def test_departments_only_rules_first_then_ai(ai):
    from app.store import store
    from scripts import tag_catalog

    _seed(store, _p(pid="hm:1:a", department=None, name="Women's Linen Shirt"),
          _p(pid="hm:2:b", department=None, name="Oversized Hoodie"),
          _p(pid="hm:3:c", department="women", name="Men's Shirt"),
          _p(pid="hm:4:d", department=None, name="Mens Chinos", summary=None))
    tag_catalog.main(["--departments-only"])
    assert store.get("products", "hm:1:a")["department"] == "women"
    assert store.get("products", "hm:2:b")["department"] == "men"      # tagger
    assert store.get("products", "hm:3:c")["department"] == "women"    # untouched
    assert store.get("products", "hm:4:d")["department"] == "men"
    assert store.get("products", "hm:4:d").get("summary") is None      # departments only
    assert sum("fashion cataloguer" in s for s in ai) == 1             # AI only for the one the rules missed


def test_normal_run_fills_tags_department_and_summary(ai):
    from app.store import store
    from scripts import tag_catalog

    _seed(store, _p(pid="hm:1:a", label="", department=None, description=None),
          _p(pid="hm:2:b", summary="Kept.", department="women"))
    tag_catalog.main([])
    a = store.get("products", "hm:1:a")
    assert a["label"] == "baggy jeans" and a["department"] == "men" and a["summary"].startswith("A light-wash")
    assert store.get("products", "hm:2:b")["summary"] == "Kept."
    tag_catalog.main([])                                                # nothing left: no new AI calls
    assert len(ai) == 2


def test_main_aborts_in_mock_mode_unless_summaries_only(monkeypatch, tmp_path):
    from app.store import store
    from scripts import tag_catalog

    monkeypatch.setattr(store, "root", tmp_path)
    _seed(store, _p(pid="hm:1:a"))
    with pytest.raises(SystemExit):
        tag_catalog.main([])
    tag_catalog.main(["--summaries-only"])                              # rules template, no AI
    assert store.get("products", "hm:1:a")["summary"].endswith("with a streetwear feel.")
