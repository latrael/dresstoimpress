"""Shared helpers for the morning photo scripts: copy a local photo into uploads and return its URL."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
         ".heic": "image/heic"}
MAX_BYTES = 10 * 1024 * 1024


def is_photo(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TYPES and not path.name.startswith(".")


def save_upload(src: Path) -> str:
    """Copy `src` into DATA_DIR/uploads under a random name; return its public URL (same shape as uploads
    through the API, so tagging, try-on and the startup URL rebase all treat it the same way)."""
    from app.store import DATA_DIR

    if not is_photo(src):
        raise ValueError(f"not a photo (jpg/png/webp/heic): {src}")
    if src.stat().st_size > MAX_BYTES:
        raise ValueError(f"over 10 MB: {src}")
    folder = DATA_DIR / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + (".jpg" if src.suffix.lower() == ".jpeg" else src.suffix.lower())
    shutil.copyfile(src, folder / name)
    base = os.getenv("PUBLIC_BASE", "http://localhost:8000").rstrip("/")
    return f"{base}/static/uploads/{name}"
