"""Reset the database to the Apify catalog only (sprint #3, section 6). Dry run unless --yes.

    python -m scripts.rebuild_db              # print what would be reset, with counts; changes nothing
    python -m scripts.rebuild_db --yes        # back up DATA_DIR, reset, reload seed/products.json

Keeps: the 3,188-product snapshot (exactly; live-search / seed / server-only products are dropped),
tag_cache + summary_cache (catalog AI results, so re-tagging is free; --drop-ai-cache to clear them
too) and the Nessie merchant ids. Resets everything people made or the app generated: users, closets,
fits, Inspo posts (Inspo starts empty), carts, orders, saves, swipes, generated reasons and try-ons,
uploaded photos, the AI spend counter and per-user Nessie accounts. Then re-creates the blank team
accounts (u_adam, u_nabil, u_ryan, u_demo) the one-tap Welcome screen opens; --no-team skips that.
Collections it doesn't know are listed and left alone. Run warm_demo afterwards.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.store import DATA_DIR, store  # noqa: E402
from scripts.load_products import SEED  # noqa: E402

RESET = ["users", "closet_items", "fits", "fit_cache", "fitcheck_posts", "carts", "orders", "swipes",
         "wishlist", "pair_cache", "tryon_cache", "live_search_cache", "ai_usage"]
AI_CACHES = ["tag_cache", "summary_cache"]
KEEP = ["products", "nessie", *AI_CACHES]
FOLDERS = ["uploads", "tryon"]  # files under DATA_DIR (both stores)
TEAM = {"u_adam": "Adam", "u_nabil": "Nabil", "u_ryan": "Ryan", "u_demo": "Demo"}


def _collections() -> set[str]:
    """Collections present in the JSON store (Firestore: the known ones)."""
    root = getattr(store, "root", None)
    if root is None:
        return set(RESET + KEEP)
    return {p.stem for p in Path(root).glob("*.json")}


def plan(drop_ai_cache: bool = False) -> dict:
    reset = RESET + (AI_CACHES if drop_ai_cache else [])
    present = _collections()
    snapshot = json.loads(SEED.read_text())
    ids = {p["id"] for p in snapshot}
    products = store.list("products")
    # Nessie docs are keyed "merchants" / "accounts" (no id field inside), so read the keys
    nessie = store._load("nessie") if hasattr(store, "_load") else {"accounts": store.get("nessie", "accounts")}
    return {
        "reset": {c: len(store.list(c)) for c in reset if c in present},
        "products": {"now": len(products), "after": len(snapshot),
                     "dropped": sum(p["id"] not in ids for p in products)},
        "nessie_reset": sorted(k for k, v in nessie.items() if k != "merchants" and v),
        "folders": {f: sum(1 for x in (DATA_DIR / f).rglob("*") if x.is_file()) if (DATA_DIR / f).exists() else 0
                    for f in FOLDERS},
        "untouched": sorted(present - set(reset) - set(KEEP)),
        "snapshot": snapshot,
    }


def backup() -> Path | None:
    """Copy DATA_DIR next to itself (JSON store). Firestore: dump the collections we reset to JSON files."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = DATA_DIR.parent / f"{DATA_DIR.name}.bak-{stamp}"
    if getattr(store, "root", None) is not None:
        shutil.copytree(DATA_DIR, dest)
    else:
        dest.mkdir(parents=True)
        for c in RESET + KEEP:
            (dest / f"{c}.json").write_text(json.dumps(store.list(c)))
    return dest


def _clear(collection: str) -> None:
    root = getattr(store, "root", None)
    if root is not None:
        store._write(collection, {})  # one write instead of one per document
        return
    for d in store.list(collection):
        store.delete(collection, d["id"])


def rebuild(p: dict, drop_ai_cache: bool = False, team: bool = True) -> None:
    for c in p["reset"]:
        _clear(c)
    for key in p["nessie_reset"]:  # per-user customers/accounts; merchant ids stay
        store.delete("nessie", key)
    for f in FOLDERS:
        shutil.rmtree(DATA_DIR / f, ignore_errors=True)
        (DATA_DIR / f).mkdir(parents=True, exist_ok=True)
    snapshot = p["snapshot"]
    if getattr(store, "root", None) is not None:
        store._write("products", {x["id"]: x for x in snapshot})  # exactly the snapshot, one write
    else:
        keep = {x["id"] for x in snapshot}
        for x in store.list("products"):
            if x["id"] not in keep:
                store.delete("products", x["id"])
        for x in snapshot:
            store.put("products", x["id"], x)
    if team:
        for uid, name in TEAM.items():
            store.put("users", uid, {"id": uid, "display_name": name, "style_text": "", "price_ranges": {},
                                     "friends": [f for f in TEAM if f != uid]})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yes", action="store_true", help="actually reset (after a backup); default is a dry run")
    ap.add_argument("--drop-ai-cache", action="store_true", help="also clear tag_cache + summary_cache")
    ap.add_argument("--no-team", action="store_true", help="don't re-create the blank team accounts")
    a = ap.parse_args(argv)
    p = plan(a.drop_ai_cache)
    print(f"DATA_DIR: {DATA_DIR}")
    print("reset (documents):", p["reset"])
    print("products:", p["products"], "(reloaded from seed/products.json)")
    print("nessie keys reset:", p["nessie_reset"], "(merchants kept)")
    print("folders emptied (files):", p["folders"])
    print("left alone (unknown collections):", p["untouched"] or "none")
    print("team accounts re-created:", "no" if a.no_team else list(TEAM))
    if not a.yes:
        print("\nDry run: nothing changed. Re-run with --yes to back up and reset.")
        return 0
    dest = backup()
    print(f"\nbacked up to {dest}")
    rebuild(p, a.drop_ai_cache, team=not a.no_team)
    print(f"done: {len(store.list('products'))} products, {len(store.list('users'))} users. "
          "Next: tag_catalog --summaries-only, restart, warm_demo --tryons 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
