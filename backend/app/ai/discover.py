"""Discover / Home ranking helpers (council D3, D9, D10, D11). Rules only: no AI calls here.

- size_rank(): adds `your_size` + `in_your_size` to feed cards and puts in-your-size cards first,
  preferred stores first within each group (stable, so the AI order is kept otherwise).
- seeded(): GET /feed?seed=: the tapped product first, then look-alikes.
- search(): GET /search?q=: vibe filters + keyword match -> "similar" cards, plus "goes with" cards.
- styles() / trending(): GET /search/styles chips.

A "card" is a product dict plus reason / score / pairs_with, the same shape GET /feed returns.
"""
from __future__ import annotations

import re
from collections import Counter

from ..store import store
from .compat import as_product, get_product, list_products
from .finder import item_type
from .sizing import recommend_size

_WORD = re.compile(r"[a-z0-9-]+")
_CLAMPED = ("clamped", "closest available")  # recommend_size reasons meaning "not really your size"


def _words(s) -> set[str]:
    return set(_WORD.findall(str(s or "").lower()))


def _price(p: dict) -> float:
    return float(p.get("sale_price_usd") or p.get("price_usd") or 0)


# ---------- D3: soft size ranking ----------

def _measurements(user: dict | None) -> dict:
    """Body numbers wherever the profile stores them: body_profile (scan / typed) or the flat
    measurements / fit / usual_sizes fields; body_profile wins."""
    user = user or {}
    out = dict(user.get("measurements") or {})
    for k in ("fit", "usual_sizes", "shoe_us"):
        if user.get(k) is not None:
            out.setdefault(k, user[k])
    out.update({k: v for k, v in (user.get("body_profile") or {}).items() if v is not None})
    return out


def your_size(user: dict | None, product: dict) -> tuple[str | None, bool]:
    """(size we'd pick, is it genuinely their size). Same logic as POST /size: body numbers through
    recommend_size, then the usual size for the category. (None, False) without a profile."""
    from .router import _usual_size

    m = _measurements(user)
    if not m:
        return None, False
    p = as_product(product) or product
    usual = (m.get("usual_sizes") or {}).get(p.get("category"))
    out = None
    if m.get("height_cm") and m.get("weight_kg"):
        out = recommend_size(p, m["height_cm"], m["weight_kg"], fit=m.get("fit") or "regular",
                             shoe_us=m.get("shoe_us"), waist_in=m.get("waist_in"))
    if not (out and out.get("size")) and usual:
        out = _usual_size(p, usual) or out
    if not out or not out.get("size"):
        return None, False
    reason = str(out.get("reason") or "")
    return str(out["size"]), not any(w in reason for w in _CLAMPED)


def size_rank(user: dict | None, cards: list[dict]) -> list[dict]:
    """In-your-size cards first, then the rest; preferred stores first within each group. Stable."""
    preferred = set(map(str, (user or {}).get("preferred_stores") or []))
    out = []
    for c in cards:
        size, ok = your_size(user, c)
        out.append({**c, "your_size": size, "in_your_size": ok})
    return sorted(out, key=lambda c: (not c["in_your_size"], c.get("retailer") not in preferred))


def _card(p: dict, reason: str, score: float, **extra) -> dict:
    return {**p, "reason": reason, "score": round(max(0.0, min(1.0, score)), 3), "pairs_with": [], **extra}


# ---------- D9: seeded feed ----------

