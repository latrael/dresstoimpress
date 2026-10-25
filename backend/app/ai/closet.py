"""Closet v2: a real wardrobe. Every photo (one piece or a whole outfit) becomes standalone pieces.

Per garment: crop by its box -> dedupe against the closet (a hit MERGES: the outfit photo is added to that
item's `worn_in` instead of making a twin) -> brand read off the photo -> strict catalog match (label nouns +
colour + pattern must agree; sets product_id / brand / match_confidence for "shop similar" only) -> display
image: a generated clean product shot of the crop (Gemini), else the crop. Never a catalog photo (sprint-3 §1.2).

Sprint-3 §1.3: an outfit photo (kind "outfit", or a Fit Check post) also makes one `outfits` record
{id, user_id, photo_url, created_at, piece_ids, source: "closet"|"fitcheck"} and each piece gets `outfit_id`.

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
from . import prompts, service
from .colors import find_duplicate, same_color
from .compat import get_product, list_products
from .finder import TYPE_GROUPS, item_type, match_score
from .finder import _words as finder_words
from .llm import BadModelOutput, gemini_image, mock_mode

log = logging.getLogger(__name__)

CATEGORIES = {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}
PATTERNS = {"solid", "striped", "plaid", "graphic", "floral", "other"}
KINDS = {"piece", "outfit"}
MAX_PHOTOS = 8
# finder.match_score: type word 2.0 + color 1.0 + a descriptor 0.5 = a confident "this exact item".
CONFIDENT_SCORE = 3.5
SCORE_CEILING = 5.0
CLEAN_SHOT = prompts.CLEAN_SHOT  # fixed studio spec, see prompts.py


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public_url(name: str) -> str:
    base = os.getenv("PUBLIC_BASE", "http://localhost:8000").rstrip("/")
    return f"{base}/static/uploads/{name}"


def _brand(raw: dict) -> str | None:
    if "brand_evidence" in raw and not str(raw.get("brand_evidence") or "").strip():
        return None  # digitize v3: a brand with nothing readable in the photo is a guess
    b = raw.get("brand")
    if not isinstance(b, str):
        return None
    b = " ".join(b.split())[:40]
    return b if b and b.lower() not in {"null", "none", "unknown", "n/a"} else None


# ---------- catalog match ----------

def _product_words(product: dict) -> set[str]:
    return finder_words(" ".join([product.get("name") or "", *(product.get("colors") or []),
                                  *(product.get("style_tags") or []), product.get("description") or ""]))


def strict_match(item: dict, product: dict) -> bool:
    """Sprint-3 §1.2 bar: label nouns + colour + pattern must all agree. Type word and category agree
    (match_score > 0), every descriptor word of the label is in the product text, the colour is the same
    colour (not just "both neutral"), and the pattern word agrees (a solid piece never matches a
    product whose name says striped/plaid/floral/graphic, and vice versa)."""
    tag = {"label": item.get("label"), "category": item.get("category"), "color": item.get("color")}
    if match_score(tag, product) < CONFIDENT_SCORE:
        return False
    have = _product_words(product)
    want_type = item_type(item.get("label") or "")
    if want_type is None:
        return False
    color_text = str(item.get("color") or "")
    color_words = finder_words(color_text)
    descriptors = finder_words(item.get("label") or "") - TYPE_GROUPS[want_type] - color_words
    if descriptors - have:
        return False
    prod_colors = product.get("colors") or []
    if not (color_words & have or any(same_color(color_text, c) for c in prod_colors)):
        return False
    pattern = str(item.get("pattern") or "solid").lower()
    pattern_words = (PATTERNS - {"solid", "other"})
    said = {w for w in have if w in pattern_words}
    if pattern in pattern_words:
        if pattern not in said:
            return False
    elif said:
        return False
    return True


def catalog_match(item: dict) -> tuple[dict, float] | None:
    """The catalog product this piece most likely IS, with a 0-1 confidence; None unless the strict bar
    (label nouns + colour + pattern) is met. Used for `product_id`/`brand` ("shop similar") only: the
    closet never shows a catalog photo for an owned piece (council decision, sprint-3 §1.2)."""
    tag = {"label": item.get("label"), "category": item.get("category"), "color": item.get("color")}
    best, best_score = None, 0.0
    for p in list_products():
        if not strict_match(item, p):
            continue
        s = match_score(tag, p)
        if s > best_score:
            best, best_score = p, s
    if best is None:
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
    # never copy the catalog's brand: a "similar" product is not proof of the brand (only a visible logo is)


# ---------- clean shot ----------

def clean_shots_on() -> bool:
    return os.getenv("CLOSET_CLEAN_SHOTS", "1") != "0" and not mock_mode("GEMINI_API_KEY")


EDGE = 0.01  # a box coordinate this close to 0 or 1 means the garment runs off the photo (cut off)


def _box4(box) -> tuple[float, float, float, float] | None:
    nb = dig.normalize_box(box, 1, 1) if box is not None else None
    return nb


def sharpness(local_path: Path | None, box=None) -> float:
    """Laplacian variance of the (boxed) region: higher = sharper. 0.0 when the file isn't ours / unreadable."""
    if not local_path:
        return 0.0
    try:
        from PIL import Image, ImageFilter

        with Image.open(local_path) as im:
            im = im.convert("L")
            nb = _box4(box)
            if nb:
                w, h = im.size
                im = im.crop((int(nb[0] * w), int(nb[1] * h), max(int(nb[0] * w) + 3, int(nb[2] * w)),
                              max(int(nb[1] * h) + 3, int(nb[3] * h))))
            im.thumbnail((256, 256))
            lap = im.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
            try:
                import numpy as np

                return float(np.var(np.asarray(lap, dtype="float32")))
            except ImportError:
                hist = lap.histogram()
                n = sum(hist) or 1
                mean = sum(i * c for i, c in enumerate(hist)) / n
                return sum(c * (i - mean) ** 2 for i, c in enumerate(hist)) / n
    except Exception:  # noqa: BLE001
        return 0.0


