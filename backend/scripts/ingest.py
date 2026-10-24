"""Load products from H&M and Uniqlo into the `products` collection.

    python -m scripts.ingest                                   # live, default keywords (needs APIFY_TOKEN)
    python -m scripts.ingest --hm "baggy jeans,y2k" --uniqlo "men jeans" --per 5 --no-tag
    python -m scripts.ingest --from-file "data/raw/hm_*.json" --retailer hm --dry-run
    python -m scripts.ingest --from-file data/raw/uniqlo_a.json --from-file data/raw/uniqlo_b.json --retailer uniqlo
    python -m scripts.ingest --hm "mens boots" --uniqlo "" --save-raw "seed/raw/{retailer}_boots.json.gz"

--from-file normalizes saved raw actor output (a JSON array, .gz ok) without calling Apify.
--save-raw keeps a live pull's raw output for that ({retailer} in the path is filled in; .gz ok).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app.commerce import ingest as ing  # noqa: E402  (after dotenv so env is set)

HM_DEFAULT = ("womens tops, mens graphic tees, baggy jeans, womens jeans, mens jackets, "
              "womens jackets, hoodies, y2k, womens sneakers, mens sneakers, womens boots")
UNIQLO_DEFAULT = ("women t-shirts, women sweaters, women jeans, women pants, women jackets, "
                  "men t-shirts, men sweaters, men jeans, men pants, men jackets")


def _split(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def _save_raw(raw: dict[str, list[dict]], pattern: str) -> list[str]:
    paths = []
    for retailer, items in raw.items():
        path = pattern.replace("{retailer}", retailer)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with (gzip.open(path, "wt") if path.endswith(".gz") else open(path, "w")) as f:
            json.dump(items, f)
        print(f"saved {len(items)} raw {retailer} items -> {path}", file=sys.stderr)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hm", default=HM_DEFAULT, help="comma-separated H&M keywords ('' to skip)")
    ap.add_argument("--uniqlo", default=UNIQLO_DEFAULT, help="comma-separated Uniqlo categories ('' to skip)")
    ap.add_argument("--per", type=int, default=10, help="items per keyword / category")
    ap.add_argument("--no-tag", action="store_true", help="skip the AI tagger")
    ap.add_argument("--dry-run", action="store_true", help="print, don't save")
    ap.add_argument("--from-file", action="append", default=[], help="raw JSON array (glob ok, repeatable)")
    ap.add_argument("--retailer", choices=sorted(ing.NORMALIZERS), help="retailer of --from-file data")
    ap.add_argument("--save-raw", metavar="PATH", help="live runs: write raw actor output here ({retailer} ok)")
    ap.add_argument("--show", type=int, default=3, help="sample products to print in --dry-run")
    a = ap.parse_args(argv)

    if a.from_file:
        if not a.retailer:
            ap.error("--from-file needs --retailer")
        paths = sorted({p for pat in a.from_file for p in (glob.glob(pat) or [pat])})
        raw: list[dict] = []
        for path in paths:
            with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
                raw += json.load(f)
        products, summary = ing.process({a.retailer: raw}, do_tag=not a.no_tag, dry_run=a.dry_run)
        summary["files"] = paths
    else:
        token = ing.os.getenv("APIFY_TOKEN")
        if not token:
            ap.error("APIFY_TOKEN not set (add it to backend/.env) or use --from-file")
        if a.save_raw and _split(a.hm) and _split(a.uniqlo) and "{retailer}" not in a.save_raw:
            ap.error("--save-raw needs {retailer} in the path when pulling both retailers")
        raw = {}
        if _split(a.hm):
            print(f"H&M: {_split(a.hm)} x {a.per}", file=sys.stderr)
            raw["hm"] = ing.fetch_hm(_split(a.hm), a.per, token)
        if _split(a.uniqlo):
            print(f"Uniqlo: {_split(a.uniqlo)} x {a.per}", file=sys.stderr)
            raw["uniqlo"] = ing.fetch_uniqlo(_split(a.uniqlo), a.per, token)
        raw_files = _save_raw(raw, a.save_raw) if a.save_raw else None  # before process, so a crash keeps it
        products, summary = ing.process(raw, do_tag=not a.no_tag, dry_run=a.dry_run)
        if raw_files:
            summary["raw_files"] = raw_files

    if a.dry_run:
        for p in products[: a.show]:
            print(json.dumps(p, indent=1))
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    main()
