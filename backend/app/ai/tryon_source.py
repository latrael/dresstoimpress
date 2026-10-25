"""Which photo of the user to edit for a try-on (v5 in-place edits).

A try-on edits only the region of the garment being replaced, so it needs a photo of the user that
actually shows a garment of that category. The lone body photo rarely does (and it is what made the
results look poor), so the candidates are: the body photo + every closet outfit photo (`outfits`
collection) + every photo a closet piece was seen worn in (`worn_in`). Each is scored and the best
becomes image 1; the matched pieces' boxes tell the prompt where to edit.
"""
from __future__ import annotations

from typing import Any

from ..store import store

# a product of this category can replace a garment of these categories in the photo
REPLACES = {
    "top": {"top", "dress"},
    "outerwear": {"outerwear", "top"},
    "bottom": {"bottom", "dress"},
    "dress": {"dress", "top", "bottom"},
    "shoes": {"shoes"},
    "accessory": {"accessory"},
}
UPPER = {"top", "outerwear", "dress"}
LOWER = {"bottom", "dress"}

# Season / layer compatibility: shorts never go into a trench-coat photo. 0 = light (summer), 1 = mid, 2 = heavy.
_LIGHT = ("shorts", "short-sleeve", "short sleeve", "tank", "tee", "t-shirt", "tshirt", "linen", "sandal", "flip-flop",
          "slide", "swim", "crop", "sleeveless", "camisole", "polo", "skirt", "mini")
_HEAVY = ("coat", "trench", "overcoat", "puffer", "parka", "wool", "boot", "sweater", "hoodie", "fleece", "knit",
          "cardigan", "turtleneck", "scarf", "beanie", "thermal", "shearling", "down")
HEAVY_PENALTY = 6.0  # heavy-vs-light: effectively disqualified unless it's the only photo
MID_PENALTY = 1.5


def warmth(text: str | None, category: str | None = None) -> int:
    """0 light / 1 mid / 2 heavy, from the label or product name (+ tags) and the category."""
    t = (text or "").lower()
    if any(w in t for w in _HEAVY):
        return 2
    if any(w in t for w in _LIGHT):
        return 0
    return 2 if category == "outerwear" else 1


def _product_warmth(prod: dict) -> int:
    text = " ".join([str(prod.get("name") or prod.get("label") or ""), *map(str, prod.get("style_tags") or [])])
    return warmth(text, prod.get("category"))


def _piece_warmth(piece: dict) -> int:
    return warmth(piece.get("label"), piece.get("category"))


def _box(v: Any) -> list[float] | None:
    if not isinstance(v, (list, tuple)) or len(v) != 4:
        return None
    try:
        b = [float(x) for x in v]
    except (TypeError, ValueError):
        return None
    return b if b[0] < b[2] and b[1] < b[3] and all(0 <= x <= 1 for x in b) else None


def _area(b: list[float] | None) -> float:
    return (b[2] - b[0]) * (b[3] - b[1]) if b else 0.0


def _cut_off(b: list[float] | None) -> bool:
    """A garment box flush against the frame edge: the garment is probably cropped."""
    return bool(b) and (b[0] <= 0.01 or b[2] >= 0.99 or b[3] >= 0.99)


def candidate_photos(user_id: str, user: dict | None = None) -> list[dict]:
    """[{url, kind: "body"|"outfit", pieces: [{category, color, style_tags, box}]}], one per distinct photo."""
    user = user if user is not None else (store.get("users", user_id) or {})
    by_url: dict[str, dict] = {}

    def photo(url: str, kind: str) -> dict:
        return by_url.setdefault(url, {"url": url, "kind": kind, "pieces": []})

    body = user.get("body_photo_url")
    if body:
        photo(body, "body")
    items = {i["id"]: i for i in store.list("closet_items", user_id=user_id)}
    for o in store.list("outfits", user_id=user_id):
        if o.get("photo_url"):
            photo(o["photo_url"], "outfit")
    for item in items.values():
        for w in item.get("worn_in") or []:
            if not isinstance(w, dict) or not w.get("photo_url"):
                continue
            ph = photo(w["photo_url"], "outfit")
            if ph["kind"] == "body":
                ph["kind"] = "outfit"  # the body photo doubles as an outfit photo: we know its pieces
            ph["pieces"].append({"category": item.get("category"), "color": item.get("color"),
                                 "label": item.get("label"), "style_tags": item.get("style_tags") or [],
                                 "box": _box(w.get("box")), "item_id": item["id"]})
    return list(by_url.values())