def source_key(photo_url: str, box) -> tuple[int, float, float]:
    """Sort key for "which photo shows this garment best": not cut off > box area > sharpness."""
    from ..static_urls import local_static_path

    nb = _box4(box)
    if nb is None:
        return (0, 0.0, 0.0)
    x0, y0, x1, y1 = nb
    whole = int(not (x0 <= EDGE or y0 <= EDGE or x1 >= 1 - EDGE or y1 >= 1 - EDGE))
    area = (x1 - x0) * (y1 - y0)
    return (whole, round(area, 4), sharpness(local_static_path(photo_url, DATA_DIR), nb))


def best_source(item: dict) -> tuple[str, list | None] | None:
    """(photo_url, box) of the source photo where this piece is clearest, among every `worn_in` entry
    that has a box for it. None when no entry has a box."""
    cands = [(w["photo_url"], w["box"]) for w in item.get("worn_in") or []
             if isinstance(w, dict) and w.get("photo_url") and w.get("box") is not None]
    if not cands:
        return None
    return max(cands, key=lambda c: source_key(*c))


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


def _source_crop(item: ClosetItem) -> str | None:
    """Pick the best source photo of this piece (best_source), record it on the item and return a padded crop
    of that region to feed the clean shot. Falls back to the piece's own crop."""
    from ..static_urls import local_static_path

    best = best_source(item.model_dump())
    if best is None:
        item.clean_source_photo_url, item.clean_source_box = item.crop_image_url, None
        return item.crop_image_url
    photo_url, box = best
    item.clean_source_photo_url, item.clean_source_box = photo_url, list(box) if box is not None else None
    first = next((w for w in item.worn_in if isinstance(w, dict) and w.get("box") is not None), None)
    if first and first.get("photo_url") == photo_url and first.get("box") == box and item.crop_image_url:
        return item.crop_image_url  # the crop we already saved is exactly this region
    return dig.save_crop(local_static_path(photo_url, DATA_DIR), box) or item.crop_image_url


def _set_display(item: ClosetItem) -> None:
    """display_image_url: generated clean shot from the best source photo of the piece > the crop.
    image_url mirrors it. Never the catalog photo: an owned piece always shows the user's own picture
    (sprint-3 §1.2)."""
    source = _source_crop(item) if clean_shots_on() else item.crop_image_url
    item.display_image_url = clean_shot(source) or item.crop_image_url
    item.image_url = item.display_image_url


def _better_source_later(item_id: str, old: tuple | None) -> None:
    """A new worn_in photo may show the piece better than the current clean-shot source: regenerate off
    the request thread, best effort."""
    if not clean_shots_on():
        return
    doc = store.get("closet_items", item_id)
    if not doc:
        return
    best = best_source(doc)
    if best is None or old is not None and source_key(*best) <= source_key(*old):
        return

    def run():
        try:
            fresh = store.get("closet_items", item_id)
            if fresh:
                reshoot(fresh)
        except Exception as e:  # noqa: BLE001
            log.warning("clean shot refresh failed: %s", e)

    try:
        service._spawn(run)
    except Exception as e:  # noqa: BLE001
        log.warning("clean shot refresh not started: %s", e)


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
        occluded=bool(raw.get("occluded")),
    )


