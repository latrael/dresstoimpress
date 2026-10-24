"""AI pipeline: closet tagging, try-on, pairing."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from typing import get_args

from ..models import ClosetItem, PairResult, Product, StyleTag
from .colors import find_duplicate
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
STYLE_VOCAB = set(get_args(StyleTag))


def _style_tags(raw: dict, n: int) -> list[str]:
    """Model style tags limited to the shared 10-word vocabulary (it sometimes adds "casual", "retro")."""
    tags = raw.get("style_tags") if isinstance(raw.get("style_tags"), list) else []
    return [t for t in dict.fromkeys(str(t).strip().lower() for t in tags) if t in STYLE_VOCAB][:n]


class NotClothing(Exception):
    pass


# ---------- /closet/tag ----------

def tag_image(image_url: str, hint: str | None = None) -> dict:
    """Raw tagger output for one garment image (cached per URL + hint). Raises NotClothing.

    `hint` = what the photo is selling (product name). Retailer photos often show a model in a
    whole outfit; the hint makes the tagger describe that one item, not the model's jeans."""
    hint = " ".join(str(hint or "").split())[:120]
    if text_mock():
        raw = {"label": "black tee", "category": "top", "color": "black", "pattern": "solid",
               "style_tags": ["streetwear"], "formality": 2}
    else:
        # same photo tagged twice (retries, re-uploads) costs nothing the second time
        key = hashlib.sha256((image_url + ("|" + hint if hint else "")).encode()).hexdigest()[:24]
        hit = store.get("tag_cache", key)
        if hit:
            raw = hit
        else:
            prompt = prompts.TAGGER + (prompts.TAGGER_HINT.format(hint=hint) if hint else "")
            raw = ai_json(prompt, image_url=image_url, max_tokens=200, model=CLAUDE_TAG_MODEL)
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
        style_tags=_style_tags(raw, 5),
        formality=min(5, max(1, int(raw.get("formality", 3)))),
        source="photo",
        label=" ".join(str(raw.get("label", "")).split()[:5]),
    )
    # same garment uploaded twice? the app can offer "you already have this - keep both?"
    item.duplicate_of = find_duplicate(item.model_dump(), store.list("closet_items", user_id=user_id))
    store.put("closet_items", item.id, item.model_dump())
    return item


# ---------- /tryon ----------

def _tryon_key(user_id: str, product_ids: list[str], closet_ids: list[str], body: str = "") -> str:
    """Cache key. Includes which body photo was used (its path, not host, so a tunnel change keeps the
    cache) so a new body photo never serves try-ons of the old one."""
    from urllib.parse import urlparse

    raw = (prompts.TRYON_VERSION + "|" + user_id + "|" + ",".join(sorted(product_ids)) + "|"
           + ",".join(sorted(closet_ids)) + "|" + (urlparse(body).path if body else ""))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


COLLAGE_RETRY_SECONDS = int(os.getenv("COLLAGE_RETRY_SECONDS", "600"))


def try_on(user_id: str, product_ids: list[str], closet_item_ids: list[str]) -> tuple[str, bool, str]:
    """Returns (image_url, cached, mode). mode "ai" = Gemini try-on; "collage" = outfit board
    fallback when AI images are unavailable (retried every COLLAGE_RETRY_SECONDS)."""
    user = store.get("users", user_id) or {}
    body = user.get("body_photo_url")
    key = _tryon_key(user_id, product_ids, closet_item_ids, body or "")
    hit = store.get("tryon_cache", key)
    if hit and (hit.get("mode", "ai") == "ai" or time.time() - hit.get("at", 0) < COLLAGE_RETRY_SECONDS
                or mock_mode("GEMINI_API_KEY")):
        return hit["image_url"], True, hit.get("mode", "ai")

    pieces = [p for pid in product_ids if (p := get_product(pid))]
    pieces += [c for cid in closet_item_ids if (c := store.get("closet_items", cid))]
    garments = [g["image_url"] for g in pieces]
    slots = [g.get("category") or "garment" for g in pieces]
    if not garments:
        raise ValueError("no garment images found for given ids")

    if os.getenv("MOCK_AI") == "1":  # UI development: instant placeholder, no downloads
        store.put("tryon_cache", key, {"image_url": garments[0], "user_id": user_id, "mode": "collage",
                                       "at": time.time()})
        return garments[0], False, "collage"

    TRYON_DIR.mkdir(parents=True, exist_ok=True)
    mode = "ai"
    img = None
    if body and not mock_mode("GEMINI_API_KEY"):
        try:
            img = gemini_image(prompts.tryon_prompt(slots), [body, *garments])
        except BadModelOutput:
            img = None  # quota, billing, budget cap, no image returned
    if img is None:
        from .collage import outfit_board

        mode = "collage"
        img = outfit_board(body, garments)
    name = f"{key}.png" if mode == "ai" else f"{key}-board.png"
    (TRYON_DIR / name).write_bytes(img)
    url = f"{PUBLIC_BASE}/static/tryon/{name}"
    store.put("tryon_cache", key, {"image_url": url, "user_id": user_id, "mode": mode, "at": time.time()})
    return url, False, mode


