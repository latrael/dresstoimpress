"""Fit Score v2: a 0-100 badge for an outfit, said in terms of a style ("68 as streetwear: strong silhouette,
palette too busy").

v1 (Gemini draft) was additive: clean neutrals + solids + one dress code = 96, so everything scored 80+.
v2 is a calibrated rubric:
  * eight criteria, each 0-10 with explicit anchors (5 = fine, nothing special; 8+ needs a reason),
  * a weighted sum -> raw 0-100, then a calibration curve fitted on 300 random catalog outfits
    (scripts/score_calibration.py): random plausible outfit ~50, solid everyday ~70, strong 80-89,
    90+ only when every criterion is >= 8,
  * per-style execution scores (streetwear, minimalist, ...): the headline is the outfit's score AS its
    best style (or `target_style`), blended 60/40 with the general rubric,
  * optional photo-aware AI critic (prompts.FIT_CRITIC) blended 50/50 with the rules when `photo_url` is
    given and AI is on; rules only otherwise. Free, instant, deterministic without a photo.

Used by POST /ai/fit-score. Items are closet-item / FitTag shaped: category, color, pattern, formality,
style_tags, label; any of them may be missing. Response keeps v1's fields (score, verdict, notes,
breakdown{color/40, pattern/20, formality/20, completeness/20}) and adds criteria, style_scores,
primary_style, raw_score, source.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from .colors import normalize_color

CERTIFIED_THRESHOLD = 90
NO_BASE_SCORE_CAP = 55  # one hoodie on its own isn't an outfit yet, however good its color
STYLE_BLEND = 0.4       # headline = (1 - STYLE_BLEND) * general + STYLE_BLEND * score-as-primary-style
AI_BLEND = 0.5          # rules vs photo critic, per criterion

STYLES = ("streetwear", "minimalist", "classic", "y2k", "preppy", "athleisure", "vintage", "business",
          "boho", "grunge")
VALID_CATEGORIES = frozenset({"top", "bottom", "outerwear", "shoes", "dress", "accessory"})
BUSY_PATTERNS = frozenset({"striped", "plaid", "graphic", "floral"})

# criterion -> weight (occasion only counts when an occasion is given; weights are renormalized)
WEIGHTS = {"color": 20, "silhouette": 12, "pattern": 10, "formality": 14, "style": 14,
           "completeness": 18, "layering": 7, "occasion": 10}
CRITERIA = tuple(WEIGHTS)

# (raw, score) anchors of the calibration curve; monotone piecewise-linear. Fitted with
# scripts/score_calibration.py on seed/products.json (seed 7): random raw p50 68 -> 49, p90 79 -> 76;
# curated raw p50 79 -> 77. Random: 5% >= 80, 0% >= 90.
CALIBRATION = ((0, 0), (45, 25), (60, 40), (68, 50), (75, 66), (80, 78), (85, 86), (90, 92), (100, 100))

# fit words in labels -> silhouette volume
_OVERSIZED = {"oversized", "oversize", "baggy", "boxy", "wide", "wideleg", "relaxed", "loose", "puffer",
              "slouchy", "balloon", "flared", "flare", "parachute", "chunky"}
_SLIM = {"slim", "skinny", "fitted", "tapered", "tight", "bodycon", "ribbed", "tailored", "straight"}
_CROPPED = {"cropped", "crop", "mini", "shrunken"}
_LONG = {"long", "maxi", "longline", "midi"}
_TEXTURES = {"knit", "leather", "denim", "suede", "corduroy", "wool", "linen", "satin", "silk", "fleece",
             "cable", "velvet", "mesh", "nylon", "cotton", "tweed", "sherpa", "shearling"}
_WORD = re.compile(r"[a-z0-9]+")

# unrelated style families: an outfit that spans 3 of them is a costume, not a look
STYLE_FAMILIES = {"streetwear": "street", "y2k": "street", "grunge": "street", "athleisure": "street",
                  "classic": "polished", "business": "polished", "preppy": "polished", "minimalist": "polished",
                  "boho": "free", "vintage": "free"}

# How each style wants to be executed. keywords: label words that read as the style; formality: (lo, hi);
# accents: how many non-neutral colours it tolerates; patterns: welcome / unwelcome; volume: silhouette.
STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "streetwear": {"keywords": {"hoodie", "graphic", "cargo", "sneakers", "sneaker", "oversized", "baggy", "puffer",
                                "jersey", "beanie", "cap", "sweatshirt", "trainers", "dunks", "jordan", "windbreaker",
                                "track", "varsity", "workwear", "carpenter", "wide", "boxy"},
                   "formality": (1, 2), "accents": 2, "good_patterns": {"graphic"}, "bad_patterns": {"floral"},
                   "volume": "oversized"},
    "minimalist": {"keywords": {"plain", "crewneck", "crew", "tailored", "trousers", "turtleneck", "loafers", "tank",
                                "slim", "straight", "clean", "basic", "tee", "tshirt", "shirt", "coat", "wool"},
                   "formality": (2, 4), "accents": 1, "good_patterns": set(),
                   "bad_patterns": {"graphic", "floral", "plaid"}, "volume": "clean"},
    "classic": {"keywords": {"oxford", "button", "chinos", "loafers", "blazer", "trench", "polo", "knit", "cardigan",
                             "leather", "boots", "sweater", "trousers", "shirt", "coat", "denim", "straight"},
                "formality": (2, 4), "accents": 1, "good_patterns": {"striped"}, "bad_patterns": {"graphic"},
                "volume": "clean"},
    "y2k": {"keywords": {"cropped", "crop", "baby", "mini", "low", "rise", "cargo", "platform", "butterfly", "rhinestone",
                         "velour", "halter", "tube", "flare", "flared", "metallic", "mesh", "baguette", "tiny", "micro"},
            "formality": (1, 2), "accents": 3, "good_patterns": {"graphic"}, "bad_patterns": set(),
            "volume": "cropped"},
    "preppy": {"keywords": {"polo", "oxford", "chinos", "loafers", "cardigan", "sweater", "vest", "pleated", "tennis",
                            "rugby", "blazer", "boat", "collar", "khaki", "argyle", "cable", "skirt"},
               "formality": (2, 3), "accents": 2, "good_patterns": {"striped", "plaid"}, "bad_patterns": {"graphic"},
               "volume": "clean"},
    "athleisure": {"keywords": {"sweatpants", "joggers", "jogger", "leggings", "legging", "hoodie", "sneakers",
                                "sneaker", "trainers", "track", "sports", "bra", "running", "zip", "fleece",
                                "tank", "shorts", "cap", "performance", "windbreaker", "sweatshirt"},
                   "formality": (1, 1), "accents": 2, "good_patterns": set(), "bad_patterns": {"floral", "plaid"},
                   "volume": "any"},
    "vintage": {"keywords": {"vintage", "retro", "70s", "80s", "90s", "corduroy", "suede", "leather", "flared",
                             "flare", "denim", "trucker", "washed", "faded", "plaid", "bootcut", "western", "boots",
                             "cardigan", "wool", "tweed"},
                "formality": (2, 3), "accents": 2, "good_patterns": {"plaid", "striped", "floral"},
                "bad_patterns": set(), "volume": "any"},
    "business": {"keywords": {"blazer", "suit", "trousers", "oxford", "loafers", "heels", "pencil", "button", "dress",
                              "shirt", "tailored", "slacks", "pumps", "blouse", "belt", "watch", "coat", "tie"},
                 "formality": (4, 5), "accents": 1, "good_patterns": {"striped"},
                 "bad_patterns": {"graphic", "floral"}, "volume": "clean"},
    "boho": {"keywords": {"maxi", "flowy", "crochet", "fringe", "embroidered", "peasant", "linen", "suede", "sandals",
                          "paisley", "tiered", "kimono", "wrap", "floral", "earthy", "woven", "tassel"},
             "formality": (1, 3), "accents": 3, "good_patterns": {"floral"}, "bad_patterns": {"graphic"},
             "volume": "any"},
    "grunge": {"keywords": {"flannel", "ripped", "distressed", "plaid", "combat", "boots", "band", "leather", "black",
                            "oversized", "baggy", "beanie", "layered", "slip", "chain", "fishnet", "doc", "studded"},
               "formality": (1, 2), "accents": 1, "good_patterns": {"plaid", "graphic"}, "bad_patterns": {"floral"},
               "volume": "oversized"},
}

# occasion words -> formality band the outfit should sit in
_OCCASIONS = (
    ({"interview", "wedding", "gala", "formal", "office", "work", "business", "meeting", "funeral", "ceremony"}, (4, 5)),
    ({"date", "dinner", "brunch", "party", "rooftop", "night", "club", "cocktail", "concert", "bar", "birthday"}, (2, 4)),
    ({"class", "campus", "school", "errands", "casual", "hangout", "coffee", "weekend", "travel", "flight"}, (1, 3)),
    ({"gym", "run", "workout", "hike", "beach", "festival", "pool", "yoga"}, (1, 2)),
)

EMPTY = {"score": 0, "verdict": "Nothing to score yet", "notes": [], "criteria": [], "style_scores": {},
         "primary_style": None, "raw_score": 0, "source": "rules",
         "breakdown": {"color": 0, "pattern": 0, "formality": 0, "completeness": 0}}


# ---------------------------------------------------------------- sanitizing

def _formality(v: Any) -> int | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v):
        return None
    return int(v) if 1 <= v <= 5 else None


def _words(label: str) -> set[str]:
    return set(_WORD.findall(label.lower().replace("-", "")))


def _clean_item(raw: Any) -> dict[str, Any] | None:
    """Sanitize one item so the scoring below never raises."""
    if not isinstance(raw, dict) or not raw:
        return None
    cat = raw.get("category")
    category = cat.strip().lower() if isinstance(cat, str) and cat.strip().lower() in VALID_CATEGORIES else None
    color_text = raw.get("color").strip() if isinstance(raw.get("color"), str) else ""
    pattern = raw.get("pattern").strip().lower() if isinstance(raw.get("pattern"), str) else "solid"
    tags_raw = raw.get("style_tags")
    tags = [t.strip().lower() for t in tags_raw if isinstance(t, str) and t.strip()] if isinstance(tags_raw, list) else []
    lbl = raw.get("label")
    label = lbl.strip() if isinstance(lbl, str) and lbl.strip() else (category or "piece")
    words = _words(label)
    if "wide" in words and "leg" in words:
        words.add("wideleg")
    return {
        "category": category,
        # no color = treat as neutral, never penalized
        "color": normalize_color(color_text) if color_text else {"name": "unknown", "family": "neutral"},
        "pattern": pattern,
        "formality": _formality(raw.get("formality")),
        "style_tags": tags,
        "label": label,
        "words": words,
        "volume": ("oversized" if words & _OVERSIZED else "slim" if words & _SLIM else "unknown"),
        "cropped": bool(words & _CROPPED),
        "long": bool(words & _LONG),
    }


def _clamp10(x: float) -> int:
    return int(max(0, min(10, round(x))))


# ---------------------------------------------------------------- criteria (0-10 each, 5 = fine, 8+ earned)

def _palette(items: list[dict[str, Any]]) -> dict[str, Any]:
    multi = [it for it in items if it["color"].get("name") == "multicolor"]
    accents: dict[str, str] = {}
    accent_items: list[dict[str, Any]] = []
    neutrals: set[str] = set()
    for it in items:
        name, fam = str(it["color"].get("name", "")), str(it["color"].get("family", "unknown"))
        if name == "multicolor":
            continue
        if fam in ("neutral", "unknown"):
            if name not in ("", "unknown"):
                neutrals.add(name)
            continue
        if name not in accents:
            accent_items.append(it)
        accents[name] = fam
    units = len(multi) + sum(0.5 if f == "earth" else 1.0 for f in accents.values())
    return {"multi": multi, "accents": accents, "accent_items": accent_items, "neutrals": neutrals,
            "units": units, "distinct": len(multi) + len(accents)}


def _score_color(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    """10: one accent on neutrals. 7: all neutral or two tones in one family. 5: warm vs cool, or a multicolor
    piece plus an accent. 3: three accents. 1: four+ or two multicolor pieces."""
    p = _palette(items)
    if len(p["multi"]) >= 2:
        return 1, "Multiple multicolor pieces compete for attention."
    score, note = 5, None
    if p["distinct"] == 0:
        score, note = 7, "Clean neutral palette, safe rather than striking."
    elif p["distinct"] == 1 and not p["multi"]:
        score, note = 9, f"Your {p['accent_items'][0]['label']} is the one pop of color."
    elif p["multi"]:
        score, note = (6, f"Your {p['multi'][0]['label']} carries all the color.") if p["distinct"] == 1 else \
            (4, "A multicolor piece plus more accents gets busy.")
    elif p["units"] <= 2.0:
        fams = set(p["accents"].values())
        if "warm" in fams and "cool" in fams:
            score, note = 5, "Warm and cool accents fight a little."
        else:
            score, note = 7, "Your accent colors stay in one tonal family."
    elif p["units"] <= 3.0:
        score, note = 3, "Three competing colors pull focus."
    else:
        score, note = 1, "Too many competing colors pull focus."
    if len(p["neutrals"]) >= 4 or len(p["neutrals"]) + p["distinct"] >= 5:
        score -= 1
        note = note or "Too many different colours, even the neutrals, muddy the look."
    if p["distinct"] == 1 and len(items) >= 3 and len(p["neutrals"]) <= 2:
        score += 1  # one accent on a tight neutral base: the textbook palette
    return _clamp10(score), note


def _score_silhouette(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    """9: volume contrast (oversized top / slim bottom or the reverse). 7: dress with a clear length, or one
    stated volume with the other unknown. 6: nothing stated. 5: oversized on oversized. 4: slim on slim."""
    tops = [it for it in items if it["category"] in ("top", "outerwear")]
    bottoms = [it for it in items if it["category"] == "bottom"]
    dresses = [it for it in items if it["category"] == "dress"]
    if dresses and not bottoms:
        d = dresses[0]
        return (7, None) if (d["long"] or d["cropped"] or d["volume"] != "unknown") else (6, None)
    tv = {t["volume"] for t in tops} - {"unknown"}
    bv = {b["volume"] for b in bottoms} - {"unknown"}
    if not tops or not bottoms:
        return 5, None
    if tv and bv:
        if tv == {"oversized"} and bv == {"slim"} or tv == {"slim"} and bv == {"oversized"}:
            return 9, f"Your {tops[0]['label']} balances your {bottoms[0]['label']}."
        if "oversized" in tv and "oversized" in bv:
            return 5, "Oversized on oversized loses your shape."
        if tv == {"slim"} and bv == {"slim"}:
            return 4, "Slim on slim reads flat; add some volume."
        return 6, None
    score = 6 if (tv or bv) else 5
    if any(t["cropped"] for t in tops) and bottoms and (bottoms[0]["volume"] == "oversized" or "rise" in bottoms[0]["words"]):
        score += 2
        return score, f"Cropped {tops[0]['label']} over {bottoms[0]['label']} lengthens your line."
    return score, None


def _score_pattern(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    """9: one print. 7: all solid, or stripes plus one print. 4: two loud prints. 1: three or more.
    +1 for two or three different textures (knit, leather, denim...)."""
    busy = [it for it in items if it["pattern"] in BUSY_PATTERNS]
    if len(busy) == 0:
        score, note = 7, None
    elif len(busy) == 1:
        score, note = 9, f"Your {busy[0]['label']} brings pattern without clutter."
    elif len(busy) == 2:
        kinds = [it["pattern"] for it in busy]
        if "striped" in kinds and kinds[0] != kinds[1]:
            score, note = 7, "Stripes with one print is a classic mix."
        else:
            score, note = 4, "Two busy patterns compete for attention here."
    else:
        score, note = 1, "Three or more loud patterns clash right now."
    textures = {w for it in items for w in it["words"] & _TEXTURES}
    if 2 <= len(textures) <= 3:
        score += 1
        note = note or f"Mixing {' and '.join(sorted(textures)[:2])} adds texture."
    return _clamp10(score), note


def _score_formality(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    """9: every piece within one step. 5: two steps apart. 2: three or more. 5 when fewer than two pieces say."""
    known = [it for it in items if it["formality"] is not None]
    if len(known) < 2:
        return 5, None
    hi = max(known, key=lambda x: x["formality"])
    lo = min(known, key=lambda x: x["formality"])
    spread = hi["formality"] - lo["formality"]
    if spread == 0:
        return 9, "Every piece matches the same dress code."
    if spread == 1:
        return 8, "Every piece sits in the same dress code."
    if spread == 2:
        return 5, f"Your {hi['label']} feels dressier than your {lo['label']}."
    return 2, f"Your {hi['label']} and {lo['label']} clash in formality."


def _style_share(items: list[dict[str, Any]]) -> tuple[Counter[str], int]:
    tagged = [it for it in items if it["style_tags"]]
    return Counter(t for it in tagged for t in set(it["style_tags"])), len(tagged)


def _score_style(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    """9: every piece shares the dominant style. 7: three quarters. 5: half. 3: less. -2 when the pieces span
    three unrelated style families, -1 for five or more different tags. 5 when nothing is tagged."""
    counts, n = _style_share(items)
    if not counts or n < 2:
        return 5, None
    top_tag, count = counts.most_common(1)[0]
    share = count / n
    if share >= 0.999 and len(counts) <= 4:
        score, note = 9, f"Your pieces all lean {top_tag}."
    elif share >= 0.999:
        score, note = 7, f"Your pieces all lean {top_tag}, but each pulls elsewhere too."
    elif share >= 0.75:
        score, note = 7, f"Most of your pieces lean {top_tag}."
    elif share >= 0.5:
        score, note = 5, f"Only half your pieces lean {top_tag}."
    else:
        score, note = 3, "Your pieces don't agree on a style."
    families = {STYLE_FAMILIES.get(t) for t in counts if t in STYLE_FAMILIES}
    if len(families) >= 3:
        score -= 2
        note = "Street, polished and boho pieces in one look read as a costume."
    if len(counts) >= 7:
        score -= 2
        note = note if share < 0.75 else "Too many style directions in one outfit."
    elif len(counts) >= 5:
        score -= 1
    return _clamp10(score), note


def _score_completeness(items: list[dict[str, Any]]) -> tuple[int, list[str]]:
    """9: top + bottom (or dress) + shoes. 5: base without shoes. 2: no top-and-bottom base."""
    cats = {it["category"] for it in items if it["category"]}
    notes: list[str] = []
    has_base = ("top" in cats and "bottom" in cats) or "dress" in cats
    if has_base:
        score = 9 if "shoes" in cats else 5
    else:
        score = 2
        if "top" in cats:
            notes.append("You need a bottom with that top.")
        elif "bottom" in cats:
            notes.append("You need a top with that bottom.")
        else:
            notes.append("Add a top and bottom to build the look.")
    if "shoes" not in cats:
        notes.append("Add shoes to finish it.")
    return score, notes


def _score_layering(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    """8: one considered extra (outerwear or an accessory). 9: outerwear plus one accessory. 5: none.
    4: three or more accessories."""
    outer = [it for it in items if it["category"] == "outerwear"]
    acc = [it for it in items if it["category"] == "accessory"]
    if len(acc) >= 3:
        return 4, "Too many accessories; pick one or two."
    if len(outer) >= 2:
        return 5, "Two outer layers is one too many."
    extras = len(outer) + len(acc)
    if extras == 0:
        return 5, None
    if extras == 1:
        piece = (outer or acc)[0]
        return 8, f"Your {piece['label']} finishes the look."
    return 9, "Layer plus accessory, considered without clutter."


def _score_occasion(items: list[dict[str, Any]], occasion: str) -> tuple[int, str | None]:
    """9: the outfit's average formality sits in the occasion's band. 6: one step off. 3: two or more.
    6 when the occasion isn't recognised or no piece states formality."""
    words = _words(occasion)
    band = next((b for ws, b in _OCCASIONS if words & ws), None)
    known = [it["formality"] for it in items if it["formality"] is not None]
    if band is None or not known:
        return 6, None
    avg = sum(known) / len(known)
    lo, hi = band
    off = lo - avg if avg < lo else avg - hi if avg > hi else 0.0
    if off <= 0.25:
        return 9, f"Dressed right for {occasion.strip()}."
    if off <= 1.25:
        return 6, f"A touch {'casual' if avg < lo else 'dressy'} for {occasion.strip()}."
    return 3, f"Too {'casual' if avg < lo else 'dressy'} for {occasion.strip()}."


