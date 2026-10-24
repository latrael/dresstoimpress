"""AI tag pass over the catalog: fill label / pattern / formality / style_tags on ingest products.

    python -m scripts.tag_catalog --limit 5      # try a few first, prints what it got
    python -m scripts.tag_catalog                # everything still untagged (~$0.0002 each on Haiku)
    python -m scripts.tag_catalog --all          # re-tag even products that already have a label
    python -m scripts.export_products            # then write seed/products.json and commit it

Uses the product name as a hint, so an H&M photo of a model in a full outfit is tagged as the
item being sold. Category stays Nabil's rule-based one unless it is missing. Cached per image +
name, so re-runs are free. Stops cleanly at the AI_BUDGET_USD cap.
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

load_dotenv()

from app.ai.llm import text_mock, usage  # noqa: E402
from app.ai.service import tag_product  # noqa: E402
from app.store import store  # noqa: E402

FIELDS = ("label", "pattern", "formality", "style_tags")


def tag_one(p: dict) -> tuple[dict, str | None]:
    try:
        t = tag_product(p["image_url"], hint=p.get("name"))
    except Exception as e:  # noqa: BLE001  NotClothing, model error, budget
        return p, type(e).__name__
    q = {**p, **{k: t[k] for k in FIELDS}}
    q["category"] = p.get("category") or t["category"]
    return q, None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="tag at most N products (0 = all)")
    ap.add_argument("--all", action="store_true", help="re-tag products that already have a label")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    if text_mock():
        raise SystemExit("MOCK_AI is on (or no AI key): the tagger would return a fixed answer. Aborting.")

    todo = [p for p in store.list("products", source="ingest") if a.all or not p.get("label")]
    todo.sort(key=lambda p: p["id"])
    if a.limit:
        todo = todo[: a.limit]
    print(f"tagging {len(todo)} products with {a.workers} workers")
    start, spent0, errors = time.time(), usage()["est_usd"], Counter()
    with ThreadPoolExecutor(a.workers) as ex:
        for i, (p, err) in enumerate(ex.map(tag_one, todo), 1):
            if err:
                errors[err] += 1
                continue
            store.put("products", p["id"], p)
            if a.limit or i % 25 == 0:
                print(f"  {i}/{len(todo)} {p['id']}: {p['label']!r} {p['pattern']} f{p['formality']} {p['style_tags']}")
    print(f"done in {time.time() - start:.0f}s, est ${usage()['est_usd'] - spent0:.4f}, errors {dict(errors)}")


if __name__ == "__main__":
    main()
