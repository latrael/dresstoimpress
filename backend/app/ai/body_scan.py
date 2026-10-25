"""Body scan: one full-body photo + height -> estimated measurements for size advice.

The vision model reads proportions (shoulders, chest, waist, hips, leg length) against the stated height.
Every number is an estimate, kept only inside human ranges. Anything missing, out of range, or from a
photo that isn't one standing person in full view falls back to the height/weight formulas the size
advisor already uses, and `source` says which ("ai" or "estimate"). The same photo becomes the try-on photo.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from . import prompts
from .llm import CLAUDE_TAG_MODEL, ai_json, text_mock
from .sizing import _estimate_inseam_inches, _estimate_waist_inches

log = logging.getLogger(__name__)

BUILDS = {"slim", "average", "athletic", "curvy", "broad"}
PRESENTING = {"men", "women"}  # store department the look points to; "unknown" when the model isn't sure
RANGES = {"chest_in": (26.0, 60.0), "waist_in": (22.0, 56.0), "hip_in": (28.0, 62.0), "inseam_in": (24.0, 38.0)}
HEIGHT_CM = (120.0, 230.0)
WEIGHT_KG = (30.0, 250.0)


def _num(v, lo: float, hi: float) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x * 2) / 2 if lo <= x <= hi else None


def _note(v) -> str:
    """At most 10 words, no trailing period, first letter capitalized."""
    text = " ".join(str(v or "").replace('"', "").split()[:10]).rstrip(" .!,;:")
    return text[:1].upper() + text[1:]


def formula(height_cm: float, weight_kg: float | None) -> dict:
    """What the size advisor would assume without a scan."""
    out = {"inseam_in": round(_estimate_inseam_inches(height_cm) * 2) / 2}
    if weight_kg:
        out["waist_in"] = round(_estimate_waist_inches(height_cm, weight_kg) * 2) / 2
    return out


def _ask(photo_url: str, height_cm: float, weight_kg: float | None) -> dict:
    if text_mock():
        return {}
    weight_part = f" and weighs about {round(weight_kg)} kg" if weight_kg else ""
    try:
        raw = ai_json(prompts.BODY_SCAN.format(height_cm=round(height_cm), weight_part=weight_part),
                      image_url=photo_url, max_tokens=300, model=CLAUDE_TAG_MODEL)
    except Exception as e:  # noqa: BLE001 - provider down or bad JSON: the formula still gives a profile
        log.warning("body scan AI unavailable, using the formula: %s", e)
        return {}
    return raw if isinstance(raw, dict) else {}


CM_FIELDS = {"waist_cm": "waist_in", "chest_cm": "chest_in", "hip_cm": "hip_in", "inseam_cm": "inseam_in"}


def apply_manual(profile: dict | None, changes: dict) -> dict:
    """Merge typed measurements into a body profile. cm lengths are stored in inches; a None value
    clears that field. Fields the user typed are listed in `manual`, and a later scan keeps them."""
    out = dict(profile or {})
    manual = set(out.get("manual") or [])
    for key, value in changes.items():
        field = CM_FIELDS.get(key, key)
        if key in CM_FIELDS and value is not None:
            value = round(value / 2.54 * 2) / 2
        out[field] = value
        if value is None:
            manual.discard(field)
        else:
            manual.add(field)
    out["manual"] = sorted(manual)
    if manual & {"height_cm", "weight_kg", *CM_FIELDS.values()}:
        out["source"] = "manual"
    out.setdefault("source", "manual")
    out["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return out


def merge_scan(previous: dict | None, scanned: dict) -> dict:
    """A new scan replaces the estimates but keeps what the user typed (and their preferences)."""
    prev = previous or {}
    out = {**prev, **scanned}
    for field in prev.get("manual") or []:
        out[field] = prev.get(field)
    out["manual"] = list(prev.get("manual") or [])
    return out


def scan(photo_url: str, height_cm: float, weight_kg: float | None = None) -> dict:
    """Body profile saved on the user as `body_profile` (inches; estimates)."""
    raw = _ask(photo_url, height_cm, weight_kg)
    full = bool(raw) and raw.get("full_body_visible") is not False
    ai = {k: _num(raw.get(k), *RANGES[k]) for k in RANGES} if full else {}
    base = formula(height_cm, weight_kg)
    profile: dict = {"height_cm": round(height_cm, 1), "weight_kg": round(weight_kg, 1) if weight_kg else None}
    for k in RANGES:
        profile[k] = ai.get(k) if ai.get(k) is not None else base.get(k)
    build = str(raw.get("build") or "").lower() if full else ""
    profile["build"] = build if build in BUILDS else None
    presenting = str(raw.get("presenting") or "").lower() if full else ""
    profile["presenting"] = presenting if presenting in PRESENTING else "unknown"
    profile["source"] = "ai" if any(v is not None for v in ai.values()) else "estimate"
    profile["full_body"] = None if not raw else full
    profile["note"] = _note(raw.get("note")) if full else ""
    if raw and not full:
        profile["note"] = "Use a full-body photo, head to feet, for a better scan"
    profile["scanned_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return profile


def confidence(scan_photos: int) -> str:
    """How much to trust the estimate: 1 full-body photo low, 2 medium, 3+ high; 0 (formula) low."""
    return "high" if scan_photos >= 3 else "medium" if scan_photos == 2 else "low"


def scan_many(photo_urls: list[str], height_cm: float, weight_kg: float | None = None) -> tuple[dict, str | None, int]:
    """Body scan over several photos: every photo is scanned, the full-body ones are averaged (numbers to
    the nearest 0.5 in; majority vote for build / presenting). Returns (profile, url of the first full-body
    photo or None, photos skipped because they weren't full-body). profile.scan_photos = number of
    full-body photos used, profile.confidence by that count. With no full-body photo the profile is the
    formula estimate from the first photo's scan (scan_photos 0, confidence low)."""
    results = [(url, scan(url, height_cm, weight_kg)) for url in photo_urls]
    full = [(url, p) for url, p in results if p.get("full_body")]
    skipped = len(results) - len(full)
    if not full:
        profile = dict(results[0][1]) if results else {
            "height_cm": round(height_cm, 1), "weight_kg": round(weight_kg, 1) if weight_kg else None,
            **formula(height_cm, weight_kg), "build": None, "presenting": "unknown", "source": "estimate",
            "full_body": None, "note": "", "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        profile["scan_photos"] = 0
        profile["confidence"] = confidence(0)
        return profile, None, skipped
    profile = dict(full[0][1])
    for k in RANGES:
        vals = [p[k] for _, p in full if p.get(k) is not None]
        profile[k] = round(sum(vals) / len(vals) * 2) / 2 if vals else profile.get(k)
    for key in ("build", "presenting"):
        votes = Counter(p.get(key) for _, p in full if p.get(key) not in (None, "unknown"))
        profile[key] = votes.most_common(1)[0][0] if votes else profile.get(key)
    profile["scan_photos"] = len(full)
    profile["confidence"] = confidence(len(full))
    return profile, full[0][0], skipped