# ---------------------------------------------------------------- per-style execution (0-100)

def _style_score(style: str, items: list[dict[str, Any]], crit: dict[str, int]) -> int:
    """How well the outfit executes `style`: tag share 35, label keywords 20, formality band 15, palette 15,
    patterns 10, silhouette 5. Pulled toward the general completeness/formality criteria so a half outfit
    can't 'execute' anything."""
    prof = STYLE_PROFILES[style]
    n = len(items)
    tagged = sum(1 for it in items if style in it["style_tags"])
    share = tagged / n
    hits = sum(1 for it in items if it["words"] & prof["keywords"])
    keyword = min(1.0, hits / max(2, n - 1))
    known = [it["formality"] for it in items if it["formality"] is not None]
    lo, hi = prof["formality"]
    if known:
        avg = sum(known) / len(known)
        off = lo - avg if avg < lo else avg - hi if avg > hi else 0.0
        form = 1.0 if off <= 0.25 else 0.6 if off <= 1.0 else 0.2 if off <= 2.0 else 0.0
    else:
        form = 0.5
    p = _palette(items)
    over = p["units"] - prof["accents"]
    palette = 1.0 if over <= 0 else 0.6 if over <= 1 else 0.2
    if style in ("y2k", "boho") and p["distinct"] == 0:
        palette = 0.6  # these styles want some colour
    pats = [it["pattern"] for it in items]
    pattern = 0.7
    if any(pt in prof["bad_patterns"] for pt in pats):
        pattern = 0.2
    elif any(pt in prof["good_patterns"] for pt in pats):
        pattern = 1.0
    elif style in ("minimalist", "business") and all(pt == "solid" for pt in pats):
        pattern = 1.0
    vols = [it["volume"] for it in items if it["category"] in ("top", "bottom", "outerwear")]
    want = prof["volume"]
    if want == "any":
        sil = 0.7
    elif want == "cropped":
        sil = 1.0 if any(it["cropped"] for it in items) else 0.4
    elif want == "oversized":
        sil = 1.0 if "oversized" in vols else 0.3 if "slim" in vols else 0.5
    else:  # clean
        sil = 0.3 if vols.count("oversized") >= 2 else 1.0 if "slim" in vols else 0.6
    raw = 100 * (0.35 * share + 0.20 * keyword + 0.15 * form + 0.15 * palette + 0.10 * pattern + 0.05 * sil)
    # a style is executed by a whole outfit: an incomplete or dress-code-mixed one can't score high as anything
    gate = min(crit["completeness"], max(crit["formality"], 4)) / 9.0
    return int(round(max(0, min(100, raw * min(1.0, 0.4 + 0.6 * gate)))))


