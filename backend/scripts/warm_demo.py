"""Warm everything the demo touches so the first tap on stage is instant. Run right after reset_demo.

    python -m scripts.reset_demo && python -m scripts.warm_demo        # u_demo: feed, Fit Check shops, 10 try-ons
    python -m scripts.warm_demo --tryons 0                             # skip try-ons (no body photo yet)
    python -m scripts.warm_demo --user u_adam --tryons 5

1. Feed: ranks the same cards the app's /feed shows (one Claude call) and fills the reason bank, so
   swipes keep answering instantly for the next hour (PAIR_BANK_SECONDS).
2. Fit Check: "shop this fit" for every post the user can see.
3. Try-ons: the top feed cards on the user's body photo, each with the closet piece it pairs with.
   These are the slow part (~5-8 s each, Gemini images) and are cached until the body photo changes.

Uses the same store as the server (the shared JSON store unless DATA_DIR is set). Complete the look
needs no warming (rules only, instant).
"""
from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

load_dotenv()

from app.ai import service  # noqa: E402
from app.ai.llm import usage  # noqa: E402
from app.commerce import fitcheck  # noqa: E402
from app.commerce.router import feed  # noqa: E402
from app.store import store  # noqa: E402


def _secs(t: float) -> str:
    return f"{time.time() - t:4.1f}s"


def warm(user_id: str, limit: int = 20, tryons: int = 10, out=print) -> dict:
    spent = usage().get("est_usd", 0.0)
    report = {}

    t = time.time()
    cards = feed(user_id, limit=limit)
    report["feed_cards"] = len(cards)
    report["feed_reasons"] = sum(1 for c in cards if c.get("reason"))
    out(f"feed: {len(cards)} cards, {report['feed_reasons']} with reasons ({_secs(t)})")
    t = time.time()
    feed(user_id, limit=limit)
    out(f"feed again (cached): {_secs(t)}")

    posts = fitcheck.feed(user_id, limit=50)
    shoppable = 0
    t = time.time()
    for p in posts:
        try:
            shoppable += len(fitcheck.shop(p["id"], user_id))
        except Exception as e:  # noqa: BLE001
            out(f"  fit check {p['id']}: FAIL {e}")
    report["fitcheck_posts"], report["fitcheck_shoppable"] = len(posts), shoppable
    out(f"fit check: {len(posts)} posts, {shoppable} shoppable items ({_secs(t)})")

    ok = fail = 0
    if tryons > 0:
        closet = store.list("closet_items", user_id=user_id)
        bottoms = [c["id"] for c in closet if c["category"] == "bottom"]
        for c in cards[:tryons]:
            closet_ids = (c.get("pairs_with") or [])[:1] or ([] if c.get("category") == "bottom" else bottoms[:1])
            t = time.time()
            try:
                _, cached, mode, _src = service.try_on(user_id, [c["id"]], closet_ids)
                ok += 1
                out(f"  try-on {'hit ' if cached else 'made'} {mode:<7} {c['id']:<28} {_secs(t)}")
            except Exception as e:  # noqa: BLE001
                fail += 1
                out(f"  try-on FAIL {c['id']:<28} {e}")
        out(f"try-ons: {ok} ready, {fail} failed")
    report["tryons_ok"], report["tryons_failed"] = ok, fail

    report["ai_usd"] = round(usage().get("est_usd", 0.0) - spent, 4)
    out(f"AI spend for this warm-up: ${report['ai_usd']:.4f}")
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default="u_demo")
    ap.add_argument("--limit", type=int, default=20, help="feed page size the app asks for")
    ap.add_argument("--tryons", type=int, default=10, help="how many top cards to try on (0 = skip)")
    a = ap.parse_args(argv)
    warm(a.user, a.limit, a.tryons)


if __name__ == "__main__":
    main()
