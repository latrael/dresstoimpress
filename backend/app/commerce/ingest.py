"""Product ingest: Apify actors -> normalized `Product` dicts -> tagger -> store.

Sources (both fine on the Apify free plan, no proxy):
  H&M     gauzy_penguin/HM-Product-Scraper   one item per article (= one colour)
  Uniqlo  abotapi/uniqlo-com-scraper         one item per product; we emit one Product per colour

    from app.commerce.ingest import ingest
    ingest(["womens tops"], ["women t-shirts"], per_keyword=10)

Normalizers are pure (no network) so they run on saved raw pulls too (scripts/ingest.py --from-file).
"""
from __future__ import annotations

import html
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import get_args

import httpx
from pydantic import ValidationError

from ..models import Product, StyleTag

log = logging.getLogger(__name__)

HM_ACTOR = "gauzy_penguin/HM-Product-Scraper"
UNIQLO_ACTOR = "abotapi/uniqlo-com-scraper"
HM_ADULT = ("ladies_", "men_", "divided_", "sportswear_")
UNIQLO_ADULT = {"WOMEN", "MEN", "UNISEX"}
MATERNITY = re.compile(r"\bmama\b|maternity|nursing", re.I)  # not for a college-student feed
MAX_COLORS = 3  # per Uniqlo product, so one tee doesn't fill the feed

# Garment words -> Category. In a name the last garment word wins ("Shirt Dress" -> dress,
# "Scarf-Detail Sweater" -> top, "Hooded Jacket" -> outerwear).
CATEGORY_WORDS = {
    "dress": {"dress", "dresses"},
    "bottom": {"jeans", "trousers", "pants", "shorts", "skirt", "skirts", "joggers", "leggings",
               "chinos", "sweatpants", "cargos", "culottes"},
    "outerwear": {"jacket", "jackets", "coat", "coats", "blazer", "blazers", "parka", "parkas", "puffer",
                  "gilet", "outerwear", "windbreaker", "overshirt", "blouson", "anorak", "trench"},
    "shoes": {"shoes", "shoe", "sneakers", "boots", "sandals", "loafers", "heels", "trainers"},
    "accessory": {"bag", "bags", "accessories", "hat", "hats", "cap", "caps", "belt", "belts",
                  "scarf", "scarves", "socks", "jewelry", "jewellery", "sunglasses", "beanie"},
    "top": {"top", "tops", "tshirt", "tshirts", "shirt", "shirts", "tee", "tees", "hoodie", "hoodies",
            "sweater", "sweaters", "sweatshirt", "sweatshirts", "cardigan", "cardigans", "blouse",
            "blouses", "polo", "polos", "tank", "tanks", "knitwear", "henley", "turtleneck", "cami",
            "camisole", "bodysuit", "jumper", "jumpers"},
}
WORD_TO_CAT = {w: c for c, ws in CATEGORY_WORDS.items() for w in ws}
# H&M category codes glue words together ("ladies_jacketscoats_bomberjackets"), so match stems
# inside each segment, in this order ("cargojackets" is outerwear, not cargo pants).
HM_STEMS = [
    ("dress", ("dress",)),
    ("outerwear", ("jacket", "coat", "blazer", "parka", "gilet", "puffer")),
    ("bottom", ("jean", "trouser", "short", "skirt", "jogger", "legging", "pant", "chino", "cargo")),
    ("shoes", ("shoe", "sneaker", "boot", "sandal", "heel", "loafer", "trainer")),
    ("accessory", ("accessor", "bag", "belt", "scarf", "sock", "jewel", "sunglass")),
    ("top", ("top", "shirt", "hoodie", "sweat", "cardigan", "jumper", "blouse", "polo", "tank", "knit",
             "camisole", "bodysuit", "longsleeve")),
]
_TOKEN = re.compile(r"[a-z]+")


def guess_category(*texts: str) -> str | None:
    """First text (most specific first) with a garment word wins; None = leave it to the tagger."""
    for text in texts:
        head = re.split(r"\||\bwith\b", (text or "").lower())[0]  # "Dress with Belt | Linen" -> "dress"
        words = _TOKEN.findall(head.replace("t-shirt", "tshirt"))
        for w in reversed(words):
            if w in WORD_TO_CAT:
                return WORD_TO_CAT[w]
    return None