def style_scores(items: list[dict[str, Any]], crit: dict[str, int]) -> dict[str, int]:
    return {s: _style_score(s, items, crit) for s in STYLES}


# ---------------------------------------------------------------- aggregation

def _weighted_raw(crit: dict[str, int]) -> float:
    ws = {k: w for k, w in WEIGHTS.items() if k in crit}
    return 10.0 * sum(crit[k] * w for k, w in ws.items()) / sum(ws.values())


def calibrate(raw: float) -> int:
    """Monotone piecewise-linear map of the raw 0-100 onto the badge scale (see CALIBRATION)."""
    raw = max(0.0, min(100.0, raw))
    for (x0, y0), (x1, y1) in zip(CALIBRATION, CALIBRATION[1:]):
        if raw <= x1:
            return int(round(y0 + (y1 - y0) * (raw - x0) / (x1 - x0)))
    return 100


_PHRASES = {  # criterion -> (strength, weakness)
    "color": ("clean palette", "palette too busy"),
    "silhouette": ("strong silhouette", "shapeless silhouette"),
    "pattern": ("patterns balanced", "patterns fighting"),
    "formality": ("one dress code", "mixed dress codes"),
    "style": ("cohesive style", "styles clash"),
    "completeness": ("complete look", "not a full outfit"),
    "layering": ("considered layering", "needs a finishing piece"),
    "occasion": ("right for the occasion", "wrong for the occasion"),
}


