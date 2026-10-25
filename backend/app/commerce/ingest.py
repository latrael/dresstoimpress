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
import time
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
# Not clothing: dropped by every normalizer (Uniqlo "bags" includes storage bags; Shopify stores sell gift cards)
NOT_APPAREL = re.compile(r"gift ?card|e-?gift|beauty|fragrance|perfume|candle|skincare|makeup|lip ?gloss|"
                         r"phone case|sticker|poster|home goods|homeware|mug|towel|insurance|shipping|keychain|key ?ring|"
                         r"storage bag", re.I)

# Garment words -> Category. In a name the last garment word wins ("Shirt Dress" -> dress,
# "Scarf-Detail Sweater" -> top, "Hooded Jacket" -> outerwear).
CATEGORY_WORDS = {
    "dress": {"dress", "dresses"},
    "bottom": {"jeans", "trousers", "pants", "shorts", "skirt", "skirts", "joggers", "leggings",
               "chinos", "sweatpants", "cargos", "culottes", "sarong"},
    "outerwear": {"jacket", "jackets", "coat", "coats", "blazer", "blazers", "parka", "parkas", "puffer",
                  "gilet", "outerwear", "windbreaker", "overshirt", "blouson", "anorak", "trench"},
    "shoes": {"shoes", "shoe", "sneakers", "sneaker", "boots", "boot", "sandals", "sandal", "loafers", "loafer",
              "heels", "heel", "trainers", "footwear", "mules", "clogs", "slippers", "flats", "derby", "derbies"},
    "accessory": {"bag", "bags", "accessories", "hat", "hats", "cap", "caps", "belt", "belts",
                  "scarf", "scarves", "socks", "jewelry", "jewellery", "sunglasses", "beanie", "beanies",
                  "headwear", "necklace", "necklaces", "earrings", "bracelet", "bracelets", "tote", "backpack",
                  "wallet", "crossbody", "clutch", "purse", "headband", "scrunchie", "eyewear", "ring", "rings", "cuff",
                  "clip", "chain"},
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


HM_DEPT = {"ladies": "women", "women": "women", "men": "men"}
UNIQLO_DEPT = {"WOMEN": "women", "MEN": "men", "UNISEX": "unisex"}


def hm_department(code: str) -> str | None:
    """H&M category code -> Product.department: "ladies_..." women, "men_..." men, "sportswear_women_..."
    by its second part. None when the code doesn't say (e.g. "divided_", H&M's teen line)."""
    segs = (code or "").lower().split("_")
    if segs[0] == "sportswear":
        segs = segs[1:]
    return HM_DEPT.get(segs[0]) if segs else None


def uniqlo_department(item: dict) -> str | None:
    """Uniqlo genderCategory / department / genderName (MEN, WOMEN, UNISEX) -> Product.department."""
    for k in ("genderCategory", "department", "genderName"):
        if dept := UNIQLO_DEPT.get(str(item.get(k) or "").upper()):
            return dept
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

APIFY_API = "https://api.apify.com/v2"
MAX_CHARGE_USD = 2.0  # default hard cap per paid run (sprint rule: ask Nabil before any run over $2)
RUN_DONE = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}  # terminal run statuses
DATASET_PAGE = 1000


class ApifyRunError(RuntimeError):
    """A run that FAILED, or was still going when we stopped waiting. Carries the ids, so whatever it
    scraped (already paid for) can be fetched later with `scripts.ingest --from-dataset`."""

    def __init__(self, msg: str, run_id: str | None = None, dataset_id: str | None = None):
        super().__init__(msg)
        self.run_id, self.dataset_id = run_id, dataset_id


def _apify(method: str, path: str, token: str, retries: int = 0, **kw) -> httpx.Response:
    """One Apify API call. The token goes in a header, so error messages and logs never carry it.
    `retries`: extra tries on network errors / 429 / 5xx (safe for GETs only)."""
    for attempt in range(retries + 1):
        try:
            r = httpx.request(method, f"{APIFY_API}{path}", headers={"Authorization": f"Bearer {token}"}, **kw)
            r.raise_for_status()
            return r
        except httpx.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", 0)
            if attempt == retries or (status and status != 429 and status < 500):
                raise
            log.warning("apify %s %s: %s %s, retrying", method, path, type(e).__name__, status or "")
            time.sleep(min(30, 2 ** attempt))
    raise AssertionError("unreachable")


