"""AI pipeline: closet tagging, try-on, pairing."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from typing import NamedTuple, get_args

from ..models import ClosetItem, PairResult, Product, StyleTag
from .colors import find_duplicate
from .compat import get_product, list_products
from ..store import DATA_DIR, store
from . import prompts
import logging
import threading
import time

from .llm import (CLAUDE_PAIR_MODEL, CLAUDE_TAG_MODEL, BadModelOutput, ai_json, gemini_image,
                  mock_mode, text_mock)
from .memory import style_memory
from .reason_polish import polish_reason

log = logging.getLogger(__name__)

TRYON_DIR = DATA_DIR / "tryon"
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "http://localhost:8000")
PAIR_TTL = int(os.getenv("PAIR_CACHE_SECONDS", "600"))
# Reason bank: every Claude ranking for a user (same closet, style text and budgets) is kept for an
# hour, keyed by product. A swipe changes the candidate list, which used to mean a fresh ~6 s Claude
# call on the next /feed. Now /feed answers at once from the bank while Claude re-ranks in the
# background, so the next load picks up what the swipes taught it. PAIR_REUSE=0 turns this off.
PAIR_REUSE = os.getenv("PAIR_REUSE", "1") != "0"
PAIR_BANK_TTL = int(os.getenv("PAIR_BANK_SECONDS", "3600"))
PAIR_BANK_MAX = 120
# Rules-first pairing: Claude re-ranks at most this many rules-shortlisted candidates (>= k), and its score
# counts PAIR_LLM_WEIGHT of the blend (the rest is the rules score), so a re-run gives the same order.
PAIR_SHORTLIST = int(os.getenv("PAIR_SHORTLIST", "20"))
PAIR_LLM_WEIGHT = float(os.getenv("PAIR_LLM_WEIGHT", "0.5"))
_refreshing: set[str] = set()
_refresh_lock = threading.Lock()
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
        key = (prompts.TAGGER_VERSION + "-"
               + hashlib.sha256((image_url + ("|" + hint if hint else "")).encode()).hexdigest()[:24])
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


class TryOnResult(NamedTuple):
    image_url: str
    cached: bool
    mode: str                    # "ai" = Gemini try-on; "collage" = outfit board fallback
    source_photo_url: str | None  # the user's photo that was edited (image 1), None without any photo


def try_on(user_id: str, product_ids: list[str], closet_item_ids: list[str]) -> TryOnResult:
    """Returns TryOnResult(image_url, cached, mode, source_photo_url). mode "ai" = Gemini try-on; "collage" =
    outfit board fallback when AI images are unavailable (retried every COLLAGE_RETRY_SECONDS).
    Image 1 is the user's best photo for these garments (tryon_source.pick_source_photo: the body photo or one
    of their own outfit photos that shows a garment of the same category, full body, not cut off), so the v5
    in-place edit has a real region to replace; its url is part of the cache key."""
    from .tryon_source import pick_source_photo

    user = store.get("users", user_id) or {}
    pieces = [p for pid in product_ids if (p := get_product(pid))]
    pieces += [c for cid in closet_item_ids if (c := store.get("closet_items", cid))]
    garments = [g["image_url"] for g in pieces]
    slots = [g.get("category") or "garment" for g in pieces]
    if not garments:
        raise ValueError("no garment images found for given ids")

    src = pick_source_photo(user_id, pieces, user)
    body = src["url"] if src else None
    boxes = src["boxes"] if src else [None] * len(pieces)
    key = _tryon_key(user_id, product_ids, closet_item_ids, body or "")
    hit = store.get("tryon_cache", key)
    if hit and (hit.get("mode", "ai") == "ai" or time.time() - hit.get("at", 0) < COLLAGE_RETRY_SECONDS
                or mock_mode("GEMINI_API_KEY")):
        return TryOnResult(hit["image_url"], True, hit.get("mode", "ai"), hit.get("source_photo_url", body))

    if os.getenv("MOCK_AI") == "1":  # UI development: instant placeholder, no downloads
        store.put("tryon_cache", key, {"image_url": garments[0], "user_id": user_id, "mode": "collage",
                                       "at": time.time(), "source_photo_url": body})
        return TryOnResult(garments[0], False, "collage", body)

    TRYON_DIR.mkdir(parents=True, exist_ok=True)
    mode = "ai"
    img = None
    if body and not mock_mode("GEMINI_API_KEY"):
        try:
            bp = user.get("body_profile") or {}
            names = [g.get("name") or g.get("label") or "" for g in pieces]
            size = None
            try:  # the size we'd recommend for the first catalog piece, so the drape matches
                from .sizing import recommend_size

                first = next((p for p in pieces if p.get("sizes")), None)
                if first and bp.get("height_cm") and bp.get("weight_kg"):
                    size = recommend_size(first, bp["height_cm"], bp["weight_kg"], fit=bp.get("fit") or "regular",
                                          shoe_us=bp.get("shoe_us"), waist_in=bp.get("waist_in")).get("size")
            except Exception:  # sizing is a nicety here, never a reason to skip the try-on
                size = None
            img = gemini_image(prompts.tryon_prompt(slots, names, bp.get("build"), size, boxes), [body, *garments])
        except BadModelOutput:
            img = None  # quota, billing, budget cap, no image returned
    if img is None:
        from .collage import outfit_board

        mode = "collage"
        img = outfit_board(body, garments)
    name = f"{key}.png" if mode == "ai" else f"{key}-board.png"
    (TRYON_DIR / name).write_bytes(img)
    url = f"{PUBLIC_BASE}/static/tryon/{name}"
    store.put("tryon_cache", key, {"image_url": url, "user_id": user_id, "mode": mode, "at": time.time(),
                                   "source_photo_url": body})
    return TryOnResult(url, False, mode, body)


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

    # One token set per closet item: every word of "your <phrase>" (colour, brand and noun alike) must sit in
    # the SAME item, so "your black tee" is unknown when the closet has a white tee and black pants.
    items: list[tuple[set[str], str | None]] = []
    for c in closet:
        lbl = (c.get("label") or f'{c.get("color", "")} {c.get("category", "")}').lower()
        text = " ".join(filter(None, [lbl, str(c.get("brand") or ""), str(c.get("color") or ""),
                                      str(c.get("category") or "")])).lower()
        words = set(re.findall(r"[a-z0-9-]+", text))
        words |= {w.rstrip("s") for w in words}
        items.append((words, item_type(lbl)))
    for m in re.finditer(r"\byour\s+([a-z0-9 -]+)", reason.lower()):
        words = []
        for w in re.findall(r"[a-z0-9-]+", m.group(1))[:5]:
            if w in _REASON_STOP:
                break
            if w not in _REASON_GENERIC and len(w) > 2:
                words.append(w)
        nouns = [w for w in words if w not in _COLOR_WORDS]
        if not nouns:
            continue  # "your look", "your closet": not an item reference
        # Known only when ONE closet item carries a colour word AND at least one of the nouns (as a word
        # or by type), so "your black tee" is unknown when the closet has a white tee and black pants.
        colours = [w for w in words if w in _COLOR_WORDS]

        def has(w: str, toks: set[str]) -> bool:
            return w in toks or w.rstrip("s") in toks

        def known(toks: set[str], typ: str | None) -> bool:
            if colours and not any(has(c, toks) for c in colours):  # any(): "denim blue" is one colour
                return False
            return any(has(n, toks) or (typ is not None and (item_type(n) == typ or item_type(n.rstrip("s")) == typ))
                       for n in nouns)

        if not any(known(toks, typ) for toks, typ in items):
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


def _closet_repr(c: dict) -> dict:
    return {"category": c.get("category"), "color": c.get("color"), "pattern": c.get("pattern"),
            "style_tags": c.get("style_tags") or [], "formality": c.get("formality"), "label": c.get("label")}


def _bad_pair(product: dict, item: dict) -> bool:
    """A closet item that can't be worn with the product: a hard clash (athletic<->formal, 3+ formality steps)
    or the same category (a top doesn't 'pair with' another top)."""
    from .complete_look import _as_closet_shape, clashes_with

    if item.get("category") == product.get("category") and product.get("category") != "accessory":
        return True
    return clashes_with(_as_closet_shape(product, "catalog"), _closet_repr(item))


def _rules_rank(cands: list[dict], closet: list[dict], style_text: str) -> list[dict]:
    """Every candidate scored by the outfit rules, with pairs_with filtered to wearable closet items."""
    from .outfit_rules import rank

    by_id = {c["id"]: c for c in closet}
    prods = {p["id"]: p for p in cands}
    out = []
    for r in rank(cands, closet, style_text, k=len(cands)):
        p = prods.get(r["product_id"]) or {}
        pw = [c for c in r.get("pairs_with", []) if c in by_id and not _bad_pair(p, by_id[c])]
        if not pw:
            pw = [c["id"] for c in closet if not _bad_pair(p, c)][:1]
        out.append({**r, "pairs_with": pw})
    return out


def _validated(r: PairResult, product: dict, closet: list[dict], rule: dict | None) -> PairResult:
    """Drop pairs_with items that clash with or duplicate the product. When Claude's pairing was built on a
    clashing item, its reason is about that item too, so the rules' reason and pairing take over."""
    by_id = {c["id"]: c for c in closet}
    keep = [c for c in r.pairs_with if c in by_id and not _bad_pair(product, by_id[c])]
    if keep == list(r.pairs_with):
        return r
    if keep:
        return r.model_copy(update={"pairs_with": keep})
    rule = rule or {}
    return r.model_copy(update={"pairs_with": rule.get("pairs_with", []),
                                "reason": polish_reason(rule.get("reason", "")) or "Pairs with your closet"})


def _fallback(cands: list[dict], ranges: dict, k: int, closet: list[dict] | None = None,
              style_text: str = "") -> list[PairResult]:
    """No-AI ranking (Claude off, over budget, or bad output): in-budget first, then the
    outfit rules scorer (category fit, color harmony, patterns, style overlap)."""
    in_budget = [p for p in cands if _in_budget(p, ranges)]
    over = [p for p in cands if not _in_budget(p, ranges)]
    ranked = _rules_rank(in_budget, closet or [], style_text)[:k] + _rules_rank(over, closet or [], style_text)[:k]
    return [PairResult(product_id=r["product_id"], id=r["product_id"], score=r["score"],
                       reason=polish_reason(r["reason"]) or r["reason"], pairs_with=r["pairs_with"])
            for r in ranked[:k]]


def _bank_key(user_id: str, closet: list[dict], user: dict) -> str:
    """The reason bank is valid while the closet, style text and budgets stay the same."""
    state = (f"bank|{prompts.PAIR_VERSION}|{user_id}|{','.join(sorted(c['id'] for c in closet))}|{user.get('style_text', '')}|"
             f"{json.dumps(user.get('price_ranges', {}), sort_keys=True)}")
    return "bank_" + hashlib.sha256(state.encode()).hexdigest()[:20]


def _from_bank(bkey: str, valid_ids: set[str], want: int) -> list[dict] | None:
    """Banked rankings for the current candidates, if they still cover at least half a page."""
    if not PAIR_REUSE:
        return None
    bank = store.get("pair_cache", bkey)
    if not bank or time.time() - bank.get("at", 0) >= PAIR_BANK_TTL:
        return None
    kept = [r for r in bank.get("raw") or [] if isinstance(r, dict) and r.get("product_id") in valid_ids]
    return kept if len(kept) >= max(1, want // 2) else None


def _remember(ckey: str, bkey: str, raw, user_id: str) -> None:
    """Store an exact-match cache entry and merge the ranking into the user's reason bank.
    Newest ranking first; older entries keep their reason with a slightly lower score."""
    now = time.time()
    store.put("pair_cache", ckey, {"at": now, "raw": raw, "user_id": user_id})
    fresh = [r for r in raw if isinstance(r, dict) and r.get("product_id")] if isinstance(raw, list) else []
    have = {r["product_id"] for r in fresh}
    old = (store.get("pair_cache", bkey) or {}).get("raw") or []
    aged = [{**r, "score": round(float(r.get("score", 0.5)) * 0.9, 4)}
            for r in old if isinstance(r, dict) and r.get("product_id") not in have]
    store.put("pair_cache", bkey, {"at": now, "raw": (fresh + aged)[:PAIR_BANK_MAX], "user_id": user_id})


def _spawn(fn) -> None:
    """Run fn off the request thread (tests swap this to run inline or not at all)."""
    threading.Thread(target=fn, daemon=True).start()


def _refresh_later(ckey: str, bkey: str, prompt: str, user_id: str) -> None:
    """Re-rank with Claude in the background, at most one refresh per bank at a time."""
    with _refresh_lock:
        if bkey in _refreshing:
            return
        _refreshing.add(bkey)

    def run():
        try:
            _remember(ckey, bkey, ai_json(prompt, max_tokens=2000, model=CLAUDE_PAIR_MODEL), user_id)
        except Exception as e:  # noqa: BLE001 - a failed refresh just leaves the bank as it was
            log.warning("background pair refresh failed: %s", e)
        finally:
            with _refresh_lock:
                _refreshing.discard(bkey)

    _spawn(run)


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

    # Rules first (free, deterministic): score every candidate with the outfit rules, then hand Claude only a
    # short list to re-rank and explain. A 30-50 item pointwise ranking moved around between identical calls;
    # a 2k shortlist with blended scores and fixed tie-breaks doesn't, and the prompt is a third of the size.
    rules = {r["product_id"]: r for r in _rules_rank(cands, closet, user.get("style_text", ""))}
    cands = sorted(cands, key=lambda p: (not _in_budget(p, ranges), -rules.get(p["id"], {}).get("score", 0.0), p["id"]))
    cands = cands[:max(k, min(PAIR_SHORTLIST, 2 * k))]

    slim_closet = [{"id": c["id"], "label": c.get("label") or f'{c["color"]} {c["category"]}',
                    "brand": c.get("brand"),  # so a reason can say "your Stüssy tee"
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
    state = (f"{prompts.PAIR_VERSION}|{user_id}|{','.join(sorted(p['id'] for p in cands))}|{len(closet)}|{len(swiped)}|{k}|"
             f"{user.get('style_text', '')}|{json.dumps(ranges, sort_keys=True)}")
    ckey = hashlib.sha256(state.encode()).hexdigest()[:24]
    bkey = _bank_key(user_id, closet, user)
    valid_ids = {p["id"] for p in cands}
    hit = store.get("pair_cache", ckey)
    if hit and time.time() - hit["at"] < PAIR_TTL:
        raw = hit["raw"]
    elif (banked := _from_bank(bkey, valid_ids, min(k, len(cands)))) is not None:
        raw = banked  # instant; Claude re-ranks with the new swipes for the next call
        _refresh_later(ckey, bkey, prompt, user_id)
    else:
        try:
            raw = ai_json(prompt, max_tokens=2000, model=CLAUDE_PAIR_MODEL)
        except BadModelOutput:
            return _fallback(cands, ranges, k, closet, user.get("style_text", ""))
        _remember(ckey, bkey, raw, user_id)

    closet_ids = {c["id"] for c in closet}
    out: list[PairResult] = []
    for r in raw if isinstance(raw, list) else []:
        if r.get("product_id") not in valid_ids:
            continue  # drop hallucinated ids
        out.append(PairResult(
            product_id=r["product_id"],
            id=r["product_id"],
            score=min(1.0, max(0.0, float(r.get("score", 0.5)))),
            reason=polish_reason(r.get("reason", "")) or "Pairs with your closet",
            pairs_with=[c for c in r.get("pairs_with", []) if c in closet_ids],
        ))
    by_id = {p["id"]: p for p in cands}
    out = [_validated(r, by_id[r.product_id], closet, rules.get(r.product_id)) for r in out]
    out = [_safe_reason(r, by_id[r.product_id], closet) for r in out]
    # blended score: half Claude, half rules; ties broken by the rules score then id, so a re-run is identical
    out = [r.model_copy(update={"score": round(PAIR_LLM_WEIGHT * r.score
                                               + (1 - PAIR_LLM_WEIGHT) * rules.get(r.product_id, {}).get("score", 0.5), 4)})
           for r in out]
    out.sort(key=lambda r: (-r.score, -rules.get(r.product_id, {}).get("score", 0.0), r.product_id))
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
    # one consistent voice on every card (capitalized, no dangling "...with your", <= 12 words)
    out = [r.model_copy(update={"reason": polish_reason(r.reason) or r.reason}) for r in out]
    out.sort(key=lambda r: (not _in_budget(by_id.get(r.product_id) or get_product(r.product_id), ranges), -r.score,
                            r.product_id))
    return out


# ---------- Fit Check: shop the fit ----------

SHOP_PER_TAG = 3          # flat /shop: cards per tagged piece (unchanged)
SHOP_GROUPED_PER_TAG = 6  # grouped /shop: similar items shown under each piece's chip


def _shop_fit_rows(viewer_id: str, tagged: list[dict], per_tag: int, keep=None) -> list[tuple[int, dict]]:
    """(tag index, card) pairs behind shop_fit / shop_fit_grouped: post order, closest match first.
    `keep(product) -> bool` filters the catalog before matching, so each tag fills up with products the
    viewer can see, and the cards after (a tag's pinned product_id / live results skip the catalog)."""
    from .finder import find_products

    from concurrent.futures import ThreadPoolExecutor

    products = list_products()
    if keep is not None:
        products = [p for p in products if keep(p)]
    matched: dict[str, tuple[int, str]] = {}
    # items that need a live store search take ~5 s each: run them side by side, keep post order
    with ThreadPoolExecutor(max(1, min(4, len(tagged)))) as ex:
        found = list(ex.map(lambda t: find_products(t, products, per_tag), tagged))
    if keep is not None:
        found = [[p for p in hits if keep(p)] for hits in found]
    from .finder import match_score

    order: dict[str, tuple[int, float]] = {}
    for i, (tag, hits) in enumerate(zip(tagged, found)):
        seen_styles = set()
        for p in sorted(hits, key=lambda h: -match_score(tag, h)):  # exact item first
            style = (p.get("retailer"), (p.get("name") or "").lower())
            if style in seen_styles or p["id"] in matched:
                continue  # one card per style: colour variants of the same item collapse
            seen_styles.add(style)
            matched[p["id"]] = (i, tag.get("label", ""))
            order[p["id"]] = (i, -match_score(tag, p))
    if not matched:
        return []

    ranked = {r.product_id: r for r in pair(viewer_id, list(matched), k=len(matched))}
    out = []
    for pid, (i, label) in matched.items():
        p = get_product(pid)
        r = ranked.get(pid)
        out.append((i, {**p,
                        "reason": r.reason if r else f"from the fit: {label}",
                        "pairs_with": r.pairs_with if r else [],
                        "score": r.score if r else 0.0,
                        "matched_tag": label}))
    # the post's items in post order, closest match first; closet fit only breaks ties
    out.sort(key=lambda row: (*order[row[1]["id"]], -row[1]["score"]))
    return out


def shop_fit(viewer_id: str, tagged: list[dict], per_tag: int = SHOP_PER_TAG, keep=None) -> list[dict]:
    """Shoppable cards for a friend's Fit Check post, ranked against the viewer's closet.

    Each result is a Product plus `reason`, `pairs_with`, and `matched_tag` (the post label it answers).
    Tags with no product match yet are skipped; Nabil can run Apify for that retailer and call again.
    `keep(product) -> bool`: only products the viewer should see (their shop_for department).
    """
    return [card for _, card in _shop_fit_rows(viewer_id, tagged, per_tag, keep)]


def shop_tag_summary(tag: dict) -> dict:
    """The part of a FitTag the app needs to draw the piece's chip / pin."""
    return {k: tag.get(k) for k in ("label", "category", "color", "box", "product_id")}


def shop_fit_grouped(viewer_id: str, tagged: list[dict], per_tag: int = SHOP_GROUPED_PER_TAG,
                     keep=None) -> list[dict]:
    """shop_fit, one group per tagged piece, in post order: [{"tag": {label, category, color, box,
    product_id}, "products": [card, ...]}]. A piece with no match keeps its chip with `products: []`.
    `keep(product) -> bool`: only products the viewer should see (their shop_for department)."""
    groups = [{"tag": shop_tag_summary(t), "products": []} for t in tagged]
    for i, card in _shop_fit_rows(viewer_id, tagged, per_tag, keep):
        groups[i]["products"].append(card)
    return groups


# ---------- Fit Check: auto-tag an outfit photo ----------

BRAND_TO_RETAILER = {"zara": "zara", "h&m": "hm", "hm": "hm", "asos": "asos", "uniqlo": "uniqlo",
                     "mango": "mango"}


def tag_fit(image_url: str) -> list[dict]:
    """Items visible in an outfit photo, shaped as Fit Check tags (label, retailer?) plus
    category/color/pattern/style_tags/brand. Feed the result to shop_fit() as `tagged`."""
    if text_mock():
        raw = [{"label": "light-wash baggy jeans", "category": "bottom", "color": "light blue",
                "pattern": "solid", "style_tags": ["y2k"], "brand": None, "box": [0.25, 0.5, 0.75, 0.95]},
               {"label": "white baby tee", "category": "top", "color": "white", "pattern": "solid",
                "style_tags": ["y2k"], "brand": None, "box": [0.28, 0.2, 0.72, 0.5]}]
    else:
        key = f"fit{prompts.FIT_TAGGER_VERSION}-" + hashlib.sha256(image_url.encode()).hexdigest()[:24]
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
            "box": fit_box(r.get("box")),
        })
    return out[:8]


def fit_box(box) -> list[float] | None:
    """A tag's pin box as [x0, y0, x1, y1] fractions of the photo (0-1, rounded), or None when the model
    gave no usable box. 0-1000 boxes are rescaled; pixel boxes can't be (no image size here) and drop."""
    from .digitize import normalize_box

    try:
        if box is None or max(float(v) for v in box) > 1000:
            return None
    except (TypeError, ValueError):
        return None
    b = normalize_box(box, 1, 1)
    return [round(v, 3) for v in b] if b else None



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
    dept = raw.get("department")
    return {**item, "department": dept if dept in DEPARTMENTS else None, "tags": to_nabil_tags(item)}


# ---------- catalog stage 2 extras: department fallback + summary (sprint-2 B3 / B4 / B5) ----------

DEPARTMENTS = {"men", "women", "unisex"}
_WOMEN_RE = re.compile(r"women'?s|ladies|\bwoman\b|\bdress(es)?\b(?!\s+(shirt|shoe|pant|sock|boot))|\bskirts?\b|"
                       r"\bbras?\b|\bbikinis?\b|\bblouses?\b|ladies_|/women/|/ladies/", re.I)
_MEN_RE = re.compile(r"\bmen'?s\b|\bman\b|men_|/men/", re.I)
SUMMARY_MAX_CHARS = 160


def department_from_text(name: str | None, url: str | None = None, category_code: str | None = None) -> str | None:
    """Rules fallback for Product.department from the name, product URL and the store's category
    code (H&M `ladies_...` / `men_...`). Women's words win over "men" (which "women" contains)."""
    text = " ".join(str(s or "") for s in (name, url, category_code))
    if _WOMEN_RE.search(text):
        return "women"
    if _MEN_RE.search(text):
        return "men"
    return None


def _clip_summary(text: str) -> str:
    """At most 2 sentences and SUMMARY_MAX_CHARS, cut at a word boundary."""
    text = " ".join(str(text or "").replace('"', "").split())
    sentences = re.findall(r"[^.!?]+[.!?]?", text)
    text = "".join(sentences[:2]).strip()
    if len(text) > SUMMARY_MAX_CHARS:
        cut = text[: SUMMARY_MAX_CHARS - 1]
        space = cut.rfind(" ")
        text = (cut[:space] if space > 40 else cut).rstrip(" ,;:") + "…"
    return text


def rules_summary(p: dict) -> str:
    """Template one-liner from the attributes, used when AI is off or the model answer is unusable."""
    label = (p.get("label") or "").strip()
    color = (p.get("colors") or [""])[0] if isinstance(p.get("colors"), list) else ""
    thing = label or " ".join(str(p.get("name") or "item").split()[:4]).lower()
    if color and color.lower() not in thing.lower():
        thing = f"{color.lower()} {thing}"
    article = "An" if thing[:1].lower() in "aeiou" else "A"
    styles = [s for s in (p.get("style_tags") or []) if isinstance(s, str)][:2]
    if styles:
        tail = f" with a {' and '.join(styles)} feel"
    else:
        cat = p.get("category") or ""
        tail = f" for everyday {cat} wear" if cat else ""
    return _clip_summary(f"{article} {thing}{tail}.")


def summarize_product(p: dict, force: bool = False) -> str:
    """Product.summary: 1-2 plain sentences (<= 160 chars). Haiku condenses the retailer description,
    or writes a one-liner from the attributes when there is none (H&M). Cached per product id +
    SUMMARY_VERSION so re-runs are free; rules template when AI is off."""
    if text_mock():
        return rules_summary(p)
    key = f"sum{prompts.SUMMARY_VERSION}-{p['id']}"
    if not force and (hit := store.get("summary_cache", key)):
        return hit["summary"]
    desc = " ".join(str(p.get("description") or "").split())[:1500]
    colors = p.get("colors") or []
    prompt = prompts.SUMMARY.format(
        name=" ".join(str(p.get("name") or "").split())[:120],
        category=p.get("category") or "unknown",
        color=", ".join(str(c) for c in colors[:2]) or "unknown",
        style=", ".join(p.get("style_tags") or []) or "unknown",
        label_part=f"; item: {p['label']}" if p.get("label") else "",
        description=desc or "none",
    )
    raw = ai_json(prompt, max_tokens=120, model=CLAUDE_TAG_MODEL)
    text = _clip_summary(raw.get("summary", "")) if isinstance(raw, dict) else ""
    if len(text) < 12:
        text = rules_summary(p)
    store.put("summary_cache", key, {"summary": text})
    return text


# ---------- sprint 4 §10: reels Home (closet picks, try-on status, prefetch) ----------
from .feed_tryon import closet_picks, prefetch_tryons, tryon_status  # noqa: E402,F401
