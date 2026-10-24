"""Ingest normalizers + CLI on saved raw fixtures (no network, MOCK_AI)."""
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

os.environ["MOCK_AI"] = "1"

from app.commerce.ingest import (gallery, guess_category, hm_category, normalize_hm,  # noqa: E402
                                 normalize_uniqlo, plain_text, process)
from app.models import Product  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
BACKEND = Path(__file__).parent.parent
HM = json.loads((FIX / "hm_raw.json").read_text())
UQ = json.loads((FIX / "uniqlo_raw.json").read_text())


def test_hm_valid_products_and_kids_dropped():
    drops = Counter()
    out = normalize_hm(HM, drops)
    assert len(out) == 4 and drops["hm_not_adult"] == 1
    assert not any("1111111001" in p["id"] for p in out)
    for p in out:
        Product(**p)
        assert p["retailer"] == "hm" and p["brand"] == "H&M" and p["source"] == "ingest"
        assert p["image_url"].endswith("?imwidth=657") and p["scraped_at"]
    by_id = {p["id"]: p for p in out}
    assert by_id["hm:1361447006:burgundy-striped"]["category"] == "top"
    jeans = by_id["hm:1234567001:light-denim-blue"]
    assert jeans["category"] == "bottom" and jeans["in_stock"]
    assert {s["name"]: s["in_stock"] for s in jeans["sizes"]}["34"] is False


def test_hm_maternity_dropped():
    item = dict(HM[0], id="999", title="MAMA Ribbed Nursing Top", category="ladies_maternity_tops")
    drops = Counter()
    assert normalize_hm([item], drops) == [] and drops["hm_maternity"] == 1


def test_uniqlo_one_product_per_color_capped():
    drops = Counter()
    out = normalize_uniqlo(UQ, drops)
    for p in out:
        Product(**p)
        assert p["retailer"] == "uniqlo" and len(p["colors"]) == 1
    per = Counter(p["id"].rsplit(":", 1)[0] for p in out)
    assert set(per.values()) == {3}  # every fixture product has > 3 colours
    assert len({p["id"] for p in out}) == len(out)
    assert drops["uniqlo_extra_colors"] > 0
    p = next(p for p in out if p["id"] == "uniqlo:E488230-000:brown")
    assert p["image_url"].endswith("usgoods_35_488230_3x4.jpg")
    assert p["product_url"].endswith("?colorDisplayCode=35")
    assert p["category"] == "top"


def test_uniqlo_low_stock_counts_as_in_stock():
    # E488230 BROWN: XL is LOW_STOCK (inStock:false), XXL-ish sizes STOCK_OUT
    raw = next(r for r in UQ if r["productId"] == "E488230-000")
    brown = [v for v in raw["variants"] if v["colorCode"] == "COL35"]
    low = next(v["sizeName"] for v in brown if v["stockStatus"] == "LOW_STOCK")
    out = {p["id"]: p for p in normalize_uniqlo([raw])}
    sizes = {s["name"]: s["in_stock"] for s in out["uniqlo:E488230-000:brown"]["sizes"]}
    assert sizes[low] is True
    out_names = {v["sizeName"] for v in brown if v["stockStatus"] == "STOCK_OUT"} - \
        {v["sizeName"] for v in brown if v["stockStatus"] != "STOCK_OUT"}
    assert all(sizes[n] is False for n in out_names)


def test_uniqlo_sold_out_colors_last_and_sale_price():
    raw = next(r for r in UQ if r["productId"] == "E488230-000")
    out = normalize_uniqlo([raw])
    assert all(p["in_stock"] for p in out)  # in-stock colours picked before sold-out ones
    assert all(p["sale_price_usd"] is None for p in out)  # promo == base is not a sale
    mini = normalize_uniqlo([next(r for r in UQ if r["productId"] == "E465760-000")])
    assert mini[0]["price_usd"] == 19.9 and mini[0]["sale_price_usd"] == 14.9


def test_hm_gallery_same_colour_deduped():
    raw = next(r for r in HM if r["id"] == "1361447006")
    p = next(p for p in normalize_hm(HM) if p["id"] == "hm:1361447006:burgundy-striped")
    urls = [i["url"] for i in p["images"]]
    assert urls[0] == p["image_url"] and len(urls) == len(set(urls)) == 5  # model_image repeated in images[]
    assert urls == [f"{u}?imwidth=657" for u in [raw["model_image"], *raw["images"][:4]]]
    assert {i["kind"] for i in p["images"]} == {"retailer_model"}
    other = {f"{w['image']}?imwidth=657" for w in raw["swatches"]}
    assert not other & set(urls)  # swatches (incl. other colours) never used
    single = next(p for p in normalize_hm(HM) if p["id"].startswith("hm:1360320001"))
    assert single["images"] == [{"url": single["image_url"], "kind": "retailer_model"}]
    assert all(p["description"] is None for p in normalize_hm(HM))  # the H&M actor has no description


