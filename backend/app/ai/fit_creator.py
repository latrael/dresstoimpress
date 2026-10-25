"""AI Fit Creator: complete outfits built ONLY from the user's own closet (sprint-4 ask: "3 fits only
from closet" — no catalog fill, no try-on render).

Pool = the user's closet pieces. Claude (FIT_CREATOR prompt) picks `count` outfits from it; ids are
validated, a missing top/bottom is filled by the outfit rules from the closet, and when AI is off or fails
the rules build one fit around each closet piece (complete_look, closet only). A slot the closet can't
fill (e.g. no shoes) is left out and listed in `missing`, so the app can say "add shoes to your closet".
Fits are cached for an hour and addressable by id. `candidate_pool` is kept for the department tests and
`/fits/{id}/cart` + `/fits/{id}/try-on` stay as routes but have nothing to buy / are not auto-rendered.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time

from ..store import store
from . import prompts
from .compat import as_product
from .complete_look import _as_closet_shape, complete_look
from .llm import CLAUDE_PAIR_MODEL, BadModelOutput, ai_json, text_mock
from .outfit_rules import score_product
from .sizing import recommend_size

log = logging.getLogger(__name__)

FIT_TTL = 3600
MAX_CANDIDATES = 40
SLOTS = ("top", "bottom", "shoes", "outerwear", "dress", "accessory")
ANCHOR_ORDER = {"top": 0, "bottom": 1, "dress": 2, "outerwear": 3, "shoes": 4, "accessory": 5}


class NoFits(Exception):
    """Both the AI and the rules came back with nothing (empty pool)."""


# ---------- body ----------

def _has_measurements(bp: dict) -> bool:
    return bool(bp.get("height_cm") and bp.get("weight_kg")) or bool(bp.get("usual_sizes"))


def _usual(product: dict, usual: str | None) -> str | None:
    for s in product.get("sizes") or []:
        if usual and str(s).strip().lower() == usual.strip().lower():
            return s
    return None


def _size_pick(p: dict, bp: dict) -> str | None:
    """What POST /size would pick for a contract-shape product (in-stock sizes only)."""
    usual = (bp.get("usual_sizes") or {}).get(p.get("category"))
    if not (bp.get("height_cm") and bp.get("weight_kg")):
        return _usual(p, usual)
    out = recommend_size(p, bp["height_cm"], bp["weight_kg"], fit=bp.get("fit") or "regular",
                         shoe_us=bp.get("shoe_us"), waist_in=bp.get("waist_in"))
    return out.get("size") or _usual(p, usual)


def _size_fields(raw: dict, bp: dict) -> dict:
    """your_size / in_your_size like the feed cards (null when we know nothing about their size)."""
    if not _has_measurements(bp):
        return {"your_size": None, "in_your_size": None}
    shaped = as_product(raw)
    yours = _size_pick(shaped, bp)
    all_sizes = [s.get("name") if isinstance(s, dict) else str(s) for s in raw.get("sizes") or []]
    ideal = _size_pick({**shaped, "sizes": [s for s in all_sizes if s]}, bp)
    return {"your_size": yours, "in_your_size": None if ideal is None else yours == ideal}


def body_summary(bp: dict) -> str:
    """One line for the prompt and the rules' reasons: "slim build, 30.5 in waist, 178 cm"."""
    parts = []
    if bp.get("build"):
        parts.append(f"{bp['build']} build")
    for key, label in (("chest_in", "chest"), ("waist_in", "waist"), ("hip_in", "hips"), ("inseam_in", "inseam")):
        if bp.get(key):
            parts.append(f"{bp[key]:g} in {label}")
    if bp.get("height_cm"):
        parts.append(f"{bp['height_cm']:g} cm")
    return ", ".join(parts)


# ---------- candidate pool ----------

def _buyable(p: dict) -> bool:
    sizes = p.get("sizes") or []
    sizes = [s if isinstance(s, dict) else {"name": str(s), "in_stock": True} for s in sizes]
    return bool(p.get("in_stock", True)) and (not sizes or any(s.get("in_stock", s.get("inStock", True)) for s in sizes))


_NOT_FOR_MEN = re.compile(r"earring|hoop|bralette|bikini|dress|skirt|heels|handbag|purse", re.I)
_NOT_FOR_WOMEN = re.compile(r"boxer|necktie|cufflink", re.I)


