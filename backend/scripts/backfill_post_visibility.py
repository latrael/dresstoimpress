"""One-time: posts made before the Friends | Everyone picker (#103) were stored as "friends" by the old default,
not by choice, so the Everyone feed now hides them from non-friends. Mark those posts public.

    python -m scripts.backfill_post_visibility            # dry run: list what would change
    python -m scripts.backfill_post_visibility --yes      # write
    python -m scripts.backfill_post_visibility --before 2026-10-25T11:54:32+00:00 --yes
"""
from __future__ import annotations

import argparse
from datetime import datetime

PICKER_SHIPPED = "2026-10-25T11:54:32+00:00"  # #103 merged: posts after this chose their visibility


def _at(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", default=PICKER_SHIPPED, help="only posts created before this ISO time")
    ap.add_argument("--yes", action="store_true", help="write (default: dry run)")
    a = ap.parse_args(argv)
    from app.store import store

    cutoff = _at(a.before)
    old = [p for p in store.list("fitcheck_posts")
           if p.get("visibility") == "friends" and p.get("created_at") and _at(p["created_at"]) < cutoff]
    for p in old:
        print(f"  {p['id']}  {p['user_id']:12} {p['created_at']}")
        if a.yes:
            store.put("fitcheck_posts", p["id"], {**p, "visibility": "public"})
    print(f"{len(old)} post(s) {'made public' if a.yes else 'would be made public (dry run; --yes to write)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
