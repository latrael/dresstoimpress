"""One closet outfit per real photo (Adam, Oct 25).

The same outfit photo can reach the closet twice: uploaded in Closet and posted to Inspo (a Fit Check post
auto-adds its pieces to the closet). Both paths call `find_same` before digitizing, so the second copy
reuses the first outfit instead of creating a duplicate.

Same photo = same URL, or a 64-bit difference hash (dHash, 9x8 grayscale) within MAX_DIST bits. A
re-encoded / resized / re-compressed copy of a photo lands within a few bits; different photos are ~30 apart.
Images with almost no structure (a blank or two-tone test image) hash to ~0 and are never matched by hash.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..store import DATA_DIR, store

log = logging.getLogger(__name__)

OUTFITS = "outfits"
MAX_DIST = 6
MIN_BITS = 4  # a hash with fewer set (or unset) bits than this has no structure to compare


def dhash(path: Path | str | None) -> str | None:
    """16-hex-char difference hash of an image file, or None if unreadable."""
    if not path:
        return None
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as im:
            small = ImageOps.exif_transpose(im).convert("L").resize((9, 8), Image.LANCZOS)
            px = list(small.tobytes())
    except Exception as e:  # noqa: BLE001
        log.debug("dhash unreadable %s: %s", path, e)
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | int(px[row * 9 + col] > px[row * 9 + col + 1])
    return f"{bits:016x}"


def distance(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def informative(h: str | None) -> bool:
    if not h:
        return False
    ones = bin(int(h, 16)).count("1")
    return MIN_BITS <= ones <= 64 - MIN_BITS


def photo_hash(photo_url: str, local_path: Path | None = None) -> str | None:
    if local_path is None:
        from ..static_urls import local_static_path

        local_path = local_static_path(photo_url or "", DATA_DIR)
    return dhash(local_path)


def outfit_hash(outfit: dict) -> str | None:
    """The outfit's photo hash, computed once and cached on the record (older outfits have none)."""
    h = outfit.get("phash")
    if h:
        return h
    h = photo_hash(outfit.get("photo_url") or "")
    if h and outfit.get("id"):
        saved = store.get(OUTFITS, outfit["id"])
        if saved is not None:
            saved["phash"] = h
            store.put(OUTFITS, outfit["id"], saved)
    return h


def same_photo(a_url: str, a_hash: str | None, outfit: dict) -> bool:
    if a_url and outfit.get("photo_url") == a_url:
        return True
    if not informative(a_hash):
        return False
    b = outfit_hash(outfit)
    return informative(b) and distance(a_hash, b) <= MAX_DIST


def find_same(user_id: str, photo_url: str, local_path: Path | None = None, h: str | None = None) -> dict | None:
    """The user's oldest outfit showing this same photo, else None."""
    h = h or photo_hash(photo_url, local_path)
    rows = sorted(store.list(OUTFITS, user_id=user_id), key=lambda o: o.get("created_at") or "")
    for o in rows:
        if same_photo(photo_url, h, o):
            return o
    return None


def duplicate_result(outfit: dict) -> dict:
    """add_photo / add_from_fit result for a photo that's already an outfit: nothing new, its pieces merged."""
    pieces = [store.get("closet_items", pid) for pid in outfit.get("piece_ids") or []]
    return {"added": [], "merged": [p for p in pieces if p], "skipped": 0, "outfit": outfit, "duplicate": True}


def dedupe_user(user_id: str, dry_run: bool = False) -> list[dict]:
    """Merge a user's existing duplicate outfits into the oldest copy. Returns [{keep, drop, photo_url}].
    Pieces move to the kept outfit (piece_ids union, `outfit_id` re-pointed) and their `worn_in` entries for
    the dropped photo are re-pointed to the kept photo (one wear per photo)."""
    rows = sorted(store.list(OUTFITS, user_id=user_id), key=lambda o: o.get("created_at") or "")
    kept: list[dict] = []
    merges: list[dict] = []
    for o in rows:
        h = outfit_hash(o)
        keeper = next((k for k in kept if same_photo(o.get("photo_url") or "", h, k)), None)
        if keeper is None:
            kept.append(o)
            continue
        merges.append({"keep": keeper["id"], "drop": o["id"], "photo_url": o.get("photo_url")})
        if dry_run:
            continue
        for pid in o.get("piece_ids") or []:
            if pid not in keeper.setdefault("piece_ids", []):
                keeper["piece_ids"].append(pid)
            item = store.get("closet_items", pid)
            if not item:
                continue
            if item.get("outfit_id") in (o["id"], None):
                item["outfit_id"] = keeper["id"]
            wears, seen = [], set()
            for w in item.get("worn_in") or []:
                url = w.get("photo_url")
                if url == o.get("photo_url"):
                    w = {**w, "photo_url": keeper.get("photo_url")}
                    url = w["photo_url"]
                if url in seen:
                    continue
                seen.add(url)
                wears.append(w)
            item["worn_in"] = wears
            store.put("closet_items", pid, item)
        if o.get("source") == "fitcheck" or keeper.get("source") == "fitcheck":
            keeper["posted"] = True
        if not (keeper.get("name") or "").strip() and (o.get("name") or "").strip():
            keeper["name"] = o["name"]  # a nickname on the dropped copy moves to the keeper
        store.put(OUTFITS, keeper["id"], keeper)
        store.delete(OUTFITS, o["id"])
    return merges