def _wear(item: dict, photo_url: str, source: str, box=None) -> dict:
    # items from before closet v2 have only image_url: that picture is both their crop and their display
    item.setdefault("crop_image_url", None)
    item["crop_image_url"] = item["crop_image_url"] or item.get("image_url")
    item["display_image_url"] = item.get("display_image_url") or item.get("image_url")
    worn = [w for w in item.get("worn_in") or [] if isinstance(w, dict)]
    hit = next((w for w in worn if w.get("photo_url") == photo_url), None)
    if hit is None:
        worn.append({"photo_url": photo_url, "at": _now(), "source": source, "box": _box_list(box)})
    elif hit.get("box") is None and box is not None:
        hit["box"] = _box_list(box)
    item["worn_in"] = worn
    return item


def _box_list(box) -> list[float] | None:
    nb = _box4(box)
    return [round(v, 4) for v in nb] if nb else None


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
            old = (hit.get("clean_source_photo_url"), hit["clean_source_box"]) if hit.get("clean_source_box") else None
            _wear(hit, photo_url, source, box=crop_box)
            if not hit.get("brand") and draft.brand:
                hit["brand"] = draft.brand
            store.put("closet_items", hit["id"], hit)
            _better_source_later(hit["id"], old)  # the new photo may show the piece better: new clean shot
            return hit, True
    # the crop is the piece's own picture; without a usable box the whole photo stands in for it
    draft.crop_image_url = (dig.save_crop(local_path, crop_box) if crop_box is not None else None) or photo_url
    draft.worn_in = [{"photo_url": photo_url, "at": _now(), "source": source, "box": _box_list(crop_box)}]
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
    if kind == "outfit" and (out["added"] or out["merged"]):
        out["outfit"] = create_outfit(user_id, photo_url, out["added"] + out["merged"], source)
    return out


# ---------- outfits ----------

OUTFITS = "outfits"


def create_outfit(user_id: str, photo_url: str, pieces: list[dict], source: str) -> dict:
    """One `outfits` record for a whole-fit photo and its pieces; each piece gets `outfit_id` (a piece
    that already belongs to an older outfit keeps that one: it was merged, not re-made)."""
    outfit = {"id": f"of_{uuid.uuid4().hex[:8]}", "user_id": user_id, "photo_url": photo_url, "created_at": _now(),
              "piece_ids": [], "source": source}
    for p in pieces:
        if p["id"] in outfit["piece_ids"]:
            continue
        outfit["piece_ids"].append(p["id"])
        if not p.get("outfit_id"):
            p["outfit_id"] = outfit["id"]
            saved = store.get("closet_items", p["id"]) or p
            saved["outfit_id"] = outfit["id"]
            store.put("closet_items", p["id"], saved)
    store.put(OUTFITS, outfit["id"], outfit)
    return outfit


def outfit_view(outfit: dict) -> dict:
    """The record with its pieces embedded (`pieces`: the ClosetItems that still exist, in order)."""
    pieces = [store.get("closet_items", pid) for pid in outfit.get("piece_ids") or []]
    return {**outfit, "pieces": [p for p in pieces if p]}


def list_outfits(user_id: str) -> list[dict]:
    """A user's outfits, newest first, pieces embedded."""
    rows = store.list(OUTFITS, user_id=user_id)
    rows.sort(key=lambda o: o.get("created_at") or "", reverse=True)
    return [outfit_view(o) for o in rows]


def delete_outfit(user_id: str, outfit_id: str) -> bool:
    """Remove the outfit record; its pieces stay in the closet (their `outfit_id` is cleared)."""
    outfit = store.get(OUTFITS, outfit_id)
    if not outfit or outfit.get("user_id") != user_id:
        return False
    for pid in outfit.get("piece_ids") or []:
        p = store.get("closet_items", pid)
        if p and p.get("outfit_id") == outfit_id:
            p["outfit_id"] = None
            store.put("closet_items", pid, p)
    store.delete(OUTFITS, outfit_id)
    return True


def add_photos(user_id: str, photos: list[tuple[str, Path | None]], kind: str) -> dict:
    """Several photos (url, local path) with one intent -> one combined {added, merged, skipped}."""
    out = {"added": [], "merged": [], "skipped": 0, "outfits": []}
    for url, path in photos[:MAX_PHOTOS]:
        r = add_photo(user_id, url, path, kind)
        out["added"] += r["added"]
        out["skipped"] += r["skipped"]
        if r.get("outfit"):
            out["outfits"].append(r["outfit"])
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
    if out["added"] or out["merged"]:
        out["outfit"] = create_outfit(user_id, photo_url, out["added"] + out["merged"], "fitcheck")
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
    """Regenerate the clean shot from the best source photo of the piece. Never a catalog image."""
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
            # the picture only changes for pre-sprint-3 items that still show a catalog photo
            redisplay = bool(item.get("catalog_image_url")) and item.get("display_image_url") == item.get("catalog_image_url")
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