def _verdict(score: int, style: str, crit: dict[str, int], cats: set) -> str:
    """'68 as streetwear: strong silhouette, palette too busy' (weakest and strongest criterion by weight)."""
    if score >= CERTIFIED_THRESHOLD:
        return f"{score} as {style}: certified fit check"
    ranked = sorted(crit, key=lambda k: (crit[k], -WEIGHTS[k]))
    weak = [k for k in ranked if crit[k] <= 5]
    strong = [k for k in reversed(ranked) if crit[k] >= 8]
    if "completeness" in weak and "shoes" not in cats and crit["completeness"] >= 5:
        weak_phrase = "add shoes"
    elif weak:
        weak_phrase = _PHRASES[weak[0]][1]
    else:
        weak_phrase = None
    strong_phrase = _PHRASES[strong[0]][0] if strong else None
    parts = [p for p in (strong_phrase, weak_phrase) if p]
    if not parts:
        parts = ["fine, nothing stands out"]
    return f"{score} as {style}: {', '.join(parts)}"


def _old_breakdown(crit: dict[str, int]) -> dict[str, int]:
    """v1 keys the app still renders: color/40, pattern/20, formality/20, completeness/20."""
    return {"color": crit["color"] * 4, "pattern": crit["pattern"] * 2, "formality": crit["formality"] * 2,
            "completeness": crit["completeness"] * 2}


