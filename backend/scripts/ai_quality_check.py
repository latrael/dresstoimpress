"""AI quality check on the live store: feed reasons, shop-the-fit, size advice, catalog tags. Re-run before demos.

    python -m scripts.ai_quality_check            # u_demo; ~4 Claude calls (~$0.01), cached after
    python -m scripts.ai_quality_check --user u_adam

Prints every finding and a summary; exits 1 if any hard check fails. Read-only except the normal caches.
"""
from __future__ import annotations

import argparse
import re
import sys

from dotenv import load_dotenv

load_dotenv()

from app.ai import service  # noqa: E402
from app.ai.compat import get_product, list_products  # noqa: E402
from app.ai.finder import TYPE_GROUPS, item_type  # noqa: E402
from app.ai.sizing import recommend_size  # noqa: E402
from app.store import store  # noqa: E402

BODIES = [("small", 158, 50), ("medium", 172, 68), ("large", 185, 95)]
fails: list[str] = []
warns: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)
    print("  FAIL", msg)


def warn(msg: str) -> None:
    warns.append(msg)
    print("  warn", msg)


def variety_warnings(reasons: list[str], closet_labels: list[str]) -> list[str]:
    """Feed reasons that all sound the same read like a template. Flags an opening (first 3 words)
    used by over a quarter of the reasons, and one closet item named in over 60% of them when the
    closet has 3+ items to choose from."""
    out: list[str] = []
    reasons = [r.lower() for r in reasons if r]
    if len(reasons) < 4:
        return out
    openings: dict[str, int] = {}
    for r in reasons:
        key = " ".join(r.split()[:3])
        openings[key] = openings.get(key, 0) + 1
    top, n = max(openings.items(), key=lambda kv: kv[1])
    if n > len(reasons) / 4:
        out.append(f"{n}/{len(reasons)} reasons start with {top!r}")
    if len(closet_labels) >= 3:
        for lbl in closet_labels:
            hits = sum(1 for r in reasons if lbl.lower() in r)
            if hits > 0.6 * len(reasons):
                out.append(f"{hits}/{len(reasons)} reasons name the same closet item ({lbl!r})")
    return out


def check_feed(user_id: str) -> None:
    print("\n== feed reasons ==")
    user = store.get("users", user_id) or {}
    closet = store.list("closet_items", user_id=user_id)
    labels = {c["id"]: (c.get("label") or "").lower() for c in closet}
    ranges = user.get("price_ranges", {})
    cands = [p["id"] for p in list_products() if p.get("in_stock", True)][:50]
    ranked = service.pair(user_id, cands, k=20)
    print(f"  {len(ranked)} ranked of {len(cands)} candidates; closet: {sorted(labels.values())}")
    if len(ranked) < 20:
        fail(f"pair returned {len(ranked)} < 20")
    for r in ranked:
        p = get_product(r.product_id)
        words = len(r.reason.split())
        mentions = any(lbl and any(w in r.reason.lower() for w in lbl.split() if len(w) > 3) for lbl in labels.values())
        bad_ref = [c for c in r.pairs_with if c not in labels]
        price = p.get("sale_price_usd") or p.get("price_usd")
        rng = ranges.get(p.get("category"))
        in_budget = not rng or rng[0] <= price <= rng[1]
        line = f"{p['name'][:34]:34} ${price:<6} {'in ' if in_budget else 'OUT'} | {r.reason}"
        print("   ", line)
        if not r.reason:
            fail(f"empty reason for {r.product_id}")
        if words > 12:
            fail(f"reason over 12 words ({words}) for {r.product_id}")
        if bad_ref:
            fail(f"pairs_with has ids not in closet: {bad_ref}")
        if closet and not mentions and not r.pairs_with:
            warn(f"reason doesn't name a closet item: {r.product_id}: {r.reason!r}")
    for msg in variety_warnings([r.reason for r in ranked], [lbl for lbl in labels.values() if lbl]):
        warn(msg)
    if ranges:
        flags = []
        for r in ranked:
            p = get_product(r.product_id)
            rng = ranges.get(p.get("category"))
            price = p.get("sale_price_usd") or p.get("price_usd")
            flags.append(not rng or rng[0] <= price <= rng[1])
        # in-budget picks should come before over-budget ones
        if any(not a and b for a, b in zip(flags, flags[1:])):
            warn("an over-budget pick is ranked above an in-budget one")