# ---------- /pair ----------

def _in_budget(p: dict, ranges: dict) -> bool:
    r = ranges.get(p["category"])
    price = p.get("sale_price_usd") or p["price_usd"]
    return not r or r[0] <= price <= r[1]


_REASON_STOP = {"for", "and", "with", "to", "that", "in", "on", "a", "an", "the", "or", "so", "as", "like", "into"}
_REASON_GENERIC = {"look", "looks", "style", "vibe", "vibes", "outfit", "outfits", "fit", "fits", "closet", "wardrobe",
                   "pieces", "piece", "items", "item", "aesthetic", "go-to", "go-tos", "favorite", "favorites", "own"}
_PARTNER = {"top": "bottom", "outerwear": "bottom", "bottom": "top", "shoes": "bottom", "dress": "shoes",
            "accessory": "top"}


def _unknown_closet_ref(reason: str, closet: list[dict]) -> bool:
    """True when the reason says "your <thing>" and <thing> isn't anything in the closet (a made-up item)."""
    import re

    from .colors import _COLOR_WORDS
    from .finder import item_type

    labels = [(c.get("label") or f'{c.get("color", "")} {c.get("category", "")}').lower() for c in closet]
    label_words = {w for lbl in labels for w in re.findall(r"[a-z0-9-]+", lbl)}
    label_types = {item_type(lbl) for lbl in labels} - {None}
    for m in re.finditer(r"\byour\s+([a-z0-9 -]+)", reason.lower()):
        nouns = []
        for w in re.findall(r"[a-z0-9-]+", m.group(1))[:5]:
            if w in _REASON_STOP:
                break
            if w not in _COLOR_WORDS and w not in _REASON_GENERIC and len(w) > 2:
                nouns.append(w)
        if nouns and not any(w in label_words or w.rstrip("s") in label_words
                             or item_type(w) in label_types or item_type(w.rstrip("s")) in label_types
                             for w in nouns):
            return True
    return False


def _safe_reason(r: PairResult, product: dict, closet: list[dict]) -> PairResult:
    """Replace a reason that names a closet item the user doesn't have with one that names a real item."""
    if not closet or not _unknown_closet_ref(r.reason, closet):
        return r
    by_id = {c["id"]: c for c in closet}
    item = next((by_id[c] for c in r.pairs_with if c in by_id), None)
    if item is None:
        want = _PARTNER.get(product.get("category"), "bottom")
        item = next((c for c in closet if c.get("category") == want), closet[0])
    label = item.get("label") or f'{item.get("color", "")} {item.get("category", "")}'.strip()
    return r.model_copy(update={"reason": f"pairs with your {label}", "pairs_with": [item["id"]]})


