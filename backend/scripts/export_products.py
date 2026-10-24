"""Write the store's ingest products to seed/products.json (commit it after a fresh ingest).

    python -m scripts.ingest && python -m scripts.export_products
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.load_products import SEED


def export(store, path: Path = SEED) -> list[dict]:
    from app.models import Product
    products = sorted(store.list("products", source="ingest"), key=lambda p: p["id"])
    for p in products:
        Product.model_validate(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(products, indent=1, ensure_ascii=False) + "\n")
    return products


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", type=Path, default=SEED)
    a = ap.parse_args(argv)
    from app.store import store
    print(f"exported {len(export(store, a.file))} ingest products -> {a.file}")


if __name__ == "__main__":
    main()