def _dept_ok(p: dict, shop_for) -> bool:
    """Same shop_for rule as the feed, for every slot: "men" gets men + unisex, "women" gets women + unisex,
    "both"/None gets everything. Unknown department passes only for non-accessories (null-department
    accessories like "Hoop Earrings" were leaking into men's fits), and accessory names that are clearly
    for the other department are dropped too."""
    if shop_for not in ("men", "women"):
        return True
    dept = p.get("department")
    accessory = p.get("category") == "accessory"
    if dept is None:
        if accessory:
            return False
    elif dept not in (shop_for, "unisex"):
        return False
    if accessory:
        rx = _NOT_FOR_MEN if shop_for == "men" else _NOT_FOR_WOMEN
        if rx.search(str(p.get("name") or "")):
            return False
    return True


def _price(p: dict) -> float:
    return float(p.get("sale_price_usd") or p.get("price_usd") or 0)


def _in_ranges(p: dict, ranges: dict) -> bool:
    r = (ranges or {}).get(p.get("category"))
    return not r or r[0] <= _price(p) <= r[1]


def candidate_pool(user: dict, must_include: list[str], budget_usd: float | None) -> list[dict]:
    """Catalog cards (contract shape + your_size / in_your_size) the fits may use. Must-include products
    are always in, even outside the filters. In-budget first, then in-your-size, then price."""
    bp = user.get("body_profile") or {}
    ranges = user.get("price_ranges") or {}
    sized = _has_measurements(bp)
    out: dict[str, dict] = {}
    for raw in store.list("products"):
        p = as_product(raw)
        if not p or p.get("category") not in SLOTS:
            continue
        card = {**p, **_size_fields(raw, bp)}
        if p["id"] in must_include:
            out[p["id"]] = card
            continue
        if not _buyable(raw) or not _dept_ok(raw, user.get("shop_for")):
            continue
        if budget_usd is not None and _price(p) > budget_usd:
            continue
        if sized and card["your_size"] is None:
            continue
        out[p["id"]] = card
    cards = list(out.values())
    cards.sort(key=lambda c: (c["id"] not in must_include, not _in_ranges(c, ranges),
                              c["in_your_size"] is not True, _price(c)))
    return cards


# ---------- pieces ----------

def _closet_label(c: dict) -> str:
    return c.get("label") or f"{c.get('color', '')} {c.get('category', '')}".strip()


def _piece(item: dict, source: str) -> dict:
    slot = item.get("category") if item.get("category") in SLOTS else "accessory"
    if source == "closet":
        return {"slot": slot, "source": "closet", "closet_item": item, "product": None,
                "your_size": None, "in_your_size": None}
    return {"slot": slot, "source": "catalog", "closet_item": None, "product": item,
            "your_size": item.get("your_size"), "in_your_size": item.get("in_your_size")}


def _pid(piece: dict) -> str:
    return (piece["closet_item"] or piece["product"])["id"]


def _complete(pieces: list[dict]) -> bool:
    """Wearable: top + bottom, or a dress. Shoes are wanted but a closet without shoes still gets fits."""
    slots = {p["slot"] for p in pieces}
    return "dress" in slots or {"top", "bottom"} <= slots


def _missing(pieces: list[dict]) -> list[str]:
    slots = {p["slot"] for p in pieces}
    need = ["shoes"] if "dress" in slots else ["top", "bottom", "shoes"]
    if "dress" not in slots and "top" not in slots and "bottom" not in slots:
        need = ["top", "bottom", "shoes"]
    return [s for s in need if s not in slots]


def _best_for_slot(slot: str, pieces: list[dict], closet: list[dict], catalog: list[dict],
                   style_text: str, remaining: float | None, catalog_only: bool = False) -> dict | None:
    """Rules fill for one empty slot: best closet piece (score >= 0.5), else best catalog piece in budget
    (in-your-size first). `catalog_only` skips the closet."""
    used = {_pid(p) for p in pieces}
    ctx = [_as_closet_shape(p["closet_item"] or p["product"], p["source"]) for p in pieces]

    def best(items, source, floor):
        ranked = []
        for it in items:
            if it.get("category") != slot or it["id"] in used:
                continue
            if source == "catalog" and remaining is not None and _price(it) > remaining:
                continue
            prod = {"id": it["id"], "name": _closet_label(it) if source == "closet" else it.get("name"),
                    "category": slot, "colors": it.get("colors") or [it.get("color")], "price_usd": _price(it),
                    "style_tags": it.get("style_tags") or [], "pattern": it.get("pattern"),
                    "formality": it.get("formality")}
            sc = score_product(prod, ctx, style_text=style_text)["score"] if ctx else 0.5
            ranked.append((sc, it.get("in_your_size") is True, -_price(it), it))
        ranked.sort(key=lambda r: r[:3], reverse=True)
        return ranked[0][3] if ranked and ranked[0][0] >= floor else None

    if not catalog_only:
        hit = best(closet, "closet", 0.5)
        if hit:
            return _piece(hit, "closet")
    hit = best(catalog, "catalog", 0.0)
    return _piece(hit, "catalog") if hit else None


