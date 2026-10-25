"""Load a folder of real clothing photos into a user's closet (the morning photo step, one command).

    python -m scripts.load_closet ~/dti-photos/closet --replace-seed       # u_demo; drop the 3 placeholders
    python -m scripts.load_closet ~/dti-photos/closet --dry-run            # tag only, save nothing
    python -m scripts.load_closet ~/dti-photos/closet --user u_adam

One item per photo, laid flat, good light. Each photo is copied into uploads and tagged by the same code as
POST /closet/upload (~$0.0002 each on Haiku), so labels, duplicate_of and pairing all work the same.
--replace-seed removes the user's seed placeholder items (source "seed") after the new ones are in.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.ai import service  # noqa: E402
from app.ai.llm import BadModelOutput  # noqa: E402
from app.store import store  # noqa: E402
from scripts.demo_photos import is_photo, save_upload  # noqa: E402


def load_closet(folder: Path, user_id: str = "u_demo", replace_seed: bool = False,
                dry_run: bool = False) -> dict:
    folder = folder.expanduser()
    photos = sorted(p for p in folder.iterdir() if is_photo(p)) if folder.is_dir() else []
    if not photos:
        raise SystemExit(f"no photos (jpg/png/webp/heic) in {folder}")
    added, skipped = [], []
    for p in photos:
        if dry_run:
            print(f"  would add {p.name}")
            continue
        url = save_upload(p)
        try:
            item = service.tag_closet_item(user_id, url)
        except service.NotClothing:
            skipped.append((p.name, "not clothing"))
            print(f"  skip {p.name}: not clothing")
            continue
        except BadModelOutput as e:
            skipped.append((p.name, str(e)))
            print(f"  skip {p.name}: tagger failed ({e})")
            continue
        added.append(item)
        dup = f"  (looks like {item.duplicate_of})" if item.duplicate_of else ""
        print(f"  + {p.name}: {item.label!r} {item.category} {item.color} {item.pattern}{dup}")
    removed = []
    if replace_seed and added:
        for c in store.list("closet_items", user_id=user_id):
            if c.get("source") == "seed":
                store.delete("closet_items", c["id"])
                removed.append(c["id"])
    return {"added": [i.id for i in added], "skipped": skipped, "removed_seed": removed}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--user", default="u_demo")
    ap.add_argument("--replace-seed", action="store_true", help="remove the seed placeholder items after adding")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    out = load_closet(a.folder, a.user, a.replace_seed, a.dry_run)
    print(f"{a.user}: added {len(out['added'])}, skipped {len(out['skipped'])}, removed seed {len(out['removed_seed'])}")
    sys.exit(1 if out["skipped"] and not out["added"] else 0)


if __name__ == "__main__":
    main()
