"""Photo onboarding: "put in a bunch of photos and it can see my style, my measurements, and recommend".

POST /onboarding/photos takes 1-8 photos + height (weight optional) and reuses the existing pieces:
  1. every photo is digitized (digitize.py) -> closet items, duplicates across the batch / closet skipped;
  2. the best photo is body-scanned (body_scan.py): every photo is scanned and the full-body ones averaged
     (more photos = better estimate); the first full-body photo becomes the try-on photo;
  3. the digitized garments are summarized into a style (rules; one optional AI sentence) and saved on
     the user the way POST /onboarding does (same text parser, so "tops under $40" in the hint works);
  4. the feed's reason bank is warmed in the background so Home is instant afterwards.
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from ..models import ClosetItem
from ..store import store
from . import prompts
from .colors import normalize_color
from .llm import CLAUDE_TAG_MODEL, ai_json, text_mock
from .style_profile import _formality

log = logging.getLogger(__name__)

MAX_PHOTOS = 8
MAX_SCAN_PHOTOS = 8  # every onboarding photo is scanned; the full-body ones are averaged
TOP_TAGS = 3
TOP_COLORS = 3
TOP_LABELS = 3
DISPLAY = {"y2k": "Y2K"}


# ---------- closet ----------

def digitize_batch(user_id: str, photos: list[tuple[str, Path | None]]) -> tuple[list[ClosetItem], int, int]:
    """Digitize every (url, local_path). Returns (items kept, duplicates skipped, photos whose tagging
    crashed). An item flagged `duplicate_of` (same garment earlier in this batch or already in the
    closet) is removed again, so the closet only grows by new garments. A photo with no clothing adds
    nothing and is not an error."""
    from .digitize import digitize

    kept: list[ClosetItem] = []
    skipped = failed = 0
    for url, path in photos:
        try:
            items = digitize(user_id, url, path)
        except Exception as e:  # noqa: BLE001 - one bad photo must not sink the batch
            log.warning("photo onboarding: digitize failed for %s: %s", url, e)
            failed += 1
            continue
        for item in items:
            if item.duplicate_of:
                store.delete("closet_items", item.id)
                skipped += 1
            else:
                kept.append(item)
    return kept, skipped, failed


# ---------- body ----------

def scan_best(photos: list[tuple[str, Path | None]], height_cm: float, weight_kg: float | None) -> tuple[dict, str | None, int]:
    """Body-scan every photo (cheapest first, at most MAX_SCAN_PHOTOS) and average the full-body ones
    (body_scan.scan_many). Returns (profile, url of the first full-body photo or None, photos that weren't
    full-body). Without a full-body photo the profile is the height/weight formula estimate with a note
    saying so."""
    from .body_scan import scan_many

    def size(p: tuple[str, Path | None]) -> int:
        try:
            return p[1].stat().st_size if p[1] else 1 << 40
        except OSError:
            return 1 << 40

    ordered = [url for url, _ in sorted(photos, key=size)[:MAX_SCAN_PHOTOS]]
    profile, body_url, skipped = scan_many(ordered, height_cm, weight_kg)
    if body_url is None:
        profile["full_body"] = False
        profile["note"] = profile.get("note") or "Add a full-body photo, head to feet, for a better scan"
    return profile, body_url, skipped


# ---------- style ----------

def _display(tag: str) -> str:
    return DISPLAY.get(tag, tag)


def style_summary(items: list[dict]) -> dict:
    """Style from digitized garments, rules only: {style_tags, colors, formality, style_text}.
    style_text reads like "streetwear and minimalist; black cargo pants, white baby tee; mostly casual"."""
    tags = Counter(t for it in items for t in (it.get("style_tags") or []) if isinstance(t, str))
    colors: Counter = Counter()
    for it in items:
        c = normalize_color(it.get("color") or "")
        if c["family"] != "unknown":
            colors[c["name"]] += 1
    top_tags = [t for t, _ in tags.most_common(TOP_TAGS)]
    top_colors = [c for c, _ in colors.most_common(TOP_COLORS)]
    formality = _formality([(it, 1.0) for it in items])["label"]
    labels: list[str] = []
    seen_cat: set[str] = set()
    for it in items:  # one label per category first, so the sentence covers the outfit
        label = " ".join(str(it.get("label") or "").split())
        if label and it.get("category") not in seen_cat:
            labels.append(label)
            seen_cat.add(it.get("category"))
    for it in items:
        label = " ".join(str(it.get("label") or "").split())
        if label and label not in labels:
            labels.append(label)
    labels = labels[:TOP_LABELS]
    parts = []
    if top_tags:
        parts.append(" and ".join(_display(t) for t in top_tags[:2]))
    if labels:
        parts.append(", ".join(labels))
    if formality != "unknown":
        parts.append(f"mostly {formality}")
    return {"style_tags": top_tags, "colors": top_colors, "formality": formality, "style_text": "; ".join(parts)}


def _ai_style_text(items: list[dict], rules: dict) -> str | None:
    """One sentence from the model when AI is on; None (use the rules) otherwise or on any problem."""
    if text_mock() or not items:
        return None
    slim = [{"label": it.get("label"), "category": it.get("category"), "color": it.get("color"),
             "style_tags": it.get("style_tags"), "formality": it.get("formality")} for it in items[:24]]
    try:
        import json

        raw = ai_json(prompts.STYLE_FROM_CLOSET.format(items_json=json.dumps(slim)), max_tokens=120,
                      model=CLAUDE_TAG_MODEL)
    except Exception as e:  # noqa: BLE001
        log.warning("style summary AI unavailable, using rules: %s", e)
        return None
    text = raw.get("style_text") if isinstance(raw, dict) else None
    if not isinstance(text, str):
        return None
    text = " ".join(text.replace('"', "").split()).rstrip(" .")
    return text if 8 <= len(text) <= 160 else None


def infer_style(items: list[dict], style_hint: str | None = None) -> dict:
    """Rules summary, AI sentence when available, hint (what the user typed) first."""
    out = style_summary(items)
    ai_text = _ai_style_text(items, out)
    if ai_text:
        out["style_text"] = ai_text
    hint = " ".join((style_hint or "").split())
    if hint:
        out["style_text"] = f"{hint}; {out['style_text']}" if out["style_text"] else hint
    return out


def save_style(user_id: str, style: dict) -> dict:
    """Save style_text / style_tags on the user the way POST /onboarding does (same parser, budgets in
    the hint merge into price_ranges) and mark the user onboarded. shop_for / preferred_stores untouched."""
    from ..commerce.users import DEMO_FRIENDS, _save, parse_prefs

    parsed = parse_prefs(style["style_text"])
    user = store.get("users", user_id) or {
        "id": user_id, "display_name": user_id,
        "friends": [f for f in DEMO_FRIENDS if f != user_id and store.get("users", f)]}
    tags = list(dict.fromkeys([*parsed["styles"], *style["style_tags"]]))
    user = {**user, "style_text": style["style_text"], "style_tags": tags,
            "price_ranges": {**(user.get("price_ranges") or {}), **parsed["budgets"]}, "onboarded": True}
    style["style_tags"] = tags
    return _save(user)


def warm_feed(user_id: str) -> None:
    """Fill the reason bank for this user off the request thread (service._spawn), so the first /feed
    after onboarding answers from the bank instead of waiting on Claude."""
    from . import service

    def run():
        try:
            service.pair(user_id, [])
        except Exception as e:  # noqa: BLE001
            log.warning("feed warm-up failed: %s", e)

    service._spawn(run)