def check_shop_fit(user_id: str) -> None:
    print("\n== shop the fit ==")
    posts = store.list("fitcheck_posts")
    tags = [t for p in posts for t in p.get("tagged", [])][:9]
    tags += [{"label": "black puffer vest", "category": "outerwear", "color": "black"},
             {"label": "light wash baggy jeans", "category": "bottom", "color": "light blue"},
             {"label": "white leather sneakers", "category": "shoes", "color": "white"},
             {"label": "grey crewneck sweatshirt", "category": "top", "color": "grey"},
             {"label": "olive cargo pants", "category": "bottom", "color": "olive"}]
    for tag in tags:
        tag = {k: v for k, v in tag.items() if k != "product_id"}  # force matching, not the direct link
        hits = service.shop_fit(user_id, [tag])
        want_type = item_type(tag.get("label") or "")
        names = [h["name"] for h in hits]
        print(f"   {tag['label'][:34]:34} -> {names[:3]}")
        for h in hits:
            if tag.get("category") and h.get("category") != tag["category"]:
                fail(f"category mismatch: {tag['label']!r} -> {h['name']!r} ({h.get('category')})")
            if want_type is not None and not (set(re.findall(r'[a-z0-9-]+', h['name'].lower())) & TYPE_GROUPS[want_type]):
                fail(f"type mismatch: {tag['label']!r} -> {h['name']!r}")
        if not hits:
            warn(f"no match for {tag['label']!r}")


def check_sizes() -> None:
    print("\n== size advice ==")
    prods = [p for p in list_products() if p.get("sizes")]
    sample = [p for cat in ("top", "bottom", "outerwear", "dress", "shoes")
              for p in [q for q in prods if q.get("category") == cat][:4]]
    for p in sample:
        out = []
        for name, h, w in BODIES:
            r = recommend_size(p, h, w, shoe_us=9.5 if p["category"] == "shoes" else None)
            out.append(f"{name}:{r['size']}")
            if r["size"] is not None and r["size"] not in p["sizes"]:
                fail(f"recommended a size not in stock: {p['id']} {r['size']}")
            if r["size"] is None:
                warn(f"no size for {p['id']} ({p['category']}, sizes {p['sizes'][:6]}) [{name}]: {r['reason']}")
        print(f"   {p['category']:9} {p['name'][:30]:30} {out}  sizes={p['sizes'][:5]}")


def check_tags() -> None:
    print("\n== catalog tags ==")
    prods = [p for p in list_products() if p.get("source") == "ingest"]  # live-search finds are untagged by design
    untagged = [p["id"] for p in prods if not p.get("label")]
    if untagged:
        warn(f"{len(untagged)} products have no label")
    contradictions = 0
    for p in prods:
        name_t, label_t = item_type(p.get("name") or ""), item_type(p.get("label") or "")
        if name_t is not None and label_t is not None and name_t != label_t:
            contradictions += 1
            if contradictions <= 8:
                warn(f"label type differs from name: {p['name']!r} -> {p.get('label')!r}")
    print(f"   {len(prods)} products, {len(untagged)} unlabeled, {contradictions} label/name type differences")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default="u_demo")
    a = ap.parse_args()
    check_tags()
    check_sizes()
    check_shop_fit(a.user)
    check_feed(a.user)
    print(f"\nSUMMARY: {len(fails)} fail, {len(warns)} warn")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