def _ensure_new(pieces: list[dict], catalog: list[dict], style_text: str, budget_usd: float | None) -> list[dict] | None:
    """Fits are closet-only now: nothing is swapped in from the catalog (kept as a hook; always a no-op)."""
    return pieces


def _fill(pieces: list[dict], closet: list[dict], catalog: list[dict], style_text: str,
          budget_usd: float | None) -> list[dict]:
    """Add whatever required slots are empty (top+bottom or dress, shoes)."""
    pieces = list(pieces)
    for _ in range(4):
        missing = _missing(pieces)
        if not missing:
            break
        spent = sum(_price(p["product"]) for p in pieces if p["source"] == "catalog")
        remaining = None if budget_usd is None else budget_usd - spent
        added = _best_for_slot(missing[0], pieces, closet, catalog, style_text, remaining)
        if added is None:
            if missing[0] in ("top", "bottom") and not any(p["slot"] == "dress" for p in pieces):
                added = _best_for_slot("dress", pieces, closet, catalog, style_text, remaining)
                if added:
                    pieces = [p for p in pieces if p["slot"] not in ("top", "bottom")]
            if added is None:
                break
        pieces.append(added)
    return pieces


def _finish(fit_id: str, name: str, reason: str, occasion: str | None, pieces: list[dict]) -> dict:
    order = {s: i for i, s in enumerate(("outerwear", "top", "dress", "bottom", "shoes", "accessory"))}
    pieces = sorted(pieces, key=lambda p: order.get(p["slot"], 9))
    return {"id": fit_id, "name": name, "occasion": occasion, "reason": reason, "pieces": pieces,
            "new_total_usd": round(sum(_price(p["product"]) for p in pieces if p["source"] == "catalog"), 2),
            "closet_count": sum(1 for p in pieces if p["source"] == "closet"), "try_on": None,
            "missing": _missing(pieces)}


def _rules_reason(body: str, anchor: dict | None, occasion: str | None) -> str:
    who = f"{body}: " if body else ""
    around = f"built around your {_closet_label(anchor)}" if anchor else "all from your closet"
    tail = f" for {occasion}" if occasion else ""
    s = f"{who}{around}{tail}."
    return s[0].upper() + s[1:]


def _with_must(pieces: list[dict], must: list[dict]) -> list[dict]:
    """Every must-include product is in the fit: it replaces the piece in its slot."""
    have = {_pid(p) for p in pieces}
    for prod in must:
        if prod["id"] in have:
            continue
        piece = _piece(prod, "catalog")
        pieces = [p for p in pieces if p["slot"] != piece["slot"]]
        if piece["slot"] == "dress":
            pieces = [p for p in pieces if p["slot"] not in ("top", "bottom")]
        elif piece["slot"] in ("top", "bottom"):
            pieces = [p for p in pieces if p["slot"] != "dress"]
        pieces.append(piece)
    return pieces


def _fit_id(key: str, pieces: list[dict]) -> str:
    return "fit_" + hashlib.sha256((key + "|" + ",".join(sorted(_pid(p) for p in pieces))).encode()).hexdigest()[:12]


# ---------- rules ----------

