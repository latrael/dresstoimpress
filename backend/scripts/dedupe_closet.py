"""Merge a user's duplicate closet outfits (the same photo uploaded to Closet and posted to Inspo).

    python -m scripts.dedupe_closet u_adam --dry-run   # list what would merge
    python -m scripts.dedupe_closet u_adam             # merge: keep the oldest copy, move pieces + wears to it

New uploads/posts are de-duplicated on the way in (app.ai.outfit_dedupe); this cleans up older data.
"""
from __future__ import annotations

import argparse

from app.ai.outfit_dedupe import dedupe_user


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("user_id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    merges = dedupe_user(args.user_id, dry_run=args.dry_run)
    verb = "would merge" if args.dry_run else "merged"
    for m in merges:
        print(f"{verb} {m['drop']} -> {m['keep']}  ({m['photo_url']})")
    print(f"{len(merges)} duplicate outfit(s) {verb} for {args.user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
