"""AI pipeline: closet tagging, try-on, pairing."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from ..models import ClosetItem, PairResult, Product
from .compat import get_product, list_products
from ..store import DATA_DIR, store
from . import prompts
import time

from .llm import (CLAUDE_PAIR_MODEL, CLAUDE_TAG_MODEL, BadModelOutput, ai_json, gemini_image,
                  mock_mode, text_mock)
from .memory import style_memory

TRYON_DIR = DATA_DIR / "tryon"
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "http://localhost:8000")
PAIR_TTL = int(os.getenv("PAIR_CACHE_SECONDS", "600"))
CATEGORIES = {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}


class NotClothing(Exception):
    pass


# ---------- /closet/tag ----------

def tag_image(image_url: str) -> dict:
    """Raw tagger output for one garment image (cached per URL). Raises NotClothing."""
    if text_mock():
        raw = {"label": "black tee", "category": "top", "color": "black", "pattern": "solid",
               "style_tags": ["streetwear"], "formality": 2}
    else:
        # same photo tagged twice (retries, re-uploads) costs nothing the second time
        key = hashlib.sha256(image_url.encode()).hexdigest()[:24]
        hit = store.get("tag_cache", key)
        if hit:
            raw = hit
        else:
            raw = ai_json(prompts.TAGGER, image_url=image_url, max_tokens=200,
                              model=CLAUDE_TAG_MODEL)
            if isinstance(raw, dict):
                store.put("tag_cache", key, raw)

    if isinstance(raw, dict) and raw.get("error") == "not_clothing":
        raise NotClothing()
    if not isinstance(raw, dict):
        raise BadModelOutput("tagger returned non-object")
    return raw


def tag_closet_item(user_id: str, image_url: str) -> ClosetItem:
    raw = tag_image(image_url)
    item = ClosetItem(
        id=f"ci_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        image_url=image_url,
        category=raw.get("category", "top") if raw.get("category") in CATEGORIES else "top",
        color=str(raw.get("color", "unknown")),
        pattern=raw.get("pattern", "other") if raw.get("pattern") in
        {"solid", "striped", "plaid", "graphic", "floral", "other"} else "other",
        style_tags=list(raw.get("style_tags", []))[:5],
        formality=min(5, max(1, int(raw.get("formality", 3)))),
        source="photo",
        label=" ".join(str(raw.get("label", "")).split()[:5]),
    )
    store.put("closet_items", item.id, item.model_dump())
    return item


# ---------- /tryon ----------

def _tryon_key(user_id: str, product_ids: list[str], closet_ids: list[str]) -> str:
    raw = user_id + "|" + ",".join(sorted(product_ids)) + "|" + ",".join(sorted(closet_ids))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def try_on(user_id: str, product_ids: list[str], closet_item_ids: list[str]) -> tuple[str, bool]:
    key = _tryon_key(user_id, product_ids, closet_item_ids)
    hit = store.get("tryon_cache", key)
    if hit:
        return hit["image_url"], True

    user = store.get("users", user_id) or {}
    body = user.get("body_photo_url")
    if not body:
        raise ValueError("user has no body_photo_url")

    garments = [p["image_url"] for pid in product_ids if (p := get_product(pid))]
    garments += [c["image_url"] for cid in closet_item_ids if (c := store.get("closet_items", cid))]
    if not garments:
        raise ValueError("no garment images found for given ids")

    if mock_mode("GEMINI_API_KEY"):
        url = garments[0]  # placeholder so the UI flow works
    else:
        img = gemini_image(prompts.TRYON, [body, *garments])
        TRYON_DIR.mkdir(parents=True, exist_ok=True)
        (TRYON_DIR / f"{key}.png").write_bytes(img)
        url = f"{PUBLIC_BASE}/static/tryon/{key}.png"

    store.put("tryon_cache", key, {"image_url": url, "user_id": user_id})
    return url, False


# ---------- /pair ----------

def _in_budget(p: dict, ranges: dict) -> bool:
    r = ranges.get(p["category"])
    price = p.get("sale_price_usd") or p["price_usd"]
    return not r or r[0] <= price <= r[1]


def _fallback(cands: list[dict], ranges: dict, k: int) -> list[PairResult]:
    ranked = sorted(cands, key=lambda p: (not _in_budget(p, ranges), p["price_usd"]))
    return [PairResult(product_id=p["id"], id=p["id"], score=0.5, reason="fits your style and budget",
                       pairs_with=[]) for p in ranked[:k]]


def pair(user_id: str, candidate_ids: list[str], k: int = 10) -> list[PairResult]:
    user = store.get("users", user_id) or {}
    ranges = user.get("price_ranges", {})
    closet = store.list("closet_items", user_id=user_id)
    swiped = {s["product_id"] for s in store.list("swipes", user_id=user_id)}

    if candidate_ids:
        cands = [p for pid in candidate_ids if (p := get_product(pid))]
    else:
        cands = [p for p in list_products() if p["id"] not in swiped]
    # keep budget matches first, cap prompt size
    cands = sorted(cands, key=lambda p: not _in_budget(p, ranges))[:50]
    if not cands:
        return []

    if text_mock() or not closet:
        return _fallback(cands, ranges, k)

    slim_closet = [{"id": c["id"], "label": c.get("label") or f'{c["color"]} {c["category"]}',
                    "category": c["category"], "color": c["color"], "pattern": c["pattern"],
                    "style_tags": c["style_tags"]} for c in closet]
    slim_cands = [{"id": p["id"], "name": p["name"], "brand": p["brand"],
                   "category": p["category"], "price_usd": p.get("sale_price_usd") or p["price_usd"],
                   "colors": p.get("colors", []), "style_tags": p.get("style_tags", [])}
                  for p in cands]
    prompt = prompts.PAIR.format(
        style_text=user.get("style_text", "") or "not given",
        price_ranges=json.dumps(ranges),
        closet_json=json.dumps(slim_closet),
        memory=style_memory(user_id, user.get("style_text", "")),
        products_json=json.dumps(slim_cands),
        k=k,
    )
    # Cache: same user, same candidates, same closet/swipe state -> reuse for 10 min.
    # The feed and shop-the-fit can hit this on every scroll; this keeps that free.
    state = (f"{user_id}|{','.join(sorted(p['id'] for p in cands))}|{len(closet)}|{len(swiped)}|{k}|"
             f"{user.get('style_text', '')}|{json.dumps(ranges, sort_keys=True)}")
    ckey = hashlib.sha256(state.encode()).hexdigest()[:24]
    hit = store.get("pair_cache", ckey)
    if hit and time.time() - hit["at"] < PAIR_TTL:
        raw = hit["raw"]
    else:
        try:
            raw = ai_json(prompt, max_tokens=1200, model=CLAUDE_PAIR_MODEL)
        except BadModelOutput:
            return _fallback(cands, ranges, k)
        store.put("pair_cache", ckey, {"at": time.time(), "raw": raw})

    valid_ids = {p["id"] for p in cands}
    closet_ids = {c["id"] for c in closet}
    out: list[PairResult] = []
    for r in raw if isinstance(raw, list) else []:
        if r.get("product_id") not in valid_ids:
            continue  # drop hallucinated ids
        out.append(PairResult(
            product_id=r["product_id"],
            id=r["product_id"],
            score=min(1.0, max(0.0, float(r.get("score", 0.5)))),
            reason=" ".join(str(r.get("reason", "")).split()[:8]) or "pairs with your closet",
            pairs_with=[c for c in r.get("pairs_with", []) if c in closet_ids],
        ))
    out.sort(key=lambda r: r.score, reverse=True)
    return out[:k] or _fallback(cands, ranges, k)


# ---------- Fit Check: shop the fit ----------

def shop_fit(viewer_id: str, tagged: list[dict]) -> list[dict]:
    """Shoppable cards for a friend's Fit Check post, ranked against the viewer's closet.

    Each result is a Product plus `reason`, `pairs_with`, and `matched_tag` (the post label it answers).
    Tags with no product match yet are skipped; Nabil can run Apify for that retailer and call again.
    """
    from .finder import find_products

    products = list_products()
    matched: dict[str, str] = {}
    for tag in tagged:
        for p in find_products(tag, products):
            matched.setdefault(p["id"], tag.get("label", ""))
    if not matched:
        return []

    ranked = {r.product_id: r for r in pair(viewer_id, list(matched), k=len(matched))}
    out = []
    for pid, label in matched.items():
        p = get_product(pid)
        r = ranked.get(pid)
        out.append({**p,
                    "reason": r.reason if r else f"from the fit: {label}",
                    "pairs_with": r.pairs_with if r else [],
                    "score": r.score if r else 0.0,
                    "matched_tag": label})
    out.sort(key=lambda d: d["score"], reverse=True)
    return out


# ---------- Fit Check: auto-tag an outfit photo ----------

BRAND_TO_RETAILER = {"zara": "zara", "h&m": "hm", "hm": "hm", "asos": "asos", "uniqlo": "uniqlo",
                     "mango": "mango"}


def tag_fit(image_url: str) -> list[dict]:
    """Items visible in an outfit photo, shaped as Fit Check tags (label, retailer?) plus
    category/color/pattern/style_tags/brand. Feed the result to shop_fit() as `tagged`."""
    if text_mock():
        raw = [{"label": "light-wash baggy jeans", "category": "bottom", "color": "light blue",
                "pattern": "solid", "style_tags": ["y2k"], "brand": None},
               {"label": "white baby tee", "category": "top", "color": "white", "pattern": "solid",
                "style_tags": ["y2k"], "brand": None}]
    else:
        key = "fit-" + hashlib.sha256(image_url.encode()).hexdigest()[:24]
        hit = store.get("tag_cache", key)
        if hit:
            raw = hit["items"]
        else:
            raw = ai_json(prompts.FIT_TAGGER, image_url=image_url, max_tokens=700, model=CLAUDE_TAG_MODEL)
            store.put("tag_cache", key, {"items": raw})
    out = []
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict) or not r.get("label"):
            continue
        brand = r.get("brand") or None
        out.append({
            "label": " ".join(str(r["label"]).split()[:5]),
            "retailer": BRAND_TO_RETAILER.get(str(brand).lower()) if brand else None,
            "brand": brand,
            "category": r.get("category") if r.get("category") in CATEGORIES else "accessory",
            "color": str(r.get("color", "")),
            "pattern": r.get("pattern", "other"),
            "style_tags": list(r.get("style_tags", []))[:3],
        })
    return out[:8]



def tag_product(image_url: str) -> dict:
    """Tags for a catalog product image (Nabil's ingest). Same vocabulary as closet items so
    pairing compares like with like. Returns contract fields plus NABIL.md's `tags` object."""
    from .compat import to_nabil_tags

    raw = tag_image(image_url)
    item = {
        "label": " ".join(str(raw.get("label", "")).split()[:5]),
        "category": raw.get("category") if raw.get("category") in CATEGORIES else "top",
        "color": str(raw.get("color", "")),
        "pattern": raw.get("pattern") if raw.get("pattern") in
        {"solid", "striped", "plaid", "graphic", "floral", "other"} else "other",
        "style_tags": list(raw.get("style_tags", []))[:5],
        "formality": min(5, max(1, int(raw.get("formality", 3)))),
    }
    return {**item, "tags": to_nabil_tags(item)}
