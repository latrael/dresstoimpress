"""Color normalization and duplicate closet detection (first draft by Gemini, reviewed by Adam).

normalize_color("light wash blue") -> {"name": "light blue", "family": "neutral", "hex": "#ADD8E6"}
Families: neutral, earth, warm, cool, unknown ("multicolor" and anything unmappable).

Used by:
- finder.match_score: "ivory" matches "off white", "navy blue" matches "dark navy".
- service.tag_closet_item: `duplicate_of` when the new photo looks like something already in the closet.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal, Optional

ColorFamily = Literal["neutral", "warm", "cool", "earth", "unknown"]

FALLBACK_HEX = "#9E9E9E"
DUPLICATE_OVERLAP = 0.6  # share of the shorter label's words that must match

CANONICAL_COLORS: dict[str, tuple[ColorFamily, str]] = {
    "black": ("neutral", "#1A1A1A"), "white": ("neutral", "#FFFFFF"), "off-white": ("neutral", "#FAF9F6"),
    "cream": ("neutral", "#FFFDD0"), "beige": ("neutral", "#F5F5DC"), "grey": ("neutral", "#808080"),
    "charcoal": ("neutral", "#36454F"), "navy": ("neutral", "#1B2A4A"), "light blue": ("neutral", "#ADD8E6"),
    "denim": ("neutral", "#4A6B82"), "silver": ("neutral", "#C0C0C0"),
    "olive": ("earth", "#708238"), "sage": ("earth", "#9CAF88"), "khaki": ("earth", "#C3B091"),
    "brown": ("earth", "#6F4E37"), "tan": ("earth", "#D2B48C"), "camel": ("earth", "#C19A6B"),
    "rust": ("earth", "#B7410E"), "burgundy": ("earth", "#800020"),
    "red": ("warm", "#D32F2F"), "pink": ("warm", "#F48FB1"), "orange": ("warm", "#F57C00"),
    "mustard": ("warm", "#E1AD01"), "yellow": ("warm", "#FBC02D"), "gold": ("warm", "#D4AF37"),
    "blue": ("cool", "#1976D2"), "teal": ("cool", "#008080"), "green": ("cool", "#388E3C"),
    "purple": ("cool", "#7B1FA2"), "lavender": ("cool", "#B39DDB"),
    "multicolor": ("unknown", FALLBACK_HEX),
}

MULTI_WORDS = ("multicolor", "multi-color", "multi color", "multicolored", "multi-colored", "multi coloured",
               "tie-dye", "tie dye", "rainbow", "colorblock", "color block")

# Checked in order, before single words: longer / more specific phrases first.
PHRASE_ALIASES: tuple[tuple[str, str], ...] = (
    ("off-white", "off-white"), ("off white", "off-white"), ("offwhite", "off-white"), ("eggshell", "off-white"),
    ("ivory", "off-white"), ("ecru", "cream"), ("bone", "cream"), ("vanilla", "cream"),
    ("oatmeal", "beige"), ("sand", "beige"), ("taupe", "beige"), ("champagne", "beige"),
    ("stone wash", "denim"), ("stonewash", "denim"), ("stone", "beige"),
    ("charcoal grey", "charcoal"), ("charcoal gray", "charcoal"), ("dark grey", "charcoal"),
    ("dark gray", "charcoal"), ("slate grey", "charcoal"), ("slate gray", "charcoal"), ("gunmetal", "charcoal"),
    ("heather grey", "grey"), ("heather gray", "grey"), ("light grey", "grey"), ("light gray", "grey"),
    ("ash grey", "grey"), ("ash gray", "grey"), ("dove grey", "grey"),
    ("light-wash", "light blue"), ("light wash", "light blue"), ("acid wash", "light blue"),
    ("sky blue", "light blue"), ("baby blue", "light blue"), ("powder blue", "light blue"),
    ("ice blue", "light blue"), ("pastel blue", "light blue"), ("pale blue", "light blue"),
    ("medium wash", "denim"), ("dark wash", "denim"), ("dark-wash", "denim"), ("mid wash", "denim"),
    ("raw denim", "denim"), ("indigo", "denim"), ("chambray", "denim"), ("jean", "denim"),
    ("dark navy", "navy"), ("navy blue", "navy"), ("midnight blue", "navy"), ("dark blue", "navy"),
    ("mustard yellow", "mustard"), ("ochre", "mustard"), ("marigold", "mustard"),
    ("burnt orange", "rust"), ("terracotta", "rust"), ("terra cotta", "rust"), ("copper", "rust"),
    ("cinnamon", "rust"), ("wine", "burgundy"), ("maroon", "burgundy"), ("oxblood", "burgundy"),
    ("merlot", "burgundy"), ("bordeaux", "burgundy"), ("cranberry", "burgundy"),
    ("plum", "purple"), ("eggplant", "purple"), ("aubergine", "purple"), ("violet", "purple"),
    ("magenta", "pink"), ("fuchsia", "pink"), ("blush", "pink"), ("rose", "pink"), ("coral", "pink"),
    ("salmon", "pink"), ("peach", "orange"), ("apricot", "orange"), ("tangerine", "orange"),
    ("lilac", "lavender"), ("periwinkle", "lavender"), ("mauve", "lavender"), ("wisteria", "lavender"),
    ("mint", "sage"), ("pistachio", "sage"), ("eucalyptus", "sage"), ("seafoam", "sage"),
    ("army green", "olive"), ("military green", "olive"), ("moss green", "olive"), ("moss", "olive"),
    ("khaki green", "olive"), ("forest green", "green"), ("emerald", "green"), ("kelly green", "green"),
    ("hunter green", "green"), ("lime", "green"), ("turquoise", "teal"), ("aqua", "teal"),
    ("cyan", "teal"), ("petrol", "teal"), ("royal blue", "blue"), ("cobalt", "blue"), ("sapphire", "blue"),
    ("chocolate", "brown"), ("espresso", "brown"), ("coffee", "brown"), ("mocha", "brown"),
    ("walnut", "brown"), ("chestnut", "brown"), ("cognac", "camel"), ("caramel", "camel"),
    ("toffee", "camel"), ("fawn", "tan"), ("buff", "tan"), ("crimson", "red"), ("scarlet", "red"),
    ("cherry", "red"), ("ruby", "red"), ("canary", "yellow"), ("lemon", "yellow"), ("butter", "yellow"),
    ("metallic gold", "gold"), ("brass", "gold"), ("bronze", "gold"), ("metallic silver", "silver"),
    ("chrome", "silver"), ("pewter", "silver"), ("platinum", "silver"), ("jet black", "black"),
    ("onyx", "black"), ("ebony", "black"), ("pure white", "white"), ("snow white", "white"),
    ("optic white", "white"),
)

TOKEN_ALIASES: dict[str, str] = {
    **{name: name for name in CANONICAL_COLORS if " " not in name and "-" not in name},
    "gray": "grey", "slate": "charcoal", "lilac": "lavender", "golden": "gold",
    "multi": "multicolor", "multicolored": "multicolor",
}

# Two color words that together mean one color ("olive green" is olive, not multicolor).
COMPOUND_PAIRS: dict[frozenset[str], str] = {
    frozenset(p): c for p, c in [
        (("mustard", "yellow"), "mustard"), (("olive", "green"), "olive"), (("sage", "green"), "sage"),
        (("navy", "blue"), "navy"), (("denim", "blue"), "denim"), (("charcoal", "grey"), "charcoal"),
        (("rust", "orange"), "rust"), (("burgundy", "red"), "burgundy"), (("camel", "brown"), "camel"),
        (("tan", "brown"), "tan"), (("khaki", "beige"), "khaki"), (("lavender", "purple"), "lavender"),
        (("teal", "blue"), "teal"), (("teal", "green"), "teal"), (("blue", "green"), "teal"),
        (("khaki", "green"), "olive"), (("grey", "blue"), "blue"),
    ]
}

LIGHT = {"light", "sky", "baby", "pale", "powder", "ice", "pastel"}
SEPARATORS = re.compile(r"\band\b|&|/|,|\+|\bwith\b")
LABEL_STOPWORDS = frozenset("the a an with and or in on of for to by my pair size new".split())
# Color words are left out when comparing labels (color is compared separately).
_COLOR_WORDS = (set(TOKEN_ALIASES) | {w for n in CANONICAL_COLORS for w in re.findall(r"[a-z]+", n)}
                | {w for p, _ in PHRASE_ALIASES for w in re.findall(r"[a-z]+", p)}
                | LIGHT | {"dark", "deep", "bright", "washed"})


def _response(name: str) -> dict:
    family, hex_code = CANONICAL_COLORS[name]
    return {"name": name, "family": family, "hex": hex_code}


def _single(segment: str) -> Optional[str]:
    """One color phrase -> canonical name, or None if unknown."""
    cleaned = " ".join(segment.split())
    if not cleaned:
        return None
    if cleaned in CANONICAL_COLORS:
        return cleaned
    for phrase, target in PHRASE_ALIASES:
        if re.search(rf"(?:^|[\s\-]){re.escape(phrase)}(?:$|[\s\-])", cleaned):
            return target
    tokens = re.findall(r"[a-z0-9]+", cleaned)
    matched: list[str] = []
    for tok in tokens:
        canon = TOKEN_ALIASES.get(tok)
        if canon and canon not in matched:
            matched.append(canon)
    if "blue" in tokens and LIGHT & set(tokens):
        return "light blue"
    if "blue" in tokens and {"dark", "midnight", "navy"} & set(tokens):
        return "navy"
    if {"grey", "gray"} & set(tokens) and {"charcoal", "dark", "slate"} & set(tokens):
        return "charcoal"
    if "white" in tokens and "off" in tokens:
        return "off-white"
    if {"wash", "washed"} & set(tokens):
        others = [c for c in matched if c not in ("blue", "denim")]
        if len(others) == 1:
            return others[0]  # "black wash", "washed black" stay black
        if not others:
            return "light blue" if "light" in tokens else "denim"
    if len(matched) == 1:
        return matched[0]
    if len(matched) >= 2:
        if "multicolor" in matched:
            return "multicolor"
        return COMPOUND_PAIRS.get(frozenset(matched), "multicolor") if len(matched) == 2 else "multicolor"
    return None


@lru_cache(maxsize=4096)
def _resolve(text: str) -> Optional[str]:
    if any(m in text for m in MULTI_WORDS) or re.search(r"(?:^|[\s\-])multi(?:$|[\s\-])", text):
        return "multicolor"
    if SEPARATORS.search(text):
        parts = [p.strip() for p in SEPARATORS.split(text) if p.strip()]
        if len(parts) >= 2:
            found = {r for p in parts if (r := _single(p))}
            if len(found) >= 2:
                return "multicolor"
            if len(found) == 1:
                return found.pop()
    return _single(text)


def normalize_color(text: Any) -> dict:
    """Free-text color -> {"name", "family", "hex"}. Unknown text keeps its own name, family "unknown"."""
    if not isinstance(text, str):
        return {"name": "", "family": "unknown", "hex": FALLBACK_HEX}
    trimmed = " ".join(text.strip().lower().split())
    if not trimmed:
        return {"name": "", "family": "unknown", "hex": FALLBACK_HEX}
    name = _resolve(trimmed)
    return _response(name) if name else {"name": trimmed, "family": "unknown", "hex": FALLBACK_HEX}


def same_color(a: Any, b: Any) -> bool:
    """True when both texts map to the same known color ("ivory" and "off white")."""
    name = normalize_color(a)["name"]
    return name in CANONICAL_COLORS and name == normalize_color(b)["name"]


def is_neutral(text: Any) -> bool:
    return normalize_color(text)["family"] == "neutral"


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


def _label_words(label: Any) -> set[str]:
    if not isinstance(label, str):
        return set()
    text = re.sub(r"\b(?:t-?shirts?|tees?)\b", "tshirt", label.lower())
    return {t for t in re.findall(r"[a-z0-9]+", text) if t not in LABEL_STOPWORDS and t not in _COLOR_WORDS}


def _kind(label: Any) -> Optional[int]:
    from .finder import item_type  # lazy: finder imports this module

    return item_type(label) if isinstance(label, str) else None


def find_duplicate(new_item: dict, closet: list[dict]) -> Optional[str]:
    """Id of a closet item that's very likely the same garment, else None.

    Same category, same normalized color, same pattern, same garment type (when both labels
    have one), and >= 60% of the shorter label's non-color words in common.
    """
    if not isinstance(new_item, dict) or not isinstance(closet, list):
        return None
    cat = _norm(new_item.get("category"))
    color = normalize_color(str(new_item.get("color") or ""))["name"]
    pattern = _norm(new_item.get("pattern")) or "solid"
    words = _label_words(new_item.get("label"))
    if not (cat and color and words):
        return None
    kind = _kind(new_item.get("label"))
    best, best_ratio = None, 0.0
    for item in closet:
        if not isinstance(item, dict) or not item.get("id") or item.get("id") == new_item.get("id"):
            continue
        if _norm(item.get("category")) != cat or (_norm(item.get("pattern")) or "solid") != pattern:
            continue
        if normalize_color(str(item.get("color") or ""))["name"] != color:
            continue
        other = _kind(item.get("label"))
        if kind is not None and other is not None and kind != other:
            continue
        theirs = _label_words(item.get("label"))
        if not theirs:
            continue
        ratio = len(words & theirs) / min(len(words), len(theirs))
        if ratio >= DUPLICATE_OVERLAP and ratio > best_ratio:
            best, best_ratio = str(item["id"]), ratio
    return best
