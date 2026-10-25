"""Digitize wardrobe: one photo of several clothes -> one closet item per garment, each with its own crop.

The vision model lists every garment with a bounding box. Each box is cropped (with a little padding)
into its own image under /static/uploads, and the tags from that same answer fill the closet item, so a
pile of 5 clothes costs one AI call. Without a usable box (or for HEIC, which Pillow can't open) the item
keeps the whole photo. No garments found -> the photo is tagged as a single item, like /closet/upload.
"""
from __future__ import annotations

import hashlib
import io
import os
import uuid
from pathlib import Path

from ..models import ClosetItem
from ..store import DATA_DIR, store
from . import prompts
from .colors import find_duplicate
from .llm import CLAUDE_TAG_MODEL, BadModelOutput, ai_json, text_mock

MAX_ITEMS = 8
PAD = 0.04          # padding around each box, as a fraction of the image size
MIN_SIDE = 0.06     # boxes thinner than this (fraction of the image) are ignored
CROP_MAX_PX = 1024  # longest side of a saved crop
CATEGORIES = {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}
PATTERNS = {"solid", "striped", "plaid", "graphic", "floral", "other"}

_MOCK = [
    {"label": "black cargo pants", "category": "bottom", "color": "black", "pattern": "solid",
     "style_tags": ["streetwear"], "formality": 2, "brand": None, "box": [0.0, 0.0, 0.5, 1.0]},
    {"label": "white baby tee", "category": "top", "color": "white", "pattern": "solid",
     "style_tags": ["y2k", "minimalist"], "formality": 2, "brand": None, "box": [0.5, 0.0, 1.0, 1.0]},
]


def normalize_box(box, width: int, height: int) -> tuple[float, float, float, float] | None:
    """[x0, y0, x1, y1] as 0-1 fractions. Accepts 0-1 fractions, 0-1000 (Gemini style) or pixels.
    None if it isn't four numbers or the box is too thin to be one garment."""
    try:
        x0, y0, x1, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    top = max(x0, y0, x1, y1)
    if top > 1.0:
        if top <= 1000.0:
            x0, y0, x1, y1 = x0 / 1000, y0 / 1000, x1 / 1000, y1 / 1000
        else:
            x0, x1, y0, y1 = x0 / width, x1 / width, y0 / height, y1 / height
    x0, x1 = sorted((min(1.0, max(0.0, x0)), min(1.0, max(0.0, x1))))
    y0, y1 = sorted((min(1.0, max(0.0, y0)), min(1.0, max(0.0, y1))))
    if x1 - x0 < MIN_SIDE or y1 - y0 < MIN_SIDE:
        return None
    return x0, y0, x1, y1


def upright_jpeg(path: Path) -> Path | None:
    """Re-save a phone photo with its EXIF rotation applied, so the model and the crops see the same
    picture. Returns the new file (same folder) or None if Pillow can't read it (e.g. HEIC)."""
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            out = path.with_name(f"{uuid.uuid4().hex}.jpg")
            im.save(out, "JPEG", quality=90)
            return out
    except Exception:  # noqa: BLE001 - unreadable format: fall back to the original upload
        return None


def crop(path: Path, box) -> bytes | None:
    """JPEG bytes of one padded box from the photo, or None if the box or image is unusable."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            nb = normalize_box(box, w, h)
            if nb is None:
                return None
            x0, y0, x1, y1 = nb
            x0, y0 = max(0.0, x0 - PAD), max(0.0, y0 - PAD)
            x1, y1 = min(1.0, x1 + PAD), min(1.0, y1 + PAD)
            piece = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
            piece.thumbnail((CROP_MAX_PX, CROP_MAX_PX))
            buf = io.BytesIO()
            piece.save(buf, "JPEG", quality=88)
            return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _public_url(name: str) -> str:
    base = os.getenv("PUBLIC_BASE", "http://localhost:8000").rstrip("/")
    return f"{base}/static/uploads/{name}"


def detect(image_url: str) -> list[dict]:
    """Garments in the photo, each with tags and a box. Cached per photo."""
    if text_mock():
        return [dict(d) for d in _MOCK]
    key = f"dig{prompts.DIGITIZE_VERSION}-" + hashlib.sha256(image_url.encode()).hexdigest()[:24]
    hit = store.get("tag_cache", key)
    if hit:
        return hit["items"]
    raw = ai_json(prompts.DIGITIZE, image_url=image_url, max_tokens=900, model=CLAUDE_TAG_MODEL)
    items = [r for r in raw if isinstance(r, dict) and r.get("label")] if isinstance(raw, list) else []
    store.put("tag_cache", key, {"items": items})
    return items


def save_crop(local_path: Path | None, box) -> str | None:
    """Crop one box out of the photo into /static/uploads; its public URL, or None without a usable box."""
    piece = crop(local_path, box) if local_path else None
    if not piece:
        return None
    name = f"{uuid.uuid4().hex}.jpg"
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads" / name).write_bytes(piece)
    return _public_url(name)


def digitize(user_id: str, image_url: str, local_path: Path | None) -> list[ClosetItem]:
    """Closet items for every garment in one photo (saved, duplicates flagged). Empty if none found."""
    from .service import _style_tags

    try:
        found = detect(image_url)[:MAX_ITEMS]
    except BadModelOutput:
        found = []
    existing = store.list("closet_items", user_id=user_id)
    out: list[ClosetItem] = []
    for d in found:
        url = image_url
        piece = crop(local_path, d.get("box")) if local_path else None
        if piece:
            name = f"{uuid.uuid4().hex}.jpg"
            (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
            (DATA_DIR / "uploads" / name).write_bytes(piece)
            url = _public_url(name)
        try:
            formality = min(5, max(1, int(d.get("formality", 3))))
        except (TypeError, ValueError):
            formality = 3
        item = ClosetItem(
            id=f"ci_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            image_url=url,
            category=d.get("category") if d.get("category") in CATEGORIES else "top",
            color=str(d.get("color") or "unknown"),
            pattern=d.get("pattern") if d.get("pattern") in PATTERNS else "other",
            style_tags=_style_tags(d, 5),
            formality=formality,
            source="photo",
            label=" ".join(str(d.get("label", "")).split()[:5]),
        )
        item.duplicate_of = find_duplicate(item.model_dump(), existing + [i.model_dump() for i in out])
        store.put("closet_items", item.id, item.model_dump())
        out.append(item)
    return out