def hm_category(code: str) -> str | None:
    """H&M category code ("men_jeans_baggy") -> Category."""
    segs = code.lower().replace("shortsleeve", "").split("_")[1:]  # drop ladies_/men_
    for cat, stems in HM_STEMS:
        if any(stem in seg for seg in segs for stem in stems):
            return cat
    return None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hm_url(u: str) -> str:
    return f"{u}?imwidth=657" if "?" not in u else u


def gallery(*imgs: tuple[str | None, str]) -> list[dict]:
    """(url, kind) pairs -> ProductImage dicts: de-duped, garment-only ("product") first, else in order."""
    seen, out = set(), []
    for url, kind in imgs:
        if url and url not in seen:
            seen.add(url)
            out.append({"url": url, "kind": kind})
    return sorted(out, key=lambda i: i["kind"] != "product")  # stable


_BREAK = re.compile(r"<br\s*/?>|</(?:p|li|div|h\d)>", re.I)
_TAG = re.compile(r"<[^>]+>")


def plain_text(s) -> str | None:
    """Retailer text/HTML -> plain text: tags stripped, entities decoded, spaces collapsed, one line per
    paragraph/bullet. None if empty."""
    if not isinstance(s, str):
        return None
    s = html.unescape(_TAG.sub(" ", _BREAK.sub("\n", s)))
    lines = (" ".join(line.split()) for line in s.splitlines())
    return "\n".join(line for line in lines if line) or None


def _valid(p: dict) -> dict | None:
    try:
        return Product(**p).model_dump()
    except ValidationError as e:
        log.warning("invalid product %s: %s", p.get("id"), e.errors()[:2])
        return None


# ---- Apify ----

def run_actor(actor: str, input: dict, token: str, timeout: float = 600) -> list[dict]:
    """Run an actor synchronously and return its dataset items."""
    r = httpx.post(f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
                   params={"token": token}, json=input, timeout=timeout)
    r.raise_for_status()
    items = r.json()
    return items if isinstance(items, list) else []


def fetch_hm(keywords: list[str], per_keyword: int, token: str) -> list[dict]:
    return run_actor(HM_ACTOR, {"keywords": ", ".join(keywords), "Country": "en_us",
                                "maxItems": per_keyword}, token)


def fetch_uniqlo(categories: list[str], per_category: int, token: str) -> list[dict]:
    # $0.08 per run, so every category goes into one run
    return run_actor(UNIQLO_ACTOR, {"mode": "search", "country": "us", "categories": categories,
                                    "maxItems": per_category * len(categories), "fetchDetails": True,
                                    "fetchReviews": False, "proxy": {"useApifyProxy": False}}, token)


# ---- normalizers (raw actor items -> Product dicts; category may be None) ----

def normalize_hm(raw: list[dict], drops: Counter | None = None) -> list[dict]:
    """H&M items -> Products. Kids/baby (anything outside HM_ADULT) is dropped."""
    drops = drops if drops is not None else Counter()
    out, now = [], _now()
    for it in raw:
        cat_raw = str(it.get("category") or "")
        if not cat_raw.startswith(HM_ADULT):
            drops["hm_not_adult"] += 1
            continue
        if MATERNITY.search(f"{cat_raw.replace('_', ' ')} {it.get('title', '')}"):
            drops["hm_maternity"] += 1
            continue
        img = it.get("model_image") or (it.get("images") or [None])[0]
        if not (it.get("id") and img and it.get("price")):
            drops["hm_missing_fields"] += 1
            continue
        sizes = [{"name": str(s["size"]), "in_stock": bool(s.get("in_stock"))}
                 for s in it.get("sizes") or [] if s.get("size")]
        color = str(it.get("color") or "")
        cat = guess_category(it.get("title", "")) or hm_category(cat_raw)
        p = _valid({
            "id": f"hm:{it['id']}:{slug(color)}",
            "retailer": "hm",
            "name": it.get("title") or "",
            "brand": "H&M",
            "category": cat or "top",
            "price_usd": float(it["price"]),
            "colors": [color] if color else [],
            "sizes": sizes,
            "in_stock": any(s["in_stock"] for s in sizes) if sizes else True,
            "image_url": _hm_url(img),
            "product_url": it.get("url") or "",
            # model_image + images[] are this article (= this colour) only; swatches[] are other
            # colours, so never used. No flag says which shots are garment-only: all retailer_model.
            "images": gallery(*((_hm_url(u), "retailer_model") for u in [img, *(it.get("images") or [])] if u)),
            "description": plain_text(it.get("description")),  # the H&M actor doesn't return one
            "scraped_at": now,
            "source": "ingest",
        })
        if p is None:
            drops["hm_invalid"] += 1
            continue
        if cat is None:
            p["category"] = None  # validated with a placeholder; the tagger fills it or it's dropped
        out.append(p)
    return out