def test_uniqlo_gallery_is_own_colour_photo_only():
    out = normalize_uniqlo(UQ)
    for p in out:
        assert p["images"] == [{"url": p["image_url"], "kind": "product"}]  # subImages aren't per colour
    sub = {u for r in UQ for u in r["subImages"]}
    assert not sub & {i["url"] for p in out for i in p["images"]}


def test_uniqlo_description_plain_text():
    by = {p["id"].split(":")[1]: p for p in normalize_uniqlo(UQ)}
    assert by["E488230-000"]["description"] == "- Ribbed binding at the collar helps the neckline keep its shape."
    mini = by["E465760-000"]["description"]
    assert mini.startswith("A sleek, cropped women’s Mini T-Shirt") and mini.endswith("\nCropped length.\nFitted.")
    assert "<" not in mini and "&" not in mini
    assert by["E470143-000"]["description"] is None  # fixture has none


def test_gallery_and_plain_text_helpers():
    assert gallery(("a", "retailer_model"), ("b", "product"), ("a", "product"), (None, "product")) == \
        [{"url": "b", "kind": "product"}, {"url": "a", "kind": "retailer_model"}]
    assert plain_text("<p>Soft&nbsp;&amp;  warm.</p><ul><li>One</li><li> Two </li></ul>") == "Soft & warm.\nOne\nTwo"
    assert plain_text("  ") is None and plain_text(None) is None and plain_text(3) is None


def test_product_without_images_or_description_validates():
    p = Product(id="hm:1:black", retailer="hm", name="Tee", brand="H&M", category="top", price_usd=9.99,
                image_url="https://x/1.jpg", product_url="https://x/1")
    assert p.images == [] and p.description is None


def test_ids_stable():
    a = [p["id"] for p in normalize_hm(HM) + normalize_uniqlo(UQ)]
    b = [p["id"] for p in normalize_hm(HM) + normalize_uniqlo(UQ)]
    assert a == b and len(set(a)) == len(a)
    assert "hm:1361447006:burgundy-striped" in a and "uniqlo:E470143-000:off-white" in a


def test_category_rules():
    assert guess_category("Flared Dress with Belt") == "dress"
    assert guess_category("Scarf-Detail Sweater") == "top"
    assert guess_category("Oversized Hooded Jacket") == "outerwear"
    assert guess_category("Viscose-Blend Cape") is None
    assert hm_category("men_jacketscoats_cargojackets") == "outerwear"
    assert hm_category("men_tshirtstanks_shortsleeve") == "top"
    assert hm_category("ladies_jeans_wide") == "bottom"


def test_process_dedupes_and_tags_in_mock():
    saved, summary = process({"hm": HM + HM, "uniqlo": UQ}, do_tag=True, dry_run=True)
    assert summary["saved"] == {"hm": 4, "uniqlo": 9}
    assert summary["dropped"]["duplicate_id"] == 4 and summary["dropped"]["hm_not_adult"] == 2
    assert all(p["label"] == "" for p in saved)  # mock tagger is skipped, rule-based fields kept


def test_tag_passes_name_hint_and_keeps_vocab(monkeypatch):
    from app.ai import llm, service
    from app.commerce.ingest import tag

    calls = []

    def fake_tag(url, hint=None):
        calls.append((url, hint))
        return {"label": "white tee", "category": "top", "pattern": "solid", "formality": 2,
                "style_tags": ["minimalist", "casual"]}

    monkeypatch.setattr(llm, "text_mock", lambda: False)
    monkeypatch.setattr(service, "tag_product", fake_tag)
    out = tag([{"id": "hm:1:white", "name": "Regular Fit T-shirt", "image_url": "https://img/a.jpg"}])
    assert calls == [("https://img/a.jpg", "Regular Fit T-shirt")]
    assert out[0]["style_tags"] == ["minimalist"] and out[0]["label"] == "white tee"


def test_cli_from_file_dry_run(tmp_path):
    env = {**os.environ, "MOCK_AI": "1", "DATA_DIR": str(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "scripts.ingest", "--from-file", str(FIX / "hm_*.json"),
                        "--retailer", "hm", "--dry-run", "--no-tag", "--show", "0"],
                       cwd=BACKEND, env=env, capture_output=True, text=True, check=True)
    summary = json.loads(r.stdout)
    assert summary["saved"] == {"hm": 4} and summary["dry_run"] is True
    assert not (tmp_path / "products.json").exists()
    r = subprocess.run([sys.executable, "-m", "scripts.ingest", "--from-file", str(FIX / "uniqlo_raw.json"),
                        "--retailer", "uniqlo", "--dry-run", "--show", "1"],
                       cwd=BACKEND, env=env, capture_output=True, text=True, check=True)
    assert '"uniqlo": 9' in r.stdout and not (tmp_path / "products.json").exists()