def dataset_items(dataset_id: str, token: str, page: int | None = None) -> list[dict]:
    """Every item of an Apify dataset (clean JSON), `page` (default DATASET_PAGE) at a time. Costs a
    fraction of a cent, and works for any run's dataset while Apify keeps it (7 days for unnamed ones)."""
    page = page or DATASET_PAGE
    items: list[dict] = []
    offset = 0
    while True:
        r = _apify("GET", f"/datasets/{dataset_id}/items", token, retries=3, timeout=120,
                   params={"clean": "true", "format": "json", "limit": page, "offset": offset})
        batch = r.json()
        if not isinstance(batch, list):
            raise ApifyRunError(f"dataset {dataset_id}: expected a JSON array, got {type(batch).__name__}",
                                dataset_id=dataset_id)
        items += batch
        offset += page
        # clean=true may return fewer than `limit` items mid-dataset, so page by the total, not the count
        total = r.headers.get("x-apify-pagination-total")
        if (offset >= int(total)) if total is not None else not batch:
            return items


def run_actor(actor: str, input: dict, token: str, timeout: float = 600,
              max_charge_usd: float | None = MAX_CHARGE_USD, poll_s: float = 5) -> list[dict]:
    """Start an actor run, wait for it (up to `timeout` s), return its dataset items.

    Asynchronous on purpose: run-sync-get-dataset-items 502s or times out on long runs while the run
    itself succeeds and is billed, which "lost" paid data. Here a 502 while waiting is just retried.
    TIMED-OUT / ABORTED runs return their partial (paid-for) items; FAILED raises ApifyRunError, as does
    a run still going after `timeout` (the error says how to fetch its data later). `max_charge_usd`
    is Apify's maxTotalChargeUsd: the run stops once it would cost more. None or 0 = no cap."""
    params = {"maxTotalChargeUsd": max_charge_usd} if max_charge_usd else {}
    run = _apify("POST", f"/acts/{actor.replace('/', '~')}/runs", token, params=params, json=input,
                 timeout=60).json()["data"]
    run_id, dataset_id = run["id"], run.get("defaultDatasetId")
    log.info("apify run %s started (dataset %s, cap $%s)", run_id, dataset_id, max_charge_usd or "none")
    deadline = time.monotonic() + timeout
    while run.get("status") not in RUN_DONE:
        left = deadline - time.monotonic()
        if left <= 0:
            raise ApifyRunError(
                f"Apify run {run_id} is still {run.get('status')} after {timeout:.0f}s. It keeps running; fetch "
                f"its items later with: python -m scripts.ingest --from-dataset {dataset_id} --retailer ...",
                run_id, dataset_id)
        time.sleep(poll_s)
        try:  # waitForFinish: Apify holds the request until the run ends (max 60 s), so few polls
            run = _apify("GET", f"/actor-runs/{run_id}", token, timeout=90,
                         params={"waitForFinish": int(max(0, min(60, left)))}).json()["data"]
        except httpx.HTTPError as e:  # 502 / network blip while waiting: the run is fine, keep waiting
            status = getattr(getattr(e, "response", None), "status_code", 0)
            if status and status != 429 and status < 500:
                raise  # 401 / 404: waiting won't help
            log.warning("polling apify run %s: %s %s, retrying", run_id, type(e).__name__, status or "")
    dataset_id = run.get("defaultDatasetId") or dataset_id
    if run["status"] == "FAILED":
        raise ApifyRunError(
            f"Apify run {run_id} FAILED ({run.get('statusMessage') or 'no message'}). Any items it scraped: "
            f"python -m scripts.ingest --from-dataset {dataset_id} --retailer ...", run_id, dataset_id)
    if run["status"] != "SUCCEEDED":
        log.warning("apify run %s ended %s; keeping its partial items", run_id, run["status"])
    return dataset_items(dataset_id, token)