def _fallback(cands: list[dict], ranges: dict, k: int, closet: list[dict] | None = None,
              style_text: str = "") -> list[PairResult]:
    """No-AI ranking (Claude off, over budget, or bad output): in-budget first, then the
    outfit rules scorer (category fit, color harmony, patterns, style overlap)."""
    from .outfit_rules import rank

    in_budget = [p for p in cands if _in_budget(p, ranges)]
    over = [p for p in cands if not _in_budget(p, ranges)]
    ranked = rank(in_budget, closet or [], style_text, k) + rank(over, closet or [], style_text, k)
    return [PairResult(product_id=r["product_id"], id=r["product_id"], score=r["score"],
                       reason=r["reason"], pairs_with=r["pairs_with"]) for r in ranked[:k]]


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
        return _fallback(cands, ranges, k, closet, user.get("style_text", ""))

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
            raw = ai_json(prompt, max_tokens=2000, model=CLAUDE_PAIR_MODEL)
        except BadModelOutput:
            return _fallback(cands, ranges, k, closet, user.get("style_text", ""))
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
            reason=" ".join(str(r.get("reason", "")).split()[:12]).rstrip(".") or "pairs with your closet",
            pairs_with=[c for c in r.get("pairs_with", []) if c in closet_ids],
        ))
    by_id = {p["id"]: p for p in cands}
    out = [_safe_reason(r, by_id[r.product_id], closet) for r in out]
    out.sort(key=lambda r: r.score, reverse=True)
    out = out[:k]
    if not out:
        return _fallback(cands, ranges, k, closet, user.get("style_text", ""))
    if len(out) < k:
        # Claude often ranks fewer than asked; top up with rules-based picks (free) so every feed
        # card gets a reason, ranked below Claude's picks
        have, floor = {r.product_id for r in out}, min(r.score for r in out)
        rest = [p for p in cands if p["id"] not in have]
        for r in _fallback(rest, ranges, k - len(out), closet, user.get("style_text", "")):
            out.append(r.model_copy(update={"score": round(min(r.score, floor) * 0.99, 4)}))
    # budget-first: anything in the user's price range ranks above anything outside it
    out.sort(key=lambda r: (not _in_budget(by_id.get(r.product_id) or get_product(r.product_id), ranges), -r.score))
    return out


# ---------- Fit Check: shop the fit ----------

def shop_fit(viewer_id: str, tagged: list[dict]) -> list[dict]:
    """Shoppable cards for a friend's Fit Check post, ranked against the viewer's closet.

    Each result is a Product plus `reason`, `pairs_with`, and `matched_tag` (the post label it answers).
    Tags with no product match yet are skipped; Nabil can run Apify for that retailer and call again.
    """
    from .finder import find_products

    from concurrent.futures import ThreadPoolExecutor

    products = list_products()
    matched: dict[str, str] = {}
    # items that need a live store search take ~5 s each: run them side by side, keep post order
    with ThreadPoolExecutor(max(1, min(4, len(tagged)))) as ex:
        found = list(ex.map(lambda t: find_products(t, products), tagged))
    from .finder import match_score

    order: dict[str, tuple[int, float]] = {}
    for i, (tag, hits) in enumerate(zip(tagged, found)):
        seen_styles = set()
        for p in sorted(hits, key=lambda h: -match_score(tag, h)):  # exact item first
            style = (p.get("retailer"), (p.get("name") or "").lower())
            if style in seen_styles or p["id"] in matched:
                continue  # one card per style: colour variants of the same item collapse
            seen_styles.add(style)
            matched[p["id"]] = tag.get("label", "")
            order[p["id"]] = (i, -match_score(tag, p))
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
    # the post's items in post order, closest match first; closet fit only breaks ties
    out.sort(key=lambda d: (*order[d["id"]], -d["score"]))
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
            "style_tags": _style_tags(r, 3),
        })
    return out[:8]



def tag_product(image_url: str, hint: str | None = None) -> dict:
    """Tags for a catalog product image (Nabil's ingest). Same vocabulary as closet items so
    pairing compares like with like. Returns contract fields plus NABIL.md's `tags` object.
    Pass the product name as `hint` for photos of a model wearing a full outfit."""
    from .compat import to_nabil_tags

    raw = tag_image(image_url, hint)
    item = {
        "label": " ".join(str(raw.get("label", "")).split()[:5]),
        "category": raw.get("category") if raw.get("category") in CATEGORIES else "top",
        "color": str(raw.get("color", "")),
        "pattern": raw.get("pattern") if raw.get("pattern") in
        {"solid", "striped", "plaid", "graphic", "floral", "other"} else "other",
        "style_tags": _style_tags(raw, 5),
        "formality": min(5, max(1, int(raw.get("formality", 3)))),
    }
    return {**item, "tags": to_nabil_tags(item)}