def similarity(seed: dict, p: dict) -> tuple[float, str]:
    """Rule score + the strongest reason. Same category dominates; then shared colour words,
    shared style tags, same item type (jeans vs jeans), same retailer, price within 40%."""
    s = 0.0
    why = []
    if p.get("category") == seed.get("category"):
        s += 3.0
    colors = _words(" ".join(seed.get("colors") or [])) & _words(" ".join(p.get("colors") or []))
    if colors:
        s += 1.0 * len(colors)
        why.append(f"also {sorted(colors)[0]}")
    tags = set(seed.get("style_tags") or []) & set(p.get("style_tags") or [])
    if tags:
        s += 1.0 * len(tags)
        why.append(f"same {sorted(tags)[0]} style")
    st = item_type(seed.get("name") or seed.get("label") or "")
    if st is not None and st == item_type(p.get("name") or p.get("label") or ""):
        s += 2.0
        why.insert(0, "same kind of piece")
    if p.get("retailer") and p.get("retailer") == seed.get("retailer"):
        s += 0.5
        why.append(f"also from {p.get('brand') or p['retailer']}")
    sp, pp = _price(seed), _price(p)
    if sp and pp and abs(pp - sp) <= 0.4 * sp:
        s += 1.0
        why.append("similar price")
    reason = "Similar to the piece you tapped" if not why else ("Like it: " + ", ".join(why[:2]))
    return s, reason


def seeded(seed: dict, cands: list[dict], user: dict | None, limit: int) -> list[dict]:
    """The seed first ("The piece you tapped"), then candidates by similarity (same category first),
    then size ranking over the look-alikes. Candidates are the feed's usual buyable set."""
    scored = []
    for p in cands:
        if p["id"] == seed["id"]:
            continue
        s, why = similarity(seed, p)
        scored.append((s, p, why))
    scored.sort(key=lambda t: (t[1].get("category") != seed.get("category"), -t[0], t[1]["id"]))
    top = max((t[0] for t in scored), default=1.0) or 1.0
    rest = [_card(p, why, s / top) for s, p, why in scored]
    head = size_rank(user, [_card(seed, "The piece you tapped", 1.0)])
    return (head + size_rank(user, rest))[:limit]


# ---------- D10: text search ----------

def _hits(p: dict, words: list[str]) -> int:
    hay = " ".join([p.get("name") or "", p.get("label") or "", p.get("brand") or "",
                    *(p.get("style_tags") or []), *(p.get("colors") or [])]).lower()
    return sum(1 for w in words if w and w in hay)


def search_products(q: str, filters: dict, catalog: list[dict]) -> list[dict]:
    """Cards matching the query words or the vibe filters (styles / categories / colors), best first."""
    words = [w for w in _WORD.findall(q.lower()) if len(w) > 1]
    styles, cats, colors = set(filters.get("styles") or []), set(filters.get("categories") or []), \
        set(filters.get("colors") or [])
    kw_words = [w for k in filters.get("keywords") or [] for w in _WORD.findall(str(k).lower())]
    out = []
    for p in catalog:
        why = []
        s = 2.0 * _hits(p, words)
        if s:
            why.append(f'matches "{q.strip()[:30]}"')
        k = _hits(p, [w for w in kw_words if w not in words])
        s += 1.0 * k
        tags = styles & set(p.get("style_tags") or [])
        if tags:
            s += 1.5 * len(tags)
            why.append(f"{sorted(tags)[0]} style")
        if cats and p.get("category") in cats:
            s += 1.0
        elif cats and p.get("category") not in cats:
            s -= 1.0  # the query named a kind of piece and this isn't it
        pc = _words(" ".join(p.get("colors") or []))
        if colors & pc:
            s += 1.0
            why.append(f"in {sorted(colors & pc)[0]}")
        if s <= 0:
            continue
        out.append((s, _card(p, "Similar: " + ", ".join(why[:2]) if why else "Fits the vibe", s)))
    out.sort(key=lambda t: (-t[0], t[1].get("name", "").lower(), t[1]["id"]))
    top = out[0][0] if out else 1.0
    return [{**c, "score": round(s / top, 3)} for s, c in out]


_COMPLEMENT = {"top": ["bottom", "shoes", "outerwear"], "bottom": ["top", "shoes", "outerwear"],
               "outerwear": ["top", "bottom", "shoes"], "shoes": ["bottom", "top", "outerwear"],
               "dress": ["shoes", "outerwear", "accessory"], "accessory": ["top", "bottom", "shoes"]}