def normalize_uniqlo(raw: list[dict], drops: Counter | None = None,
                     max_colors: int = MAX_COLORS) -> list[dict]:
    """Uniqlo products -> one Product per colour (in-stock colours first, capped)."""
    drops = drops if drops is not None else Counter()
    out, now = [], _now()
    for it in raw:
        gender = str(it.get("genderName") or "").upper()
        top_path = str(it.get("categoryPath") or "").split(">")[0].strip().upper()
        if (gender and gender not in UNIQLO_ADULT) or top_path in {"KIDS", "BABY"}:
            drops["uniqlo_not_adult"] += 1
            continue
        pid = it.get("productId")
        if not pid:
            drops["uniqlo_missing_fields"] += 1
            continue
        path = [s.strip() for s in str(it.get("categoryPath") or "").split(">")]
        cat = guess_category(it.get("name", ""), *reversed(path))
        base = it.get("basePrice") or it.get("price")
        promo = it.get("promoPrice")

        by_code: dict[str, list[dict]] = {}
        for v in it.get("variants") or []:
            by_code.setdefault(v.get("colorCode"), []).append(v)

        colors, seen_names = [], set()
        for c in it.get("colors") or []:
            name = str(c.get("name") or "").strip()
            if not name or slug(name) in seen_names or not c.get("imageUrl"):
                continue  # same name, different code (RED COL15/COL17): keep the first, ids stay unique
            seen_names.add(slug(name))
            sizes: dict[str, bool] = {}
            for v in by_code.get(c.get("code"), []):
                # LOW_STOCK reports inStock:false but is buyable
                sizes[str(v.get("sizeName"))] = sizes.get(str(v.get("sizeName")), False) or \
                    v.get("stockStatus") != "STOCK_OUT"
            colors.append((c, name, [{"name": k, "in_stock": s} for k, s in sizes.items()]))
        colors.sort(key=lambda x: not any(s["in_stock"] for s in x[2]))  # stable: keeps site order
        if len(colors) > max_colors:
            drops["uniqlo_extra_colors"] += len(colors) - max_colors

        for c, name, sizes in colors[:max_colors]:
            v0 = (by_code.get(c.get("code")) or [{}])[0]
            c_base = v0.get("basePrice") or base
            c_promo = v0.get("promoPrice") or promo
            if not c_base:
                drops["uniqlo_missing_fields"] += 1
                continue
            code = str(c.get("code") or "").removeprefix("COL")
            url = it.get("url") or ""
            p = _valid({
                "id": f"uniqlo:{pid}:{slug(name)}",
                "retailer": "uniqlo",
                "name": it.get("name") or "",
                "brand": "Uniqlo",
                "category": cat or "top",
                "price_usd": float(c_base),
                "sale_price_usd": float(c_promo) if c_promo and float(c_promo) < float(c_base) else None,
                "colors": [name.title()],
                "sizes": sizes,
                "in_stock": any(s["in_stock"] for s in sizes) if sizes else True,
                "image_url": c["imageUrl"],
                "product_url": f"{url}?colorDisplayCode={code}" if url and code else url,
                # subImages aren't keyed by colour (may show another one), so only this colour's photo
                "images": gallery((c["imageUrl"], "product")),
                "description": plain_text(it.get("descriptionLong") or it.get("description")
                                          or it.get("descriptionShort")),
                "scraped_at": now,
                "source": "ingest",
            })
            if p is None:
                drops["uniqlo_invalid"] += 1
                continue
            if cat is None:
                p["category"] = None
            out.append(p)
    return out


