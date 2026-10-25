"""Season / layer warmth, shared by the try-on source-photo picker and the fit creator.

0 = light (shorts, tees, sandals), 1 = mid, 2 = heavy (coats, knits, boots). Shorts never go under a trench coat.
"""
from __future__ import annotations

import re

LIGHT, MID, HEAVY = 0, 1, 2

_LIGHT = ("shorts", "short-sleeve", "short sleeve", "tank", "tee", "t-shirt", "tshirt", "linen", "sandal", "flip-flop",
          "slide", "swim", "crop", "sleeveless", "camisole", "polo", "skirt", "mini")
_HEAVY = ("coat", "trench", "overcoat", "puffer", "parka", "wool", "boot", "sweater", "hoodie", "fleece", "knit",
          "cardigan", "turtleneck", "scarf", "beanie", "thermal", "shearling", "down")


def warmth(text: str | None, category: str | None = None) -> int:
    """0 light / 1 mid / 2 heavy, from the label or product name (+ tags) and the category."""
    t = (text or "").lower()
    if any(w in t for w in _HEAVY):
        return HEAVY
    if any(w in t for w in _LIGHT):
        return LIGHT
    return HEAVY if category == "outerwear" else MID


def product_warmth(prod: dict) -> int:
    text = " ".join([str(prod.get("name") or prod.get("label") or ""), *map(str, prod.get("style_tags") or [])])
    return warmth(text, prod.get("category"))


def piece_warmth(piece: dict) -> int:
    return warmth(piece.get("label"), piece.get("category"))


_EXPOSED = ("tank", "sleeveless", "camisole", "crop", "swim", "sandal", "flip-flop", "slide")


def exposed_light(piece: dict) -> bool:
    """A light piece that can't sit under a coat: shorts, skirts, sandals, tanks. A tee under a coat is fine."""
    if piece_warmth(piece) != LIGHT:
        return False
    cat = piece.get("category") or piece.get("slot")
    if cat in ("bottom", "shoes"):
        return True
    return any(w in (piece.get("label") or "").lower() for w in _EXPOSED)


def coherent(pieces: list[dict]) -> bool:
    """A fit is season-coherent when no heavy piece (overcoat, boots, knit) shares it with an exposed light one
    (shorts, sandals, tank): shorts never go under a trench coat."""
    return not (any(piece_warmth(p) == HEAVY for p in pieces) and any(exposed_light(p) for p in pieces))


# ---------- the occasion text → season ----------

_COLD = ("cold", "chilly", "freez", "snow", "winter", "sleet", "frost", "icy", "windy", "rain", "storm", "fog",
         "night hike", "ski", "december", "january", "february", "november")
_HOT = ("hot", "heat", "warm day", "sunny", "beach", "pool", "summer", "humid", "scorch", "july", "august", "june",
        "swim", "bbq", "picnic")
_LABELS = {LIGHT: "light", MID: "mid", HEAVY: "heavy"}


def _temps(text: str) -> list[float]:
    """Temperatures mentioned, in °F. "55°F", "55F", "55 degrees", "12°C", "12C"."""
    out = []
    for m in re.finditer(r"(-?\d{1,3})\s*(?:°|º|deg(?:rees)?)?\s*([cf])\b", text):
        v, unit = float(m.group(1)), m.group(2)
        out.append(v * 9 / 5 + 32 if unit == "c" else v)
    for m in re.finditer(r"(-?\d{1,3})\s*(?:°|º|degrees)(?![cf])", text):
        out.append(float(m.group(1)))
    return out


def occasion_season(occasion: str | None) -> int:
    """light / mid / heavy for free-text like "date night in SF, 55°F, walking a lot". Numbers win over words."""
    t = (occasion or "").lower()
    temps = _temps(t)
    if temps:
        f = min(temps)
        return HEAVY if f < 55 else LIGHT if f >= 75 else MID
    if any(w in t for w in _COLD):
        return HEAVY
    if any(w in t for w in _HOT):
        return LIGHT
    return MID


def season_label(season: int) -> str:
    return _LABELS.get(season, "mid")


def fits_season(pieces: list[dict], season: int) -> bool:
    """heavy occasion → no light pieces (shorts); light occasion → no heavy outerwear (coats)."""
    if season == HEAVY and any(exposed_light(p) for p in pieces):
        return False
    if season == LIGHT and any(piece_warmth(p) == HEAVY for p in pieces):
        return False
    return True
