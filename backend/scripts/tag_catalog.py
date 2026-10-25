"""Catalog stage 2: AI tags (label / pattern / formality / style_tags), `summary` and a `department`
fallback on ingest products.

    python -m scripts.tag_catalog --limit 5         # try a few first, prints what it got
    python -m scripts.tag_catalog                   # everything still untagged or without a summary
    python -m scripts.tag_catalog --all             # re-tag even products that already have a label
    python -m scripts.tag_catalog --summaries-only  # only fill `summary` where it is missing (no tagging)
    python -m scripts.tag_catalog --departments-only  # only fill `department` where null: rules, then AI
    python -m scripts.export_products               # then write seed/products.json and commit it

Tags use the product name as a hint, so an H&M photo of a model in a full outfit is tagged as the
item being sold. Category stays Nabil's rule-based one unless it is missing. Summaries (sprint-2 B4):
Haiku condenses the retailer description, or writes a one-liner from the attributes when there is
none (H&M). Department (B5 gap 3): never overwrites a non-null value; rules from the name / URL /
H&M category code first, then the tagger's answer. Everything is cached (tags per image + name,
summaries per product id + SUMMARY_VERSION), so re-runs are free. Stops cleanly at AI_BUDGET_USD.
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from dotenv import load_dotenv

load_dotenv()

from app.ai.llm import text_mock, usage  # noqa: E402
from app.ai.service import department_from_text, summarize_product, tag_product  # noqa: E402
from app.store import store  # noqa: E402

FIELDS = ("label", "pattern", "formality", "style_tags")


def rules_department(p: dict) -> str | None:
    """Department from the name, product URL and (H&M) category code; None when they don't say."""
    return department_from_text(p.get("name"), p.get("product_url"), p.get("category_code"))


def tag_one(p: dict, retag: bool = False) -> tuple[dict, str | None]:
    """Tags (when missing, or `retag`) + department fallback + summary for one product.
    Returns (updated product, error name)."""
    q, t = dict(p), {}
    if retag or not p.get("label"):
        try:
            t = tag_product(p["image_url"], hint=p.get("name"))
        except Exception as e:  # noqa: BLE001  NotClothing, model error, budget
            return p, type(e).__name__
        q.update({k: t[k] for k in FIELDS})
        q["category"] = p.get("category") or t["category"]
    if not q.get("department"):
        q["department"] = rules_department(q) or t.get("department")
    if not q.get("summary"):
        q, err = summarize_one(q)
        if err:
            return q, err
    return q, None


def summarize_one(p: dict) -> tuple[dict, str | None]:
    try:
        return {**p, "summary": summarize_product(p)}, None
    except Exception as e:  # noqa: BLE001
        return p, type(e).__name__


def department_one(p: dict) -> tuple[dict, str | None]:
    """Rules first (free); the tagger only for products the rules can't place."""
    if p.get("department"):
        return p, None
    if dept := rules_department(p):
        return {**p, "department": dept}, None
    try:
        t = tag_product(p["image_url"], hint=p.get("name"))
    except Exception as e:  # noqa: BLE001
        return p, type(e).__name__
    return {**p, "department": t.get("department")}, None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="process at most N products (0 = all)")
    ap.add_argument("--all", action="store_true", help="re-tag products that already have a label")
    ap.add_argument("--summaries-only", action="store_true", help="only fill missing `summary` (no tagging)")
    ap.add_argument("--departments-only", action="store_true",
                    help="only fill null `department`: name/URL rules first, the tagger for the rest")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    if a.summaries_only and a.departments_only:
        raise SystemExit("pick one of --summaries-only / --departments-only")
    if text_mock() and not a.summaries_only:
        raise SystemExit("MOCK_AI is on (or no AI key): the tagger would return a fixed answer. Aborting.")
    if text_mock():
        print("MOCK_AI is on: summaries come from the attributes template, not Haiku")

    products = store.list("products", source="ingest")
    if a.summaries_only:
        todo, work, what = [p for p in products if not p.get("summary")], summarize_one, "summarizing"
    elif a.departments_only:
        todo, work, what = [p for p in products if not p.get("department")], department_one, "placing"
    else:
        todo = [p for p in products if a.all or not p.get("label") or not p.get("summary")]
        work, what = partial(tag_one, retag=a.all), "tagging"
    todo.sort(key=lambda p: p["id"])
    if a.limit:
        todo = todo[: a.limit]
    print(f"{what} {len(todo)} products with {a.workers} workers")
    start, spent0, errors, changed = time.time(), usage()["est_usd"], Counter(), 0
    with ThreadPoolExecutor(a.workers) as ex:
        for i, (p, err) in enumerate(ex.map(work, todo), 1):
            if err:
                errors[err] += 1
                continue
            store.put("products", p["id"], p)
            changed += 1
            if a.limit or i % 25 == 0:
                print(f"  {i}/{len(todo)} {p['id']}: {p.get('label')!r} {p.get('department')} "
                      f"{p.get('style_tags')} | {p.get('summary')!r}")
    print(f"done: {changed} updated in {time.time() - start:.0f}s, est ${usage()['est_usd'] - spent0:.4f}, "
          f"errors {dict(errors)}")


if __name__ == "__main__":
    main()
