"""Outfit board: a collage of the user's photo next to the garments.

Used by /tryon when AI image generation is unavailable (no key, quota, billing, budget cap),
so the demo always shows something sensible instead of an error.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps

from .llm import fetch_image

W, H = 1024, 1280
BG = (246, 244, 241)
PAD = 32


def _load(url: str) -> Image.Image | None:
    try:
        data, _ = fetch_image(url)
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except Exception:  # noqa: BLE001 — a missing piece just leaves a gap
        return None


def _fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((box_w, box_h), Image.LANCZOS)
    return img


def outfit_board(body_url: str | None, garment_urls: list[str]) -> bytes:
    """PNG bytes: person on the left (if a photo exists), up to 4 garments stacked on the right."""
    canvas = Image.new("RGB", (W, H), BG)
    garments = [g for g in (_load(u) for u in garment_urls[:4]) if g is not None]
    body = _load(body_url) if body_url else None

    if body is not None:
        left_w = int(W * 0.58)
        b = _fit(body, left_w - 2 * PAD, H - 2 * PAD)
        canvas.paste(b, (PAD + (left_w - 2 * PAD - b.width) // 2, (H - b.height) // 2))
        col_x, col_w = left_w, W - left_w - PAD
    else:
        col_x, col_w = PAD, W - 2 * PAD

    if garments:
        slot_h = (H - PAD * (len(garments) + 1)) // len(garments)
        y = PAD
        for g in garments:
            t = _fit(g, col_w, slot_h)
            card = Image.new("RGB", (col_w, slot_h), (255, 255, 255))
            card.paste(t, ((col_w - t.width) // 2, (slot_h - t.height) // 2))
            canvas.paste(card, (col_x, y))
            y += slot_h + PAD

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