def rules_fits(key: str, user: dict, closet: list[dict], catalog: list[dict], count: int, occasion: str | None,
               must: list[dict], budget_usd: float | None) -> list[dict]:
    """One fit around each top closet piece (complete_look + outfit rules), or around catalog pieces when the
    closet is empty. Name = "<color> <category> fit"."""
    body = body_summary(user.get("body_profile") or {})
    style_text = user.get("style_text", "") or ""
    anchors = sorted(closet, key=lambda c: ANCHOR_ORDER.get(c.get("category"), 9))
    fits, seen = [], set()
    for anchor in anchors:
        if len(fits) >= count:
            break
        pieces = _with_must([_piece(anchor, "closet")], must)
        rest = [c for c in closet if c["id"] != anchor["id"]]
        look = complete_look({**anchor, "colors": [anchor.get("color")], "price_usd": 0.0}, rest, catalog,
                             budget_usd=budget_usd, style_text=style_text)
        by_id = {**{c["id"]: c for c in closet}, **{p["id"]: p for p in catalog}}
        for it in look["items"]:
            item = by_id.get(it["id"])
            if item and it["category"] not in {p["slot"] for p in pieces}:
                pieces.append(_piece(item, it["source"]))
        pieces = _ensure_new(_fill(pieces, rest, catalog, style_text, budget_usd), catalog, style_text, budget_usd)
        if pieces is None:
            continue
        sig = frozenset(_pid(p) for p in pieces)
        if not _complete(pieces) or sig in seen:
            continue
        seen.add(sig)
        name = f"{anchor.get('color', '')} {anchor.get('category', '')} fit".strip()
        fits.append(_finish(_fit_id(key, pieces), name, _rules_reason(body, anchor, occasion), occasion, pieces))
    # not enough closet anchors: build all-new fits around catalog tops / dresses
    for anchor in [p for p in catalog if p["category"] in ("top", "dress")]:
        if len(fits) >= count:
            break
        pieces = _fill(_with_must([_piece(anchor, "catalog")], must), closet, catalog, style_text, budget_usd)
        sig = frozenset(_pid(p) for p in pieces)
        if not _complete(pieces) or sig in seen:
            continue
        seen.add(sig)
        name = f"{(anchor.get('colors') or ['new'])[0]} {anchor['category']} fit"
        fits.append(_finish(_fit_id(key, pieces), name, _rules_reason(body, None, occasion), occasion, pieces))
    return fits


# ---------- AI ----------

def ai_fits(key: str, user: dict, closet: list[dict], catalog: list[dict], count: int, occasion: str | None,
            must: list[dict], budget_usd: float | None) -> list[dict]:
    """Claude picks the outfits from the pool; ids are validated, incomplete fits are filled by the rules."""
    bp = user.get("body_profile") or {}
    style_text = user.get("style_text", "") or ""
    slim_closet = [{"id": c["id"], "label": _closet_label(c), "category": c.get("category"), "color": c.get("color")}
                   for c in closet]
    slim_cands = [{"id": p["id"], "name": p.get("name"), "category": p["category"], "color": (p.get("colors") or [""])[0],
                   "price_usd": _price(p), "style_tags": p.get("style_tags") or [], "your_size": p.get("your_size")}
                  for p in catalog[:MAX_CANDIDATES]]
    prompt = prompts.FIT_CREATOR.format(
        body=body_summary(bp) or "not scanned yet", fit=bp.get("fit") or "regular",
        style_text=style_text or "not given", occasion=occasion or "everyday",
        budget="no limit" if budget_usd is None else f"{budget_usd:g}",
        must_include=json.dumps([m["id"] for m in must]) if must else "none",
        closet_json=json.dumps(slim_closet), products_json=json.dumps(slim_cands), count=count)
    raw = ai_json(prompt, max_tokens=1500, model=CLAUDE_PAIR_MODEL)
    by_id = {**{c["id"]: ("closet", c) for c in closet}, **{p["id"]: ("catalog", p) for p in catalog}}
    fits, seen = [], set()
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        pieces, slots = [], set()
        for pc in r.get("pieces") or []:
            hit = by_id.get(str((pc or {}).get("id", "")) if isinstance(pc, dict) else str(pc))
            if not hit or hit[1].get("category") in slots:
                continue  # hallucinated id or a second piece for the same slot
            slots.add(hit[1].get("category"))
            pieces.append(_piece(hit[1], hit[0]))
        pieces = _fill(_with_must(pieces, must), closet, catalog, style_text, budget_usd)
        pieces = _ensure_new(pieces, catalog, style_text, budget_usd)  # closet-only fits get one new piece
        if pieces is None:
            continue
        sig = frozenset(_pid(p) for p in pieces)
        if not _complete(pieces) or sig in seen:
            continue
        seen.add(sig)
        name = " ".join(str(r.get("name") or "").split()[:4]) or "new fit"
        anchor = next((p["closet_item"] for p in pieces if p["source"] == "closet"), None)
        reason = " ".join(str(r.get("reason") or "").split()) or _rules_reason(body_summary(bp), anchor, occasion)
        fits.append(_finish(_fit_id(key, pieces), name, reason, occasion, pieces))
        if len(fits) >= count:
            break
    return fits


# ---------- entry points ----------

