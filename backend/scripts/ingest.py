"""Load products from H&M and Uniqlo into the `products` collection.

    python -m scripts.ingest                                   # live, default keywords (needs APIFY_TOKEN)
    python -m scripts.ingest --hm "baggy jeans,y2k" --uniqlo "men jeans" --per 5 --no-tag
    python -m scripts.ingest --from-file "data/raw/hm_*.json" --retailer hm --dry-run
    python -m scripts.ingest --from-file data/raw/uniqlo_a.json --from-file data/raw/uniqlo_b.json --retailer uniqlo
    python -m scripts.ingest --hm "mens boots" --uniqlo "" --save-raw "seed/raw/{retailer}_boots.json.gz"
    python -m scripts.ingest --hm "mens polos" --uniqlo "" --max-charge 1.5      # cap this run at $1.50
    python -m scripts.ingest --from-dataset DATASET_ID --retailer hm --save-raw seed/raw/hm_x.json.gz

--from-file normalizes saved raw actor output (a JSON array, .gz ok) without calling Apify.
--from-dataset downloads an existing Apify run's dataset (no new run, a fraction of a cent) and
    normalizes it the same way: how to recover a run whose wait timed out or 502'd. Needs APIFY_TOKEN.
--save-raw keeps the raw output of a live pull or --from-dataset ({retailer} in the path is filled in; .gz ok).
--max-charge caps every live actor run (Apify maxTotalChargeUsd, per run; 0 = no cap).
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


def _load_files(patterns: list[str]) -> tuple[list[str], list[dict]]:
    paths = sorted({p for pat in patterns for p in (glob.glob(pat) or [pat])})
    raw: list[dict] = []
    for path in paths:
        with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
            raw += json.load(f)
    return paths, raw


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hm", default=HM_DEFAULT, help="comma-separated H&M keywords ('' to skip)")
    ap.add_argument("--uniqlo", default=UNIQLO_DEFAULT, help="comma-separated Uniqlo categories ('' to skip)")
    ap.add_argument("--per", type=int, default=10, help="items per keyword / category")
    ap.add_argument("--no-tag", action="store_true", help="skip the AI tagger")
    ap.add_argument("--dry-run", action="store_true", help="print, don't save")
    ap.add_argument("--from-file", action="append", default=[], help="raw JSON array (glob ok, repeatable)")
    ap.add_argument("--from-dataset", action="append", default=[], metavar="ID",
                    help="Apify dataset id of a finished run (repeatable, same retailer)")
    ap.add_argument("--retailer", choices=sorted(ing.NORMALIZERS), help="retailer of --from-file / --from-dataset data")
    ap.add_argument("--save-raw", metavar="PATH", help="live runs / --from-dataset: write raw actor output here ({retailer} ok)")
    ap.add_argument("--max-charge", type=float, default=ing.MAX_CHARGE_USD, metavar="USD",
                    help=f"cap per live actor run (default ${ing.MAX_CHARGE_USD}; 0 = no cap)")
    ap.add_argument("--wait", type=float, default=900, metavar="S",
                    help="seconds to wait for a live run before giving up (it keeps running; use --from-dataset)")
    ap.add_argument("--show", type=int, default=3, help="sample products to print in --dry-run")
    a = ap.parse_args(argv)
    if a.from_file and a.from_dataset:
        ap.error("use --from-file or --from-dataset, not both")

    if a.from_file:
        if not a.retailer:
            ap.error("--from-file needs --retailer")
        paths, raw_items = _load_files(a.from_file)
        products, summary = ing.process({a.retailer: raw_items}, do_tag=not a.no_tag, dry_run=a.dry_run)
        summary["files"] = paths
        return _report(a, products, summary)

    token = ing.os.getenv("APIFY_TOKEN")
    if not token:
        ap.error("APIFY_TOKEN not set (add it to backend/.env) or use --from-file")
    if a.from_dataset:
        if not a.retailer:
            ap.error("--from-dataset needs --retailer")
        raw_items = []
        for ds in a.from_dataset:
            items = ing.dataset_items(ds, token)
            print(f"dataset {ds}: {len(items)} items", file=sys.stderr)
            raw_items += items
        raw_files = _save_raw({a.retailer: raw_items}, a.save_raw) if a.save_raw else None
        products, summary = ing.process({a.retailer: raw_items}, do_tag=not a.no_tag, dry_run=a.dry_run)
        summary["datasets"] = a.from_dataset
        if raw_files:
            summary["raw_files"] = raw_files
        return _report(a, products, summary)

    if a.save_raw and _split(a.hm) and _split(a.uniqlo) and "{retailer}" not in a.save_raw:
        ap.error("--save-raw needs {retailer} in the path when pulling both retailers")
    raw, raw_files = {}, []
    pulls = [("hm", "H&M", ing.fetch_hm, _split(a.hm)), ("uniqlo", "Uniqlo", ing.fetch_uniqlo, _split(a.uniqlo))]
    try:
        for retailer, label, fetch, terms in pulls:
            if not terms:
                continue
            print(f"{label}: {terms} x {a.per} (cap ${a.max_charge or 'none'})", file=sys.stderr)
            raw[retailer] = fetch(terms, a.per, token, a.max_charge or None, a.wait)
            if a.save_raw:  # right away, so a later failure (other retailer, process) keeps this paid pull
                raw_files += _save_raw({retailer: raw[retailer]}, a.save_raw)
    except ing.ApifyRunError as e:
        sys.exit(f"{e}\n(raw saved so far: {raw_files or 'none'})")
    products, summary = ing.process(raw, do_tag=not a.no_tag, dry_run=a.dry_run)
    if raw_files:
        summary["raw_files"] = raw_files
    return _report(a, products, summary)


def _report(a, products: list[dict], summary: dict) -> dict:
    if a.dry_run:
        for p in products[: a.show]:
            print(json.dumps(p, indent=1))
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    main()
