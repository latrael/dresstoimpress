"""Discover board pins: seed/raw/pinterest_<style>_<dept>_*.json.gz -> AI-tagged pins in seed/pins.json, and load them.

Normalizes epctex/pinterest-scraper search results (app.commerce.discover.normalize_pin: drops ads, videos, pins
without an image size), de-dupes by image, tags each pin's pieces with service.tag_fit (the Inspo tagger, Claude
vision, ~$0.0005/pin, cached) and keeps only real outfits (>= MIN_PIECES tagged garments).

    python -m scripts.ingest_pins --limit 10           # dry run: tag 10, print, write nothing
    python -m scripts.ingest_pins --yes                # tag everything new, write seed/pins.json
    python -m scripts.ingest_pins --load               # load seed/pins.json into the store (no AI): servers
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "seed" / "raw"
SNAPSHOT = ROOT / "seed" / "pins.json"
MIN_PIECES = 2
_FILE = re.compile(r"pinterest_(?P<style>[a-z0-9]+)_(?P<dept>women|men)_")


def raw_pins() -> list[dict]:
    """Every normalized pin from the raw pulls, first occurrence of each image wins."""
    from app.commerce.discover import normalize_pin

    out, seen = [], set()
    for f in sorted(glob.glob(str(RAW / "pinterest_*.json.gz"))):
        m = _FILE.search(Path(f).name)
        if not m:
            continue
        for raw in json.load(gzip.open(f)):
            pin = normalize_pin(raw, m["style"], m["dept"])
            if pin and pin["image_url"] not in seen and pin["id"] not in seen:
                seen.update((pin["image_url"], pin["id"]))
                out.append(pin)
    return out


def tag(pin: dict) -> dict:
    from app.ai import service

    try:
        return {**pin, "tagged": service.tag_fit(pin["image_url"])}
    except Exception as e:  # noqa: BLE001 - an untaggable pin is just left out
        print(f"  tag failed {pin['id']}: {str(e)[:80]}")
        return pin


def load(path: Path | None = None) -> int:
    from app.store import store

    pins = json.loads((path or SNAPSHOT).read_text())
    keep = {p["id"] for p in pins}
    for p in store.list("pins"):
        if p["id"] not in keep:
            store.delete("pins", p["id"])
    for p in pins:
        store.put("pins", p["id"], p)
    return len(pins)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yes", action="store_true", help="write seed/pins.json (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="only tag this many new pins")
    ap.add_argument("--load", action="store_true", help="load seed/pins.json into the store and stop (no AI)")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    if a.load:
        print(f"loaded {load()} pins -> store 'pins'")
        return 0

    done = {p["id"]: p for p in json.loads(SNAPSHOT.read_text())} if SNAPSHOT.exists() else {}
    todo = [p for p in raw_pins() if p["id"] not in done]
    todo = todo[:a.limit] if a.limit else todo
    print(f"{len(todo)} new pins to tag ({len(done)} already in the snapshot)")
    with ThreadPoolExecutor(a.workers) as ex:
        tagged = list(ex.map(tag, todo))
    kept = [p for p in tagged if len(p.get("tagged") or []) >= MIN_PIECES]
    for p in kept[:8] if not a.yes else []:
        print(f"  {p['style']:11} {p['department']:5} {len(p['tagged'])} pieces  {p['title'][:50]}")
    print(f"kept {len(kept)} outfits of {len(tagged)} (dropped {len(tagged) - len(kept)} with < {MIN_PIECES} pieces)")
    if not a.yes:
        print("Dry run: nothing written. Re-run with --yes to save.")
        return 0
    pins = sorted([*done.values(), *kept], key=lambda p: (p["style"], p["department"], p["id"]))
    SNAPSHOT.write_text(json.dumps(pins, indent=1, ensure_ascii=False) + "\n")
    print(f"snapshot: {len(pins)} pins -> {SNAPSHOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