def rules_criteria(items: list[dict[str, Any]], occasion: str | None = None) -> tuple[dict[str, int], dict[str, str | None], list[str]]:
    """(criterion -> 0-10, criterion -> note, completeness notes) from the rules alone."""
    c_score, c_note = _score_color(items)
    s_score, s_note = _score_silhouette(items)
    p_score, p_note = _score_pattern(items)
    f_score, f_note = _score_formality(items)
    st_score, st_note = _score_style(items)
    comp_score, comp_notes = _score_completeness(items)
    l_score, l_note = _score_layering(items)
    crit = {"color": c_score, "silhouette": s_score, "pattern": p_score, "formality": f_score, "style": st_score,
            "completeness": comp_score, "layering": l_score}
    notes = {"color": c_note, "silhouette": s_note, "pattern": p_note, "formality": f_note, "style": st_note,
             "completeness": comp_notes[0] if comp_notes else None, "layering": l_note}
    if isinstance(occasion, str) and occasion.strip():
        crit["occasion"], notes["occasion"] = _score_occasion(items, occasion)
    return crit, notes, comp_notes


# ---------------------------------------------------------------- photo-aware critic (optional)

def _critic_key(photo_url: str, version: str) -> str:
    return hashlib.sha1(f"{version}|{photo_url}".encode()).hexdigest()[:24]


