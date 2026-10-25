"""Warm the try-on cache for the demo so every card's try-on loads instantly.

    python -m scripts.precompute_tryons                 # u_demo, top 10 picks x each closet bottom
    python -m scripts.precompute_tryons --user u_adam --limit 5

Pairs each of the user's top feed picks with the closet item it was paired with
(or the first closet bottom). Run Saturday night after feature freeze.
"""
import argparse
import time

from dotenv import load_dotenv

load_dotenv()

from app.ai import service  # noqa: E402
from app.store import store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="u_demo")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    closet = store.list("closet_items", user_id=args.user)
    bottoms = [c["id"] for c in closet if c["category"] == "bottom"]
    picks = service.pair(args.user, [], k=args.limit)
    print(f"{len(picks)} picks for {args.user}")

    ok = fail = 0
    for r in picks:
        closet_ids = r.pairs_with[:1] or bottoms[:1]
        t = time.time()
        try:
            url, cached, mode, _src = service.try_on(args.user, [r.product_id], closet_ids)
            ok += 1
            print(f"  {'hit ' if cached else 'made'} {mode:<7} {r.product_id:<20} {time.time() - t:5.1f}s  {url}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  FAIL {r.product_id:<20} {e}")
    print(f"done: {ok} ready, {fail} failed")


if __name__ == "__main__":
    main()