def fetch_hm(keywords: list[str], per_keyword: int, token: str,
             max_charge_usd: float | None = MAX_CHARGE_USD, timeout: float = 600) -> list[dict]:
    return run_actor(HM_ACTOR, {"keywords": ", ".join(keywords), "Country": "en_us",
                                "maxItems": per_keyword}, token, timeout, max_charge_usd)


def fetch_uniqlo(categories: list[str], per_category: int, token: str,
                 max_charge_usd: float | None = MAX_CHARGE_USD, timeout: float = 600) -> list[dict]:
    # $0.08 per run, so every category goes into one run
    return run_actor(UNIQLO_ACTOR, {"mode": "search", "country": "us", "categories": categories,
                                    "maxItems": per_category * len(categories), "fetchDetails": True,
                                    "fetchReviews": False, "proxy": {"useApifyProxy": False}},
                     token, timeout, max_charge_usd)


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
        if NOT_APPAREL.search(str(it.get("title") or "")):
            drops["hm_not_apparel"] += 1
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
            "department": hm_department(cat_raw),
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
        if NOT_APPAREL.search(str(it.get("name") or "")):
            drops["uniqlo_not_apparel"] += 1
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
                "department": uniqlo_department(it),
            })
            if p is None:
                drops["uniqlo_invalid"] += 1
                continue
            if cat is None:
                p["category"] = None
            out.append(p)
    return out


NORMALIZERS = {"hm": normalize_hm, "uniqlo": normalize_uniqlo}

from .ingest_shopify import normalize_shopify  # noqa: E402  (it imports the helpers above)

NORMALIZERS["shopify"] = normalize_shopify


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


# Paid-for AI output (tag_catalog). `summary` is Adam's card blurb, read by key because the model may
# not define it yet. A re-ingest refreshes everything else.
AI_FIELDS = ("label", "pattern", "formality", "style_tags", "summary")


def keep_ai_fields(new: dict, old: dict | None) -> dict:
    """`new` (a fresh scrape) plus the AI fields of `old` (the stored copy) wherever `new` has no value
    of its own. Price, sizes/stock, images, department, scraped_at... always come from `new`."""
    if not old:
        return new
    return {**new, **{k: old[k] for k in AI_FIELDS if not new.get(k) and old.get(k)}}


def save(products: list[dict], dry_run: bool = False) -> list[dict]:
    """Dedupe by id (last wins), keep stored AI fields (`keep_ai_fields`), validate, store.put unless
    dry_run. Returns what was (or would be) saved."""
    from ..store import store  # lazy: DATA_DIR is read at import (tests set it late)

    from . import image_kinds

    uniq = {p["id"]: p for p in products}
    stored = {p.get("id"): p for p in store.list("products")} if uniq else {}  # one read, not one per product
    kinds = image_kinds.load_cache()  # photo labels from scripts.classify_images: free to re-apply
    good = []
    for pid, p in uniq.items():
        merged = image_kinds.apply(keep_ai_fields(p, stored.get(pid)), kinds)
        q = _valid(merged)
        if q:  # validation drops fields the model doesn't define yet (summary): carry them over as they are
            good.append({**q, **{k: merged[k] for k in AI_FIELDS if k in merged and k not in q}})
    if not dry_run:
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
           token: str | None = None, do_tag: bool = True, dry_run: bool = False,
           max_charge_usd: float | None = MAX_CHARGE_USD) -> dict:
    """Pull from Apify (each run capped at `max_charge_usd`), then `process`. Returns the summary dict."""
    token = token or os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN is not set")
    raw: dict[str, list[dict]] = {}
    if hm_keywords:
        raw["hm"] = fetch_hm(hm_keywords, per_keyword, token, max_charge_usd)
    if uniqlo_categories:
        raw["uniqlo"] = fetch_uniqlo(uniqlo_categories, per_keyword, token, max_charge_usd)
    return process(raw, do_tag, dry_run)[1]
