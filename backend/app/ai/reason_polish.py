"""Pure-rules one-line feed reason normalizer for dresstoimpress."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_MAX_WORDS = 12
MIN_WORDS_AFTER_DROP = 3

QUOTE_CHARS = "\"'“”‘’`"
TRAILING_PUNCT_CHARS = ".!,;:…-–—"
WORD_EDGE_PUNCT = QUOTE_CHARS + TRAILING_PUNCT_CHARS + "()[]{}"

DANGLING_WORDS = frozenset({
    "a", "an", "the", "your", "my", "with", "and", "or", "but", "for",
    "to", "of", "over", "on", "in", "at", "by", "from", "that", "this",
    "into", "as", "so", "its", "it's",
})

_WS_RE = re.compile(r"\s+")
_PREFIX_RE = re.compile(r"^reason\s*[:\-–—]\s*", re.IGNORECASE)
_TRAILING_PUNCT_RE = re.compile(r"[.!,;:…\-–—\s]+$")
_DOUBLED_WORD_RE = re.compile(r"\b([A-Za-z0-9']+)(\s+\1\b)+", re.IGNORECASE)
_Y2K_RE = re.compile(r"\by2k\b", re.IGNORECASE)
_TSHIRT_RE = re.compile(r"\bt-?shirt\b", re.IGNORECASE)
_AMPERSAND_RE = re.compile(r"(?:^|(?<=\s))&(?=\s|$)")


def _strip_quotes(text: str) -> str:
    """Strip matching or unmatched quote characters from both ends repeatedly."""
    while text and (text[0] in QUOTE_CHARS or text[-1] in QUOTE_CHARS):
        text = text.strip(QUOTE_CHARS).strip()
    return text


def _strip_trailing_punct(text: str) -> str:
    """Strip trailing punctuation runs while preserving % and $ amounts."""
    return _TRAILING_PUNCT_RE.sub("", text).strip()


def polish_reason(text: Any, max_words: int = DEFAULT_MAX_WORDS) -> str:
    """Clean and normalize a single feed card reason string."""
    if not isinstance(text, str):
        return ""
    if not isinstance(max_words, int) or isinstance(max_words, bool) or max_words < 1:
        max_words = DEFAULT_MAX_WORDS

    cleaned = _WS_RE.sub(" ", text).strip()
    cleaned = _strip_quotes(cleaned)
    cleaned = _PREFIX_RE.sub("", cleaned).strip()
    cleaned = _strip_quotes(cleaned)
    cleaned = _strip_trailing_punct(cleaned)
    cleaned = _DOUBLED_WORD_RE.sub(r"\1", cleaned)

    cleaned = _Y2K_RE.sub("Y2K", cleaned)
    cleaned = _TSHIRT_RE.sub("tee", cleaned)
    cleaned = _AMPERSAND_RE.sub("and", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()

    words = cleaned.split()
    if len(words) > max_words:
        capped = words[:max_words]
        trimmed = list(capped)
        while trimmed and trimmed[-1].lower().strip(WORD_EDGE_PUNCT) in DANGLING_WORDS:
            trimmed.pop()
        words = trimmed if len(trimmed) >= MIN_WORDS_AFTER_DROP else capped
        cleaned = _strip_trailing_punct(" ".join(words))
    else:
        cleaned = " ".join(words)

    if not cleaned:
        return ""
    if cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def polish_page(reasons: Any, max_words: int = DEFAULT_MAX_WORDS) -> list[str]:
    """Polish a list of feed reasons, returning an empty list for non-list inputs."""
    if not isinstance(reasons, list):
        return []
    return [polish_reason(item, max_words=max_words) for item in reasons]


if __name__ == "__main__":
    cases: list[tuple[Any, Any]] = [
        (
            polish_reason('  "goes with your black cargo pants."  '),
            "Goes with your black cargo pants",
        ),
        (
            polish_reason("reason: y2k tee that pairs with your your baggy jeans!"),
            "Y2K tee that pairs with your baggy jeans",
        ),
        (
            polish_reason(
                "Oversized NASCAR tee pushes your baggy jeans into full Y2K energy for weekends with your",
                max_words=12,
            ),
            "Oversized NASCAR tee pushes your baggy jeans into full Y2K energy",
        ),
        (
            polish_reason("only $13 & it works with your jeans..."),
            "Only $13 and it works with your jeans",
        ),
        (polish_reason(None), ""),
        (polish_reason("   "), ""),
        (
            polish_page(["goes with your tee.", 5, None]),
            ["Goes with your tee", "", ""],
        ),
    ]
    for actual, expected in cases:
        mark = "✓" if actual == expected else "✗"
        print(f"{mark} {actual!r} (expected {expected!r})")
