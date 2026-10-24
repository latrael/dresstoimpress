"""Load the committed real catalog (seed/products.json) into the store. Safe to re-run.

    python -m scripts.load_products                  # upsert 370 H&M/Uniqlo products, drop seed_demo placeholders
    python -m scripts.load_products --replace        # also drop ingest products not in the snapshot
    python -m scripts.load_products --keep-seed-demo # keep the 5 picsum placeholders
Works with the JSON store and Firestore (USE_FIRESTORE=1).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "seed" / "products.json"


def delete(store, ids: list[str]) -> None:
    if not ids:
        return
    if hasattr(store, "db"):  # FirestoreStore
        for i in ids:
            store.db.collection("products").document(i).delete()
        return
    with store._lock:  # JsonStore has no delete; edit the file directly
        data = store._load("products")
        for i in ids:
            data.pop(i, None)
        store._path("products").write_text(json.dumps(data, indent=2))


def load(store, path: Path = SEED, replace: bool = False, keep_seed_demo: bool = False) -> list[dict]:
    products = json.loads(path.read_text())
    ids = {p["id"] for p in products}
    drop = [] if keep_seed_demo else [p["id"] for p in store.list("products", source="seed")]
    if replace:
        drop += [p["id"] for p in store.list("products", source="ingest") if p["id"] not in ids]
    delete(store, drop)
    for p in products:
        store.put("products", p["id"], p)
    return products


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", type=Path, default=SEED)
    ap.add_argument("--replace", action="store_true", help="drop existing ingest products first")
    ap.add_argument("--keep-seed-demo", action="store_true", help="keep scripts.seed_demo placeholder products")
    a = ap.parse_args(argv)

    from app.store import store
    products = load(store, a.file, a.replace, a.keep_seed_demo)
    print(f"loaded {len(products)} products; store now has {len(store.list('products'))}")
    print("by retailer:", dict(Counter(p["retailer"] for p in products).most_common()))
    print("by category:", dict(Counter(p["category"] for p in products).most_common()))


if __name__ == "__main__":
    main()
