"""Did the try-on edit image 1, or did Gemini hand back a reference photo?

Gemini sometimes returns the retailer's model shot (the garment reference) instead of editing the user's
photo. A cheap perceptual-hash check catches that: the output must look more like image 1 (the person) than
like any garment reference, and not wildly different from image 1.
"""
from __future__ import annotations

import io

from PIL import Image

HASH_SIZE = 16  # 256-bit dHash; distances below are in bits


def dhash(data: bytes, size: int = HASH_SIZE) -> int:
    img = Image.open(io.BytesIO(data)).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left, right = px[row * (size + 1) + col], px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def looks_like_edit(output: bytes, source: bytes, references: list[bytes], max_source_dist: int = 110) -> bool:
    """True when `output` is plausibly an edit of `source`: closer to it than to every reference, and not
    too far from it (an in-place swap changes a small region, so most of the hash is unchanged)."""
    try:
        ho, hs = dhash(output), dhash(source)
    except Exception:
        return True  # unreadable image: let the caller's normal path decide
    d_src = hamming(ho, hs)
    if d_src > max_source_dist:
        return False
    for ref in references:
        try:
            if hamming(ho, dhash(ref)) <= d_src:
                return False
        except Exception:
            continue
    return True