def _cache_key(user_id: str, closet: list[dict], count: int, occasion: str | None, must_include: list[str],
               budget_usd: float | None) -> str:
    state = (f"fits|{prompts.FIT_CREATOR_VERSION}|{prompts.PAIR_VERSION}|{user_id}|"
             f"{','.join(sorted(c['id'] for c in closet))}|{count}|{(occasion or '').strip().lower()}|"
             f"{','.join(sorted(must_include))}|{budget_usd}")
    return "fits_" + hashlib.sha256(state.encode()).hexdigest()[:20]


def _remember(key: str, user_id: str, fits: list[dict], source: str) -> None:
    now = time.time()
    store.put("fit_cache", key, {"at": now, "user_id": user_id, "fits": fits, "source": source})
    for f in fits:
        store.put("fits", f["id"], {"at": now, "user_id": user_id, "fit": f})


def create_fits(user_id: str, count: int = 3, occasion: str | None = None, must_include: list[str] | None = None,
                budget_usd: float | None = None, tryon: bool = False) -> dict:
    """{"fits": [...], "source": "ai"|"rules"}, built only from the closet. `must_include`, `budget_usd` and
    `tryon` are accepted for old clients and ignored. Raises NoFits when the closet can't make one outfit."""
    user = store.get("users", user_id) or {}
    closet = [c for c in store.list("closet_items", user_id=user_id) if c.get("category") in SLOTS]
    must_include = [m for m in (must_include or []) if m]
    key = _cache_key(user_id, closet, count, occasion, must_include, budget_usd)
    hit = store.get("fit_cache", key)
    if hit and time.time() - hit.get("at", 0) < FIT_TTL:
        fits, source = hit["fits"], hit["source"]
    else:
        catalog: list[dict] = []  # closet only: no shop pieces, ever
        must: list[dict] = []
        fits, source = [], "rules"
        if not text_mock():
            try:
                fits = ai_fits(key, user, closet, catalog, count, occasion, must, budget_usd)
                source = "ai" if fits else "rules"
            except BadModelOutput as e:
                log.warning("fit creator AI failed, using rules: %s", e)
        if len(fits) < count:
            have = {frozenset(_pid(p) for p in f["pieces"]) for f in fits}
            for f in rules_fits(key, user, closet, catalog, count, occasion, must, budget_usd):
                if len(fits) >= count:
                    break
                if frozenset(_pid(p) for p in f["pieces"]) not in have:
                    fits.append(f)
        if not fits:
            raise NoFits("no complete outfit possible from the closet (needs a top + bottom, or a dress)")
        _remember(key, user_id, fits, source)
    # `tryon` is accepted for old clients but ignored: fits are closet outfits, not try-on renders.
    return {"fits": fits, "source": source}


def get_fit(fit_id: str, user_id: str) -> dict | None:
    row = store.get("fits", fit_id)
    if not row or row.get("user_id") != user_id or time.time() - row.get("at", 0) >= FIT_TTL:
        return None
    return row["fit"]


def _try_on(user_id: str, fit: dict) -> dict | None:
    from .service import try_on

    product_ids = [p["product"]["id"] for p in fit["pieces"] if p["source"] == "catalog"]
    closet_ids = [p["closet_item"]["id"] for p in fit["pieces"] if p["source"] == "closet"]
    try:
        r = try_on(user_id, product_ids, closet_ids)
    except (BadModelOutput, ValueError) as e:
        log.warning("fit try-on failed: %s", e)
        return None
    return {"image_url": r.image_url, "mode": r.mode, "source_photo_url": r.source_photo_url}


def fit_try_on(fit_id: str, user_id: str) -> dict | None:
    """Generate (or return the cached) try-on for one fit; None if the fit is unknown/expired."""
    fit = get_fit(fit_id, user_id)
    if fit is None:
        return None
    if not fit.get("try_on"):
        fit = {**fit, "try_on": _try_on(user_id, fit)}
        row = store.get("fits", fit_id)
        store.put("fits", fit_id, {**row, "fit": fit})
    return fit["try_on"]


def fit_to_cart(fit_id: str, user_id: str) -> dict | None:
    """Add every catalog piece at your_size (first in-stock size when we have no size for them) and return the
    grouped cart like POST /cart/{user}/items. None if the fit is unknown/expired."""
    from ..commerce.router import _add_to_cart, _grouped

    fit = get_fit(fit_id, user_id)
    if fit is None:
        return None
    for p in fit["pieces"]:
        if p["source"] != "catalog":
            continue
        sizes = p["product"].get("sizes") or []
        size = p.get("your_size") or (sizes[0] if sizes else None)
        if size is None or (sizes and size not in sizes):
            continue
        _add_to_cart(user_id, p["product"]["id"], size, 1)
    return _grouped(user_id)
