"""Keep our own image URLs working when the public address changes.

Uploads and try-ons are saved as absolute URLs (`{PUBLIC_BASE}/static/uploads/x.jpg`). A quick tunnel gets a
new hostname every restart, and seeds made before the tunnel point at localhost, so stored URLs go stale
and phones can't load them. Two fixes:
- `local_static_path(url)`: any URL whose path is /static/uploads/... or /static/tryon/... and whose file
  exists here is read from disk, whatever host it names (llm.fetch_image uses this).
- `rebase_static_urls(base)`: rewrites stored URLs of that shape to the current base. main.py runs it at
  startup, so restarting the server after a tunnel change fixes everything.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

STATIC_URL = re.compile(r"^https?://[^/?#]+(/static/(?:uploads|tryon)/[A-Za-z0-9._-]+)$")
# collection -> fields holding one of our image URLs
FIELDS = {
    "users": ("body_photo_url",),
    "closet_items": ("image_url",),
    "fitcheck_posts": ("photo_url",),
    "tryon_cache": ("image_url",),
}


def local_static_path(url: str, data_dir: Path) -> Optional[Path]:
    """The local file behind one of our /static image URLs (any host), or None."""
    m = STATIC_URL.match(url or "")
    rel = m.group(1)[len("/static/"):] if m else (url[len("/static/"):] if (url or "").startswith("/static/") else None)
    if not rel:
        return None
    root = data_dir.resolve()
    p = (root / rel).resolve()
    if root not in p.parents or not p.is_file():
        return None
    return p


def rebase_static_urls(base: str, store=None) -> int:
    """Point every stored /static image URL at `base`. Returns how many fields changed. JSON store only."""
    from .store import JsonStore
    from .store import store as default_store

    store = store or default_store
    if not isinstance(store, JsonStore):
        return 0
    base = base.rstrip("/")
    changed = 0
    for col, fields in FIELDS.items():
        for doc_id, doc in store._load(col).items():
            if not isinstance(doc, dict):
                continue
            new = dict(doc)
            for f in fields:
                m = STATIC_URL.match(str(doc.get(f) or ""))
                if m and doc[f] != base + m.group(1):
                    new[f] = base + m.group(1)
            if new != doc:
                store.put(col, doc_id, new)
                changed += sum(new[f] != doc.get(f) for f in fields if f in new)
    if changed:
        log.info("rebased %d stored image URLs onto %s", changed, base)
    return changed
