"""Re-render a user's white-background clean shots only (no re-tagging), with the validated clean_shot (v3).

    python -m scripts.redo_clean_shots u_adam --dry-run        # count + cost
    python -m scripts.redo_clean_shots u_adam --only ci_a,ci_b  # just these items
    python -m scripts.redo_clean_shots u_adam                   # all of the user's pieces

Each item costs ~1-2 Gemini images (second only when the first fails the check) + ~2 Haiku checks.
"""
from __future__ import annotations

import argparse

from app.ai import closet
from app.ai.service import store

COST_PER_ITEM_USD = 0.06  # ~1.3 images × $0.039 + checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("user_id")
    ap.add_argument("--only", default="", help="comma-separated closet item ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    items = [i for i in store.list("closet_items") if i.get("user_id") == args.user_id
             and (not only or i.get("id") in only)]
    print(f"{len(items)} item(s), est. ${len(items) * COST_PER_ITEM_USD:.2f}")
    if args.dry_run:
        for i in items:
            print(f"  {i['id']}  {i.get('category')}: {i.get('label')}")
        return 0
    ok = 0
    for i in items:
        before = i.get("display_image_url")
        doc = closet.reshoot(i)
        after = doc.get("display_image_url")
        good = bool(after and after.endswith("-clean.png"))
        ok += good
        print(f"  {i['id']}  {i.get('label')}: {'clean shot' if good else 'kept crop'}"
              f"{'' if after != before else ' (unchanged)'}")
    print(f"{ok}/{len(items)} clean shots passed the check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
