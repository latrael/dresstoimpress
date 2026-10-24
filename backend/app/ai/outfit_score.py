"""Fit Score: a 0-100 badge for an outfit ("87 · Clean neutrals, one pop"). Pure rules, no AI, free.

First draft by Gemini, reviewed by Adam. Used by POST /ai/fit-score (Fit Check posts, complete-the-look
outfits, closet combos). Items are closet-item / FitTag shaped: category, color, pattern, formality,
style_tags, label; any of them may be missing.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .colors import normalize_color

CERTIFIED_THRESHOLD = 90

COLOR_ONE_ACCENT = 40
COLOR_ALL_NEUTRAL = 36
COLOR_SAME_FAMILY_ACCENTS = 34
COLOR_WARM_COOL_ACCENTS = 26
COLOR_TOO_MANY_ACCENTS = 16
COLOR_MULTI_CLASH = 12
EARTH_ACCENT_WEIGHT = 0.5  # earth tones work almost like neutrals

PATTERN_CLEAN = 20
PATTERN_CLASSIC_MIX = 14
PATTERN_TWO_BUSY = 10
PATTERN_TOO_BUSY = 0
BUSY_PATTERNS = frozenset({"striped", "plaid", "graphic", "floral"})

FORMALITY_COHESIVE = 20
FORMALITY_DEFAULT = 15
FORMALITY_MIXED = 12
FORMALITY_CLASH = 4

COMPLETENESS_MAX = 20
COMPLETENESS_BASE = 14
COMPLETENESS_SHOES = 6
COMPLETENESS_EXTRA = 2
COMPLETENESS_NO_BASE_PER_ITEM = 4
COMPLETENESS_NO_BASE_CAP = 12
NO_BASE_SCORE_CAP = 60  # one hoodie on its own isn't an outfit yet, however good its color

VALID_CATEGORIES = frozenset({"top", "bottom", "outerwear", "shoes", "dress", "accessory"})
EMPTY = {"score": 0, "verdict": "Nothing to score yet", "notes": [],
         "breakdown": {"color": 0, "pattern": 0, "formality": 0, "completeness": 0}}


def _formality(v: Any) -> int | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v):
        return None
    return int(v) if 1 <= v <= 5 else None


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
    return {
        "category": category,
        # no color = treat as neutral, never penalized
        "color": normalize_color(color_text) if color_text else {"name": "unknown", "family": "neutral"},
        "pattern": pattern,
        "formality": _formality(raw.get("formality")),
        "style_tags": tags,
        "label": label,
    }


def _score_color(items: list[dict[str, Any]]) -> tuple[int, str | None, bool]:
    """(score, note, has_single_pop)."""
    multi = [it for it in items if it["color"].get("name") == "multicolor"]
    if len(multi) >= 2:
        return COLOR_MULTI_CLASH, "Multiple multicolor pieces compete for attention.", False
    accent_families: dict[str, str] = {}
    accent_items: list[dict[str, Any]] = list(multi)
    for it in items:
        name, fam = str(it["color"].get("name", "")), str(it["color"].get("family", "unknown"))
        if name == "multicolor" or fam in ("neutral", "unknown"):
            continue
        accent_items.append(it)
        accent_families[name] = fam
    units = float(len(multi)) + sum(EARTH_ACCENT_WEIGHT if f == "earth" else 1.0 for f in accent_families.values())
    distinct = len(multi) + len(accent_families)
    if distinct == 0:
        return COLOR_ALL_NEUTRAL, "Your clean neutral palette looks effortless.", False
    if distinct == 1 or units <= 1.0:
        return COLOR_ONE_ACCENT, f"Your {accent_items[0]['label']} is the one pop of color.", True
    if units <= 2.0:
        fams = set(accent_families.values())
        if "warm" in fams and "cool" in fams:
            return COLOR_WARM_COOL_ACCENTS, "Your warm and cool tones make a bold contrast.", False
        return COLOR_SAME_FAMILY_ACCENTS, "Your accent colors stay in the same tonal family.", False
    return COLOR_TOO_MANY_ACCENTS, "Too many competing colors pull focus.", False


def _score_pattern(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    busy = [it for it in items if it["pattern"] in BUSY_PATTERNS]
    if len(busy) == 0:
        return PATTERN_CLEAN, None
    if len(busy) == 1:
        return PATTERN_CLEAN, f"Your {busy[0]['label']} brings pattern without clutter."
    if len(busy) == 2:
        kinds = [it["pattern"] for it in busy]
        if "striped" in kinds and kinds[0] != kinds[1]:
            return PATTERN_CLASSIC_MIX, "Stripes with one print is a classic mix."
        return PATTERN_TWO_BUSY, "Two busy patterns compete for attention here."
    return PATTERN_TOO_BUSY, "Three or more loud patterns clash right now."


def _score_formality(items: list[dict[str, Any]]) -> tuple[int, str | None]:
    known = [it for it in items if it["formality"] is not None]
    if len(known) < 2:
        return FORMALITY_DEFAULT, None
    hi = max(known, key=lambda x: x["formality"])
    lo = min(known, key=lambda x: x["formality"])
    spread = hi["formality"] - lo["formality"]
    if spread <= 1:
        return FORMALITY_COHESIVE, "Every piece matches the same dress code."
    if spread == 2:
        return FORMALITY_MIXED, f"Your {hi['label']} feels dressier than your {lo['label']}."
    return FORMALITY_CLASH, f"Your {hi['label']} and {lo['label']} clash in formality."


def _score_completeness(items: list[dict[str, Any]]) -> tuple[int, list[str]]:
    cats = {it["category"] for it in items if it["category"]}
    notes: list[str] = []
    if ("top" in cats and "bottom" in cats) or "dress" in cats:
        score = COMPLETENESS_BASE
        if "shoes" in cats:
            score += COMPLETENESS_SHOES
        if "outerwear" in cats or "accessory" in cats:
            score += COMPLETENESS_EXTRA
        score = min(score, COMPLETENESS_MAX)
    else:
        score = min(len(items) * COMPLETENESS_NO_BASE_PER_ITEM, COMPLETENESS_NO_BASE_CAP)
        if "top" in cats:
            notes.append("You need a bottom with that top.")
        elif "bottom" in cats:
            notes.append("You need a top with that bottom.")
        else:
            notes.append("Add a top and bottom to build the look.")
    if "shoes" not in cats:
        notes.append("Add shoes to finish it.")
    return score, notes


def _verdict(score: int, b: dict[str, int], has_pop: bool, cats: set) -> str:
    """<= 6 words, from the weakest part first."""
    if score >= CERTIFIED_THRESHOLD:
        return "Certified fit check"
    if b["pattern"] <= PATTERN_TWO_BUSY:
        return "Patterns are fighting"
    if b["formality"] <= FORMALITY_MIXED:
        return "Mixed dress codes"
    if b["completeness"] < COMPLETENESS_BASE:
        return "Great start, finish the look"
    if "shoes" not in cats:
        return "Almost there, add shoes"
    if b["color"] == COLOR_ONE_ACCENT and has_pop:
        return "Clean neutrals, one pop"
    if b["color"] == COLOR_ALL_NEUTRAL:
        return "Clean neutrals, effortless vibe"
    if b["color"] in (COLOR_SAME_FAMILY_ACCENTS, COLOR_WARM_COOL_ACCENTS):
        return "Bold mix, it works"
    return "Loud palette, tone it down"


def score_outfit(items: list[dict[str, Any]]) -> dict[str, Any]:
    """{score 0-100, verdict, notes (2-4), breakdown {color/40, pattern/20, formality/20, completeness/20}}."""
    cleaned = [c for raw in (items if isinstance(items, list) else []) if (c := _clean_item(raw))]
    if not cleaned:
        return {**EMPTY, "breakdown": dict(EMPTY["breakdown"])}
    c_score, c_note, has_pop = _score_color(cleaned)
    p_score, p_note = _score_pattern(cleaned)
    f_score, f_note = _score_formality(cleaned)
    comp_score, comp_notes = _score_completeness(cleaned)

    tag_counts: Counter[str] = Counter(t for it in cleaned for t in set(it["style_tags"]))
    style_note = None
    if tag_counts:
        top_tag, count = tag_counts.most_common(1)[0]
        if count == 2:
            style_note = f"Both pieces lean {top_tag}."
        elif count > 2:
            style_note = f"Your pieces all lean {top_tag}."

    notes: list[str] = []
    for n in (c_note, *comp_notes, f_note, p_note, style_note):
        if n and n not in notes and len(notes) < 4:
            notes.append(n)
    if len(notes) < 2:
        notes.append("Your silhouette stays clean and easy to wear.")

    breakdown = {"color": c_score, "pattern": p_score, "formality": f_score, "completeness": comp_score}
    total = sum(breakdown.values())
    cats = {it["category"] for it in cleaned}
    if not (("top" in cats and "bottom" in cats) or "dress" in cats):
        total = min(total, NO_BASE_SCORE_CAP)
    return {"score": total, "verdict": _verdict(total, breakdown, has_pop, cats), "notes": notes,
            "breakdown": breakdown}


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
