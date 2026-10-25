"""Closet v2: a real wardrobe. Every photo (one piece or a whole outfit) becomes standalone pieces.

Per garment: crop by its box -> dedupe against the closet (a hit MERGES: the outfit photo is added to that
item's `worn_in` instead of making a twin) -> brand read off the photo -> catalog match (same matcher
shop_fit uses; confident hits set product_id / catalog_image_url / match_confidence) -> display image:
catalog photo when matched, else a generated clean product shot of the crop (Gemini), else the crop.

Entry points: add_photos() for POST /closet/upload, add_from_fit() after a Fit Check post (best effort,
off the request thread via add_from_fit_later), reshoot() and edit() for the item routes.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..models import ClosetItem
from ..store import DATA_DIR, store
from . import digitize as dig
from . import service
from .colors import find_duplicate
from .compat import get_product, list_products
from .finder import match_score
from .llm import BadModelOutput, gemini_image, mock_mode

log = logging.getLogger(__name__)

CATEGORIES = {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}
PATTERNS = {"solid", "striped", "plaid", "graphic", "floral", "other"}
KINDS = {"piece", "outfit"}
MAX_PHOTOS = 8
# finder.match_score: type word 2.0 + color 1.0 + a descriptor 0.5 = a confident "this exact item".
CONFIDENT_SCORE = 3.5
SCORE_CEILING = 5.0
CLEAN_SHOT = ("Product photo of only this garment, centered, plain white background, flat-lay or "
              "ghost-mannequin style, no person, no text")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public_url(name: str) -> str:
    base = os.getenv("PUBLIC_BASE", "http://localhost:8000").rstrip("/")
    return f"{base}/static/uploads/{name}"


def _brand(raw: dict) -> str | None:
    b = raw.get("brand")
    if not isinstance(b, str):
        return None
    b = " ".join(b.split())[:40]
    return b if b and b.lower() not in {"null", "none", "unknown", "n/a"} else None


# ---------- catalog match ----------

def catalog_match(item: dict) -> tuple[dict, float] | None:
    """The catalog product this piece most likely IS, with a 0-1 confidence; None below the bar."""
    tag = {"label": item.get("label"), "category": item.get("category"), "color": item.get("color")}
    best, best_score = None, 0.0
    for p in list_products():
        s = match_score(tag, p)
        if s > best_score:
            best, best_score = p, s
    if best is None or best_score < CONFIDENT_SCORE:
        return None
    return best, round(min(1.0, best_score / SCORE_CEILING), 3)


def _apply_match(item: ClosetItem) -> None:
    hit = catalog_match(item.model_dump())
    if not hit:
        return
    product, conf = hit
    item.product_id = product["id"]
    item.catalog_image_url = product.get("image_url")
    item.match_confidence = conf
    if not item.brand and product.get("brand"):
        item.brand = product["brand"]


# ---------- clean shot ----------

def clean_shots_on() -> bool:
    return os.getenv("CLOSET_CLEAN_SHOTS", "1") != "0" and not mock_mode("GEMINI_API_KEY")


def clean_shot(source_url: str) -> str | None:
    """Generated product photo of just this garment (from its crop). None when image AI is off or fails."""
    if not clean_shots_on():
        return None
    try:
        img = gemini_image(CLEAN_SHOT, [source_url])
    except BadModelOutput as e:
        log.warning("clean shot skipped: %s", e)
        return None
    except Exception as e:  # noqa: BLE001 - never let a nicety break an upload
        log.warning("clean shot failed: %s", e)
        return None
    if not img:
        return None
    name = f"{uuid.uuid4().hex}-clean.png"
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads" / name).write_bytes(img)
    return _public_url(name)


def _set_display(item: ClosetItem) -> None:
    """display_image_url: catalog photo > generated clean shot of the crop > the crop. image_url mirrors it."""
    if item.catalog_image_url:
        item.display_image_url = item.catalog_image_url
    else:
        item.display_image_url = clean_shot(item.crop_image_url) or item.crop_image_url
    item.image_url = item.display_image_url


# ---------- one garment ----------

def _tag_to_item(user_id: str, raw: dict, photo_url: str) -> ClosetItem:
    try:
        formality = min(5, max(1, int(raw.get("formality", 3))))
    except (TypeError, ValueError):
        formality = 3
    return ClosetItem(
        id=f"ci_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        image_url=photo_url,
        category=raw.get("category") if raw.get("category") in CATEGORIES else "top",
        color=str(raw.get("color") or "unknown"),
        pattern=raw.get("pattern") if raw.get("pattern") in PATTERNS else "other",
        style_tags=service._style_tags(raw, 5),
        formality=formality,
        source="photo",
        label=" ".join(str(raw.get("label", "")).split()[:5]),
        brand=_brand(raw),
    )


def _wear(item: dict, photo_url: str, source: str) -> dict:
    # items from before closet v2 have only image_url: that picture is both their crop and their display
    item.setdefault("crop_image_url", None)
    item["crop_image_url"] = item["crop_image_url"] or item.get("image_url")
    item["display_image_url"] = item.get("display_image_url") or item.get("image_url")
    worn = [w for w in item.get("worn_in") or [] if isinstance(w, dict)]
    if not any(w.get("photo_url") == photo_url for w in worn):
        worn.append({"photo_url": photo_url, "at": _now(), "source": source})
    item["worn_in"] = worn
    return item


def add_garment(user_id: str, raw: dict, photo_url: str, local_path: Path | None, source: str,
                existing: list[dict], crop_box=None) -> tuple[dict, bool]:
    """One detected garment -> (closet item dict, merged). merged=True means an item the user already
    had matched; that item got this photo in `worn_in` and nothing new was created."""
    draft = _tag_to_item(user_id, raw, photo_url)
    dup = find_duplicate(draft.model_dump(), existing)
    if dup:
        # the dict in `existing` (so an item added earlier in this same upload shows its new wear too)
        hit = next((e for e in existing if e.get("id") == dup), None) or store.get("closet_items", dup)
        if hit:
            _wear(hit, photo_url, source)
            if not hit.get("brand") and draft.brand:
                hit["brand"] = draft.brand
            store.put("closet_items", hit["id"], hit)
            return hit, True
    # the crop is the piece's own picture; without a usable box the whole photo stands in for it
    draft.crop_image_url = (dig.save_crop(local_path, crop_box) if crop_box is not None else None) or photo_url
    draft.worn_in = [{"photo_url": photo_url, "at": _now(), "source": source}]
    _apply_match(draft)
    _set_display(draft)
    doc = draft.model_dump()
    store.put("closet_items", draft.id, doc)
    return doc, False


# ---------- whole photos ----------

def add_photo(user_id: str, photo_url: str, local_path: Path | None, kind: str, source: str = "closet") -> dict:
    """One photo -> {"added": [...], "merged": [...], "skipped": int}.
    kind "piece": the photo is one garment (tagger). kind "outfit": every garment with its box (digitize)."""
    if kind == "piece":
        try:
            found = [service.tag_image(photo_url)]
        except service.NotClothing:
            return {"added": [], "merged": [], "skipped": 1}
        boxes = [None]
    else:
        try:
            found = dig.detect(photo_url)[:dig.MAX_ITEMS]
        except BadModelOutput:
            found = []
        if not found:  # nothing boxed: treat the photo as one piece rather than losing it
            try:
                found = [service.tag_image(photo_url)]
            except service.NotClothing:
                return {"added": [], "merged": [], "skipped": 1}
        boxes = [d.get("box") for d in found]
    existing = store.list("closet_items", user_id=user_id)
    out = {"added": [], "merged": [], "skipped": 0}
    for raw, box in zip(found, boxes):
        if not isinstance(raw, dict) or not raw.get("label"):
            out["skipped"] += 1
            continue
        item, merged = add_garment(user_id, raw, photo_url, local_path, source, existing, crop_box=box)
        if merged:
            if not any(m["id"] == item["id"] for m in out["merged"]):
                out["merged"].append(item)
        else:
            out["added"].append(item)
            existing.append(item)
    return out


def add_photos(user_id: str, photos: list[tuple[str, Path | None]], kind: str) -> dict:
    """Several photos (url, local path) with one intent -> one combined {added, merged, skipped}."""
    out = {"added": [], "merged": [], "skipped": 0}
    for url, path in photos[:MAX_PHOTOS]:
        r = add_photo(user_id, url, path, kind)
        out["added"] += r["added"]
        out["skipped"] += r["skipped"]
        for m in r["merged"]:
            if not any(x["id"] == m["id"] for x in out["merged"]) and not any(a["id"] == m["id"] for a in out["added"]):
                out["merged"].append(m)
    # a later photo may have added a wear to an item an earlier photo created: report the saved state
    out["added"] = [store.get("closet_items", a["id"]) or a for a in out["added"]]
    return out


# ---------- Fit Check hook ----------

def add_from_fit(user_id: str, photo_url: str, local_path: Path | None, tags: list[dict]) -> dict:
    """Pieces of a posted Fit Check -> the poster's closet (worn_in source "fitcheck"). Uses the post's
    tags (already from tag_fit) so no extra AI call; crops by box when the tag has one."""
    existing = store.list("closet_items", user_id=user_id)
    out = {"added": [], "merged": [], "skipped": 0}
    for t in tags or []:
        if not isinstance(t, dict) or not t.get("label"):
            out["skipped"] += 1
            continue
        raw = {**t, "style_tags": t.get("style_tags") or []}
        item, merged = add_garment(user_id, raw, photo_url, local_path, "fitcheck", existing, crop_box=t.get("box"))
        (out["merged"] if merged else out["added"]).append(item)
        if not merged:
            existing.append(item)
    return out


def add_from_fit_later(user_id: str, photo_url: str, tags: list[dict]) -> None:
    """Best effort, off the request thread: a post never waits for or fails because of the closet."""
    from ..static_urls import local_static_path

    def run():
        try:
            add_from_fit(user_id, photo_url, local_static_path(photo_url, DATA_DIR), tags)
        except Exception as e:  # noqa: BLE001
            log.warning("closet add from fit check failed: %s", e)

    try:
        service._spawn(run)
    except Exception as e:  # noqa: BLE001
        log.warning("closet add from fit check not started: %s", e)


# ---------- item routes ----------

EDITABLE = {"label", "brand", "category", "color", "product_id"}


def reshoot(item: dict) -> dict:
    """Regenerate the clean shot (or re-point at the catalog image when matched)."""
    ci = ClosetItem(**item)
    ci.crop_image_url = ci.crop_image_url or ci.image_url
    _set_display(ci)
    doc = ci.model_dump()
    store.put("closet_items", ci.id, doc)
    return doc


def edit(item: dict, patch: dict) -> dict:
    """Apply {label?, brand?, category?, color?, product_id?}. product_id null clears the catalog match
    and reverts the display image to the clean shot / crop. Raises ValueError on a bad value."""
    redisplay = False
    for k, v in patch.items():
        if k not in EDITABLE:
            continue
        if k == "product_id":
            redisplay = True
            if v is None:
                item["product_id"] = item["catalog_image_url"] = item["match_confidence"] = None
                continue
            p = get_product(str(v))
            if not p:
                raise ValueError(f"unknown product {v}")
            item["product_id"], item["catalog_image_url"], item["match_confidence"] = p["id"], p.get("image_url"), 1.0
            if not item.get("brand") and p.get("brand"):
                item["brand"] = p["brand"]
            continue
        if k == "category" and v not in CATEGORIES:
            raise ValueError("category must be one of " + ", ".join(sorted(CATEGORIES)))
        if k == "category" or k == "color":
            if v is None:
                raise ValueError(f"{k} can't be null")
            item[k] = " ".join(str(v).split())[:60] or item[k]
        else:
            item[k] = (" ".join(str(v).split())[:60] or None) if v is not None else None
    ci = ClosetItem(**item)
    if redisplay:
        ci.crop_image_url = ci.crop_image_url or ci.image_url
        _set_display(ci)
    doc = ci.model_dump()
    store.put("closet_items", ci.id, doc)
    return doc