def ai_critique(photo_url: str, items: list[dict[str, Any]], occasion: str | None) -> dict[str, Any] | None:
    """One Claude vision call (prompts.FIT_CRITIC) -> {criteria: {name: {score, note}}, style}, cached per
    photo url + prompt version. None when AI is off, over budget, or the reply is unusable."""
    from ..store import store
    from .llm import ai_json, text_mock
    from .prompts import FIT_CRITIC, FIT_CRITIC_VERSION

    if text_mock() or not isinstance(photo_url, str) or not photo_url.startswith(("http://", "https://")):
        return None
    key = _critic_key(photo_url, FIT_CRITIC_VERSION)
    try:
        hit = store.get("fit_critic_cache", key)
        if hit and isinstance(hit.get("critique"), dict):
            return hit["critique"]
        prompt = FIT_CRITIC.format(
            items_json=str([{"category": it["category"], "label": it["label"], "color": it["color"].get("name")}
                            for it in items]),
            occasion=occasion or "none given",
            styles=", ".join(STYLES))
        raw = ai_json(prompt, image_url=photo_url, max_tokens=700)
    except Exception:  # noqa: BLE001 — the badge must never fail because the critic did
        return None
    out = _parse_critique(raw)
    if out:
        try:
            store.put("fit_critic_cache", key, {"photo_url": photo_url, "critique": out})
        except Exception:  # noqa: BLE001
            pass
    return out


