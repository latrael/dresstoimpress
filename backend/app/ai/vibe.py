"""Vibe search: a shopper's sentence -> catalog filters for Discover.

    "fit for a rooftop party" -> {"styles": ["streetwear", "minimalist"], "categories": [], "colors": ["black"],
                                  "keywords": ["satin shirt", ...], "source": "ai"}

Nabil's GET /search?q= calls it in-process: `from app.ai.vibe import vibe; filters = vibe(q)`.
Claude (cached per normalized query) with a keyword-rules fallback (mock mode, AI down, empty answer).
"""
from __future__ import annotations

import hashlib
import logging
import re

from ..store import store
from . import prompts
from .llm import CLAUDE_TAG_MODEL, ai_json, text_mock

log = logging.getLogger(__name__)

STYLES = ["y2k", "streetwear", "minimalist", "preppy", "athleisure", "vintage", "business", "boho", "grunge",
          "classic"]
CATEGORIES = ["top", "bottom", "outerwear", "shoes", "dress", "accessory"]

# Rules fallback: words in the query -> style / category / colors.
STYLE_WORDS = {
    "y2k": ["y2k", "2000s", "baby tee", "low rise", "butterfly"],
    "streetwear": ["street", "streetwear", "skate", "hype", "baggy", "cargo", "hoodie", "concert", "festival"],
    "minimalist": ["minimal", "clean", "simple", "neutral", "capsule", "quiet luxury"],
    "preppy": ["preppy", "polo", "country club", "campus", "brunch", "tennis"],
    "athleisure": ["gym", "athleisure", "workout", "yoga", "run", "sporty", "lounge", "comfy"],
    "vintage": ["vintage", "retro", "thrift", "70s", "80s", "90s"],
    "business": ["office", "work", "business", "interview", "meeting", "formal", "professional"],
    "boho": ["boho", "beach", "summer", "flowy", "linen", "picnic", "vacation"],
    "grunge": ["grunge", "punk", "rock", "edgy", "flannel"],
    "classic": ["classic", "timeless", "date", "dinner", "wedding", "party", "rooftop", "smart casual"],
}
CATEGORY_WORDS = {
    "top": ["top", "tee", "t-shirt", "shirt", "blouse", "sweater", "hoodie", "polo", "tank", "cardigan"],
    "bottom": ["jeans", "pants", "trousers", "shorts", "skirt", "cargo", "joggers", "chinos"],
    "outerwear": ["jacket", "coat", "puffer", "blazer", "vest", "parka", "fleece", "windbreaker"],
    "shoes": ["shoes", "sneakers", "boots", "loafers", "heels", "sandals", "trainers"],
    "dress": ["dress", "gown", "jumpsuit"],
    "accessory": ["bag", "hat", "cap", "belt", "scarf", "jewelry", "necklace", "watch", "sunglasses"],
}
COLOR_WORDS = ["black", "white", "grey", "gray", "navy", "blue", "red", "green", "olive", "beige", "brown", "cream",
               "pink", "purple", "yellow", "orange", "khaki", "denim"]
OCCASION_COLORS = {"party": ["black"], "rooftop": ["black"], "wedding": ["navy", "beige"], "beach": ["white"],
                   "summer": ["white", "beige"], "winter": ["black", "grey"], "office": ["navy", "grey"],
                   "interview": ["navy", "black"], "funeral": ["black"], "grunge": ["black"]}


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


def _has(text: str, word: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text) is not None


def rules(q: str) -> dict:
    """Keyword rules only: free and instant. Same shape as vibe()."""
    t = _norm(q)
    styles = [s for s, words in STYLE_WORDS.items() if any(_has(t, w) for w in words)][:3]
    cats = [c for c, words in CATEGORY_WORDS.items() if any(_has(t, w) for w in words)][:3]
    colors = [c for c in COLOR_WORDS if _has(t, c)]
    for word, extra in OCCASION_COLORS.items():
        if _has(t, word):
            colors += [c for c in extra if c not in colors]
    item_words = [w for words in CATEGORY_WORDS.values() for w in words if _has(t, w)]
    return {"styles": styles, "categories": cats, "colors": colors[:4], "keywords": item_words[:5],
            "source": "rules"}


def _clean(raw) -> dict | None:
    """The model's answer limited to our vocabularies; None if it's unusable or empty."""
    if not isinstance(raw, dict):
        return None

    def words(key: str, n: int, allowed: list[str] | None = None) -> list[str]:
        vals = raw.get(key) if isinstance(raw.get(key), list) else []
        out = [str(v).strip().lower() for v in vals if str(v).strip()]
        if allowed is not None:
            out = [v for v in out if v in allowed]
        return list(dict.fromkeys(out))[:n]

    out = {"styles": words("styles", 3, STYLES), "categories": words("categories", 3, CATEGORIES),
           "colors": words("colors", 4), "keywords": [" ".join(k.split()[:4]) for k in words("keywords", 5)],
           "source": "ai"}
    if not (out["styles"] or out["categories"] or out["colors"] or out["keywords"]):
        return None
    return out


def vibe(q: str) -> dict:
    """{"styles", "categories", "colors", "keywords", "source": "ai" | "rules"} for a Discover search.
    Never raises: the rules answer is used when the AI is off, down, or says nothing useful."""
    q = _norm(q)[:200]
    if not q or text_mock():
        return rules(q)
    key = f"vibe{prompts.VIBE_VERSION}-" + hashlib.sha256(q.encode()).hexdigest()[:24]
    hit = store.get("tag_cache", key)
    if hit and isinstance(hit.get("vibe"), dict):
        return hit["vibe"]
    try:
        out = _clean(ai_json(prompts.VIBE.format(q=q.replace('"', "'")), max_tokens=300, model=CLAUDE_TAG_MODEL))
    except Exception as e:  # noqa: BLE001 — budget, network, bad JSON: rules instead
        log.warning("vibe search fell back to rules: %s", e)
        out = None
    if out is None:
        return rules(q)
    store.put("tag_cache", key, {"vibe": out})
    return out