_NEUTRAL = {"black", "white", "grey", "gray", "beige", "cream", "navy", "denim", "ecru", "khaki", "brown"}


def goes_with(user_id: str, anchor: dict | None, catalog: list[dict], n: int = 8) -> list[dict]:
    """Pieces from other categories that complete `anchor`: complete_look() picks (closet-aware) first,
    then a category-complement + colour-harmony top-up (neutrals go with everything, shared style tags)."""
    if not anchor:
        return []
    from .complete_look import complete_look

    user = store.get("users", user_id) or {}
    closet = store.list("closet_items", user_id=user_id)
    others = [p for p in catalog if p["id"] != anchor["id"] and p.get("category") != anchor.get("category")]
    by_id = {p["id"]: p for p in others}
    cards, seen = [], set()
    try:
        look = complete_look(anchor, closet, others, style_text=user.get("style_text", ""))
    except Exception:  # noqa: BLE001 - rules helper; a bad product never breaks search
        look = {"items": []}
    for it in look.get("items") or []:
        p = by_id.get(str(it.get("id")))
        if it.get("source") == "catalog" and p and p["id"] not in seen:
            seen.add(p["id"])
            cards.append(_card(p, str(it.get("reason") or "completes your look").capitalize(), 1.0))
    want = _COMPLEMENT.get(anchor.get("category") or "", ["top", "bottom", "shoes"])
    a_colors = _words(" ".join(anchor.get("colors") or []))
    a_tags = set(anchor.get("style_tags") or [])
    scored = []
    for p in others:
        if p["id"] in seen or p.get("category") not in want:
            continue
        pc = _words(" ".join(p.get("colors") or []))
        s = 1.0 + (len(want) - want.index(p["category"])) * 0.5
        s += 1.0 if pc & _NEUTRAL or a_colors & _NEUTRAL else 0.0
        s += 0.5 * len(pc & a_colors) + 1.0 * len(a_tags & set(p.get("style_tags") or []))
        scored.append((s, p))
    scored.sort(key=lambda t: (-t[0], t[1]["id"]))
    # one of each wanted category first so the section reads as an outfit, not five pairs of shoes
    per_cat: dict[str, list] = {}
    for s, p in scored:
        per_cat.setdefault(p["category"], []).append((s, p))
    for c in want:
        for s, p in per_cat.get(c, [])[:max(1, n // len(want))]:
            cards.append(_card(p, f"Goes with the {anchor.get('name') or anchor.get('category')}"[:60],
                               min(1.0, s / 5.0)))
    return size_rank(user, cards[:n])


# ---------- D11: chips + trending ----------

def styles(catalog: list[dict]) -> list[dict]:
    counts = Counter(t for p in catalog for t in (p.get("style_tags") or []))
    return [{"tag": t, "count": c} for t, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def trending(catalog: list[dict], n: int = 10) -> list[dict]:
    """Most wishlisted / carted products across all users; the top of the catalog when there's no traffic."""
    counts: Counter = Counter()
    for w in store.list("wishlist"):
        counts[w.get("product_id")] += 1
    for s in store.list("swipes"):
        if s.get("action") == "cart":
            counts[s.get("product_id")] += 1
    by_id = {p["id"]: p for p in catalog}
    out = []
    for pid, c in counts.most_common():
        p = by_id.get(pid)
        if p:
            out.append(_card(p, f"Trending: saved by {c} shopper{'s' if c != 1 else ''}", 1.0, trend_count=c))
        if len(out) >= n:
            break
    if not out:
        out = [_card(p, "Popular right now", 0.5, trend_count=0) for p in catalog[:n]]
    return out


def buyable_catalog() -> list[dict]:
    return [p for p in list_products() if p.get("in_stock", True)]


__all__ = ["your_size", "size_rank", "seeded", "similarity", "search_products", "goes_with", "styles", "trending",
           "buyable_catalog", "get_product"]
