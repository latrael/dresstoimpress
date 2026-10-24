"""Add Product.department to seed/products.json from the saved raw scrapes (seed/raw/*.json.gz). No network.

    python -m scripts.backfill_department     # then python -m scripts.load_products to update the store
Matches raw items to products by id (H&M article id, Uniqlo productId) and sets only `department`; every
other key (AI tags included) stays as it is. Same JSON formatting as scripts.export_products. Safe to re-run.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

from app.commerce.ingest import hm_department, uniqlo_department
from scripts.load_products import SEED

RAW = SEED.parent / "raw"


def departments(raw_dir: Path = RAW) -> dict[tuple[str, str], str | None]:
    """(retailer, product code) -> department, from every raw file (hm*, uniqlo*)."""
    out: dict[tuple[str, str], str | None] = {}
    for f in sorted(raw_dir.glob("*.json.gz")):
        items = json.loads(gzip.decompress(f.read_bytes()))
        if f.name.startswith("hm"):
            out.update({("hm", str(it["id"])): hm_department(str(it.get("category") or ""))
                        for it in items if it.get("id")})
        elif f.name.startswith("uniqlo"):
            out.update({("uniqlo", str(it["productId"])): uniqlo_department(it)
                        for it in items if it.get("productId")})
    return out


def backfill(products: list[dict], depts: dict[tuple[str, str], str | None]) -> list[dict]:
    """Set `department` in place (None when the raw item is missing or doesn't say)."""
    for p in products:
        p["department"] = depts.get((p["retailer"], p["id"].split(":")[1]))
    return products


def main(path: Path = SEED) -> None:
    products = backfill(json.loads(path.read_text()), departments())
    path.write_text(json.dumps(products, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(products)} products:", dict(Counter(str(p["department"]) for p in products).most_common()))


if __name__ == "__main__":
    main()