def _full_body(ph: dict, body_profile: dict) -> float:
    """0..3: how much of the person the photo shows (from the pieces' categories / boxes, or the scan)."""
    cats = {p["category"] for p in ph["pieces"]}
    boxes = [p["box"] for p in ph["pieces"] if p["box"]]
    if boxes:
        top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
        if top <= 0.3 and bottom >= 0.85:
            return 3.0
    if cats & UPPER and cats & LOWER and "shoes" in cats:
        return 3.0
    if cats & UPPER and cats & LOWER:
        return 2.0
    if ph["kind"] == "body":
        return 0.0 if body_profile.get("full_body") is False else 2.5
    return 1.0 if cats else 0.5


def _compat(ph: dict, product: dict, replaced: set[str]) -> float:
    """0..1: do the photo's other pieces go with the product (colour harmony, shared style tags)?"""
    others = [p for p in ph["pieces"] if p.get("item_id") not in replaced]
    if not others:
        return 0.5
    from .outfit_rules import _color_harmony_score

    prod_colors = [str(c) for c in product.get("colors") or []]
    prod_tags = set(product.get("style_tags") or [])
    total = 0.0
    for p in others:
        total += _color_harmony_score(prod_colors, str(p.get("color") or "")) * 4  # 0..1
        if prod_tags and prod_tags & set(p.get("style_tags") or []):
            total += 0.3
    return min(1.0, total / len(others))


def score_photo(ph: dict, products: list[dict], body_profile: dict | None = None) -> tuple[float, list]:
    """(score, boxes): boxes[i] is the box of the garment product i would replace in this photo (or None)."""
    body_profile = body_profile or {}
    score = _full_body(ph, body_profile)
    boxes: list = []
    replaced: set[str] = set()
    matched = 0
    for prod in products:
        cat = prod.get("category") or ""
        cands = [p for p in ph["pieces"] if p.get("category") in REPLACES.get(cat, {cat})
                 and p.get("item_id") not in replaced]
        cands.sort(key=lambda p: (p.get("category") != cat, -_area(p["box"])))  # same category, biggest first
        if cands:
            matched += 1
            replaced.add(cands[0].get("item_id"))
            boxes.append(cands[0]["box"])
            score += 3.0 + 2.0 * _area(cands[0]["box"]) - (1.0 if _cut_off(cands[0]["box"]) else 0.0)
        else:
            boxes.append(None)
            score -= 0.0 if ph["kind"] == "body" and not ph["pieces"] else 2.0  # a known fit with no such garment
    if products and matched == 0 and ph["pieces"]:
        score -= 3.0  # nothing to replace: the model would have to invent a region
    if ph["pieces"]:
        score += sum(_compat(ph, prod, replaced) for prod in products) / max(1, len(products))
        score -= _season_penalty(ph, products, replaced)
    return round(score, 3), boxes


def _season_penalty(ph: dict, products: list[dict], replaced: set[str]) -> float:
    """What stays in the photo must suit the product's season: shorts into a trench-coat photo (or a parka
    onto a tank-top photo) is a heavy penalty; one step apart is a mild one. A top going under outerwear
    that stays on is penalised too: prefer a photo where the top is the outer layer."""
    kept = [p for p in ph["pieces"] if p.get("item_id") not in replaced]
    if not kept:
        return 0.0
    photo_w = max(_piece_warmth(p) for p in kept)
    photo_light = min(_piece_warmth(p) for p in kept)
    penalty = 0.0
    for prod in products:
        pw = _product_warmth(prod)
        gap = max(abs(pw - photo_w), abs(pw - photo_light))
        if gap >= 2:
            penalty += HEAVY_PENALTY
        elif gap == 1:
            penalty += MID_PENALTY
        if prod.get("category") == "top" and any(p.get("category") == "outerwear" for p in kept):
            penalty += 2.0
    return penalty


def pick_source_photo(user_id: str, products: list[dict], user: dict | None = None) -> dict | None:
    """The best photo to edit: {url, kind, score, boxes} or None when the user has no photo at all.
    Ties go to the body photo, then to the newest outfit (candidate order)."""
    user = user if user is not None else (store.get("users", user_id) or {})
    cands = candidate_photos(user_id, user)
    if not cands:
        return None
    bp = user.get("body_profile") or {}
    best = None
    for ph in cands:
        s, boxes = score_photo(ph, products, bp)
        if best is None or s > best["score"]:
            best = {"url": ph["url"], "kind": ph["kind"], "score": s, "boxes": boxes}
    return best