def _parse_critique(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    crit_raw = raw.get("criteria")
    if not isinstance(crit_raw, dict):
        return None
    crit: dict[str, dict[str, Any]] = {}
    for name in CRITERIA:
        v = crit_raw.get(name)
        if isinstance(v, dict):
            s, note = v.get("score"), v.get("note")
        else:
            s, note = v, None
        if isinstance(s, bool) or not isinstance(s, (int, float)):
            continue
        crit[name] = {"score": _clamp10(s), "note": note.strip() if isinstance(note, str) and note.strip() else None}
    if len(crit) < 4:
        return None
    style = raw.get("style")
    return {"criteria": crit, "style": style.strip().lower() if isinstance(style, str) and style.strip().lower() in STYLES else None}


# ---------------------------------------------------------------- entry point

def score_outfit(items: list[dict[str, Any]], *, occasion: str | None = None, target_style: str | None = None,
                 photo_url: str | None = None, use_ai: bool = True) -> dict[str, Any]:
    """{score 0-100, verdict, notes (2-4), breakdown (v1 keys), criteria [{name, score_10, note}],
    style_scores {style: 0-100}, primary_style, raw_score, source "rules"|"rules+ai"}."""
    cleaned = [c for raw in (items if isinstance(items, list) else []) if (c := _clean_item(raw))]
    if not cleaned:
        return {**EMPTY, "breakdown": dict(EMPTY["breakdown"]), "criteria": [], "style_scores": {}}
    crit, notes, comp_notes = rules_criteria(cleaned, occasion)
    source = "rules"
    ai_style = None
    if photo_url and use_ai:
        critique = ai_critique(photo_url, cleaned, occasion)
        if critique:
            source = "rules+ai"
            ai_style = critique["style"]
            for name, v in critique["criteria"].items():
                if name in crit:
                    crit[name] = _clamp10((1 - AI_BLEND) * crit[name] + AI_BLEND * v["score"])
                    if v["note"] and crit[name] <= 6:
                        notes[name] = v["note"]  # the critic saw the photo; its criticism beats our guess
    styles = style_scores(cleaned, crit)
    if ai_style:
        styles[ai_style] = min(100, styles[ai_style] + 10)
    target = target_style.strip().lower() if isinstance(target_style, str) and target_style.strip().lower() in STYLES else None
    primary = target or max(STYLES, key=lambda s: styles[s])

    general_raw = _weighted_raw(crit)
    raw = (1 - STYLE_BLEND) * general_raw + STYLE_BLEND * styles[primary]
    score = calibrate(raw)
    cats = {it["category"] for it in cleaned}
    if not (("top" in cats and "bottom" in cats) or "dress" in cats):
        score = min(score, NO_BASE_SCORE_CAP)
    if min(crit.values()) < 8:
        score = min(score, CERTIFIED_THRESHOLD - 1)  # 90+ only when every criterion is at least 8

    # notes: problems first (weakest up), then what works (strongest, heaviest criterion first)
    weak = sorted((k for k in crit if crit[k] <= 5), key=lambda k: (crit[k], -WEIGHTS[k]))
    strong = sorted((k for k in crit if crit[k] > 5), key=lambda k: (-crit[k], -WEIGHTS[k]))
    ordered = weak + strong
    out_notes: list[str] = []
    for n in (*comp_notes, *(notes[k] for k in ordered if k != "completeness")):
        if n and n not in out_notes and len(out_notes) < 4:
            out_notes.append(n)
    if len(out_notes) < 2:
        out_notes.append(f"Reads as {primary}; lean into it to score higher.")

    criteria = [{"name": k, "score_10": crit[k], "note": notes.get(k)} for k in CRITERIA if k in crit]
    return {"score": score, "verdict": _verdict(score, primary, crit, cats), "notes": out_notes,
            "breakdown": _old_breakdown(crit), "criteria": criteria, "style_scores": styles,
            "primary_style": primary, "raw_score": int(round(raw)), "source": source}


if __name__ == "__main__":
    for outfit in (
        [{"category": "top", "color": "black", "formality": 2, "style_tags": ["streetwear"], "label": "black tee"},
         {"category": "bottom", "color": "light blue", "formality": 2, "style_tags": ["streetwear"],
          "label": "light blue baggy jeans"},
         {"category": "shoes", "color": "white", "formality": 2, "label": "white sneakers"}],
        [{"category": "dress", "color": "red", "pattern": "floral", "formality": 3, "label": "red floral dress"},
         {"category": "outerwear", "color": "green", "pattern": "plaid", "formality": 2, "label": "green plaid jacket"}],
        [{"category": "top", "color": "mustard", "pattern": "graphic", "formality": 1, "label": "mustard graphic hoodie"}],
    ):
        print(score_outfit(outfit))