NORMALIZERS = {"hm": normalize_hm, "uniqlo": normalize_uniqlo}


# ---- tagging + saving ----

STYLE_VOCAB = set(get_args(StyleTag))


def tag(products: list[dict], drops: Counter | None = None) -> list[dict]:
    """Fill label/pattern/formality/style_tags (and a missing category) from the image tagger.
    Without an AI key (or MOCK_AI=1) the tagger returns one fixed answer, so we skip it."""
    from ..ai.llm import text_mock

    drops = drops if drops is not None else Counter()
    use_ai = not text_mock()
    if use_ai:
        from ..ai.service import tag_product
    out = []
    for p in products:
        if use_ai:
            try:
                t = tag_product(p["image_url"], hint=p["name"])  # model shots: name says which garment
                p.update({k: t[k] for k in ("label", "pattern", "formality")})
                p["style_tags"] = [s for s in t.get("style_tags") or [] if s in STYLE_VOCAB]  # model drifts ("casual")
                p["category"] = p.get("category") or t["category"]
            except Exception as e:  # NotClothing, model errors, budget: keep the rule-based fields
                log.warning("tag failed for %s: %s", p["id"], e)
                drops["tag_failed"] += 1
        if not p.get("category"):
            drops["no_category"] += 1
            continue
        out.append(p)
    return out


def save(products: list[dict], dry_run: bool = False) -> list[dict]:
    """Dedupe by id (last wins), validate, store.put unless dry_run. Returns what was (or would be) saved."""
    uniq = {p["id"]: p for p in products}
    good = [q for q in (_valid(p) for p in uniq.values()) if q]
    if not dry_run:
        from ..store import store  # lazy: DATA_DIR is read at import (tests set it late)

        for p in good:
            store.put("products", p["id"], p)
    return good


def process(raw_by_retailer: dict[str, list[dict]], do_tag: bool = True,
            dry_run: bool = False) -> tuple[list[dict], dict]:
    """Normalize -> tag -> dedupe/save. Returns (products, summary)."""
    drops: Counter = Counter()
    normalized: list[dict] = []
    raw_counts = {}
    for retailer, raw in raw_by_retailer.items():
        raw_counts[retailer] = len(raw)
        normalized += NORMALIZERS[retailer](raw, drops)
    if do_tag:
        normalized = tag(normalized, drops)
    else:
        missing = sum(1 for p in normalized if not p.get("category"))
        if missing:
            drops["no_category"] += missing
        normalized = [p for p in normalized if p.get("category")]
    dupes = len(normalized) - len({p["id"] for p in normalized})
    if dupes:
        drops["duplicate_id"] += dupes
    saved = save(normalized, dry_run)
    summary = {
        "raw": raw_counts,
        "saved": dict(Counter(p["retailer"] for p in saved)),
        "by_category": dict(Counter(p["category"] for p in saved)),
        "dropped": dict(drops),
        "tagged": do_tag,
        "dry_run": dry_run,
    }
    return saved, summary


def ingest(hm_keywords: list[str], uniqlo_categories: list[str], per_keyword: int = 10,
           token: str | None = None, do_tag: bool = True, dry_run: bool = False) -> dict:
    """Pull from Apify, then `process`. Returns the summary dict."""
    token = token or os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")
    raw: dict[str, list[dict]] = {}
    if hm_keywords:
        raw["hm"] = fetch_hm(hm_keywords, per_keyword, token)
    if uniqlo_categories:
        raw["uniqlo"] = fetch_uniqlo(uniqlo_categories, per_keyword, token)
    return process(raw, do_tag, dry_run)[1]
