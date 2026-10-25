"""Re-run a user's closet through the current pipeline from the outfit photos already uploaded.
For closets built before closet v3 (#59): catalog photos on owned pieces, no outfits, weak brands.

    python -m scripts.redo_closet u_adam --dry-run
    python -m scripts.redo_closet u_adam
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

from app.ai import closet  # noqa: E402
from app.store import DATA_DIR, store  # noqa: E402

UPLOADS = DATA_DIR / "uploads"  # honours DATA_DIR like the server


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("user_id")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = store.list("closet_items", user_id=a.user_id)
    photos: list[str] = []
    for c in items:
        for w in c.get("worn_in") or []:
            url = w.get("photo_url")
            if url and url not in photos:
                photos.append(url)
    local = [(u, UPLOADS / u.rsplit("/", 1)[-1]) for u in photos]
    missing = [u for u, p in local if not p.exists()]
    print(f"{a.user_id}: {len(items)} items from {len(photos)} photos ({len(missing)} missing on disk)")
    if a.dry_run or not local:
        return
    for c in items:
        store.delete("closet_items", c["id"])
    names = {}  # nicknames survive the redo, keyed by photo
    for o in store.list("outfits", user_id=a.user_id):
        if (o.get("name") or "").strip():
            names[o.get("photo_url")] = o["name"]
        store.delete("outfits", o["id"])
    out = closet.add_photos(a.user_id, [(u, p if p.exists() else None) for u, p in local], kind="outfit")
    for o in out.get("outfits", []):
        if names.get(o.get("photo_url")):
            rec = store.get("outfits", o["id"])
            if rec:
                rec["name"] = names[o["photo_url"]]
                store.put("outfits", o["id"], rec)
    added = out.get("added", [])
    print(f"re-added {len(added)} pieces, merged {len(out.get('merged', []))}, "
          f"skipped {out.get('skipped', 0)}, outfits {len(out.get('outfits', []))}")
    for it in added:
        print(f"  {it.get('label')} | brand={it.get('brand')} | {str(it.get('image_url'))[-28:]}")


if __name__ == "__main__":
    main()
