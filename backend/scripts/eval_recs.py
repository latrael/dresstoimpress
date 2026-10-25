"""Recommendation eval: stability, rule validity, Fit Score calibration, latency and cost.

    set -a; . ./.env; set +a
    .venv/bin/python -m scripts.eval_recs --out data/eval_before.json          # real LLM, ~$0.30
    .venv/bin/python -m scripts.eval_recs --out data/eval_after.json --runs 3
    .venv/bin/python -m scripts.eval_recs --compare data/eval_before.json data/eval_after.json

Cases: every user with a closet plus three synthetic closets, x 4 fixed candidate pools (seeded), so the same
products are ranked each time. pair() runs with its caches off so each run is a fresh ranking.
Metrics: top-5 Jaccard and Spearman between repeated runs; % cards whose reason names a closet item the user
doesn't own; % cards whose pairs_with clashes (athletic<->formal, 3+ formality steps) or shares the product's
category; complete_look / closet_picks stability + clashes; Fit Score spread vs the v2 calibration targets.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from typing import Any

from app.store import store

SEED = 7
POOL = 30
POOLS_PER_USER = 4
K = 10

SYNTHETIC = {
    "u_eval_min": {"style_text": "minimalist, neutral, clean", "closet": [
        ("white tee", "top", "white", "solid", ["minimalist"], 2), ("black trousers", "bottom", "black", "solid", ["minimalist"], 3),
        ("white sneakers", "shoes", "white", "solid", ["minimalist"], 2)]},
    "u_eval_gym": {"style_text": "athleisure, sporty", "closet": [
        ("grey athletic tee", "top", "grey", "solid", ["athleisure"], 1), ("black joggers", "bottom", "black", "solid", ["athleisure"], 1),
        ("running shoes", "shoes", "black", "solid", ["athleisure"], 1), ("zip hoodie", "outerwear", "grey", "solid", ["athleisure"], 1)]},
    "u_eval_biz": {"style_text": "business, classic", "closet": [
        ("navy blazer", "outerwear", "navy", "solid", ["business", "classic"], 5), ("white oxford shirt", "top", "white", "solid", ["business"], 4),
        ("grey wool trousers", "bottom", "grey", "solid", ["business"], 5), ("black leather belt", "accessory", "black", "solid", ["business"], 5),
        ("brown loafers", "shoes", "brown", "solid", ["classic"], 4)]},
}


def _ensure_synthetic() -> None:
    for uid, spec in SYNTHETIC.items():
        if store.get("users", uid):
            continue
        store.put("users", uid, {"id": uid, "name": uid, "style_text": spec["style_text"], "price_ranges": {}})
        for i, (label, cat, color, pattern, tags, formality) in enumerate(spec["closet"]):
            store.put("closet_items", f"{uid}_c{i}", {
                "id": f"{uid}_c{i}", "user_id": uid, "label": label, "category": cat, "color": color,
                "pattern": pattern, "style_tags": tags, "formality": formality, "image_url": "", "brand": None})


def _cases() -> list[dict]:
    from app.ai.compat import list_products
    _ensure_synthetic()
    products = sorted(list_products(), key=lambda p: p["id"])
    users = [u["id"] for u in store.list("users") if store.list("closet_items", user_id=u["id"])]
    rng = random.Random(SEED)
    cases = []
    for uid in sorted(users):
        for j in range(POOLS_PER_USER):
            pool = rng.sample(products, POOL)
            cases.append({"user_id": uid, "pool": [p["id"] for p in pool], "case": f"{uid}#{j}"})
    return cases


def _no_cache(service) -> None:
    orig_get = service.store.get

    def get(coll, key, *a, **kw):
        if coll == "pair_cache":
            return None
        return orig_get(coll, key, *a, **kw)

    service.store.get = get
    service._remember = lambda *a, **kw: None
    service._refresh_later = lambda *a, **kw: None


def _jaccard(a: list[str], b: list[str], n: int = 5) -> float:
    sa, sb = set(a[:n]), set(b[:n])
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0


def _spearman(a: list[str], b: list[str]) -> float:
    common = [x for x in a if x in b]
    if len(common) < 3:
        return 1.0 if a[:3] == b[:3] else 0.0
    ra = {x: i for i, x in enumerate(a)}
    rb = {x: i for i, x in enumerate(b)}
    n = len(common)
    d2 = sum((ra[x] - rb[x]) ** 2 for x in common)
    return 1 - 6 * d2 / (n * (n * n - 1))


def _closet_repr(c: dict) -> dict:
    return {"category": c.get("category"), "color": c.get("color"), "pattern": c.get("pattern"),
            "style_tags": c.get("style_tags") or [], "formality": c.get("formality"), "label": c.get("label")}


def eval_pair(runs: int) -> dict:
    from app.ai import service
    from app.ai.complete_look import _as_closet_shape, clashes_with
    from app.ai.compat import get_product
    from app.ai.llm import usage

    _no_cache(service)
    cases = _cases()
    u0 = usage()
    jac, spear, lat = [], [], []
    cards = bad_ref = clash = same_cat = empty_pairs = budget_viol = 0
    per_case = []
    for case in cases:
        closet = store.list("closet_items", user_id=case["user_id"])
        by_id = {c["id"]: c for c in closet}
        outs = []
        for _ in range(runs):
            t = time.perf_counter()
            res = service.pair(case["user_id"], case["pool"], k=K)
            lat.append(time.perf_counter() - t)
            outs.append(res)
        ids = [[r.product_id for r in o] for o in outs]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                jac.append(_jaccard(ids[i], ids[j]))
                spear.append(_spearman(ids[i], ids[j]))
        for r in outs[0]:
            cards += 1
            p = get_product(r.product_id) or {}
            prep = _as_closet_shape(p, "catalog")
            if service._unknown_closet_ref(r.reason, closet):
                bad_ref += 1
            if not r.pairs_with:
                empty_pairs += 1
            for cid in r.pairs_with:
                c = by_id.get(cid)
                if not c:
                    continue
                if clashes_with(prep, _closet_repr(c)):
                    clash += 1
                    break
                if c.get("category") == p.get("category") and p.get("category") != "accessory":
                    same_cat += 1
                    break
        per_case.append({"case": case["case"], "top5": ids[0][:5], "jaccard": round(statistics.mean(jac[-3:]), 3) if runs > 1 else None})
    u1 = usage()
    return {
        "cases": len(cases), "runs": runs, "cards": cards,
        "top5_jaccard": round(statistics.mean(jac), 3) if jac else None,
        "spearman": round(statistics.mean(spear), 3) if spear else None,
        "bad_closet_ref_pct": round(100 * bad_ref / max(cards, 1), 1),
        "clash_pct": round(100 * clash / max(cards, 1), 1),
        "same_category_pct": round(100 * same_cat / max(cards, 1), 1),
        "empty_pairs_with_pct": round(100 * empty_pairs / max(cards, 1), 1),
        "latency_p50_s": round(statistics.median(lat), 2), "latency_p95_s": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 2),
        "llm_calls": u1["claude_calls"] - u0["claude_calls"],
        "usd": round(u1["est_usd"] - u0["est_usd"], 4),
        "usd_per_call": round((u1["est_usd"] - u0["est_usd"]) / max(len(lat), 1), 5),
        "per_case": per_case,
    }


def eval_rules(runs: int) -> dict:
    """complete_look and closet_picks: deterministic by design, so stability must be 1.0; count clashes."""
    from app.ai.complete_look import _as_closet_shape, clashes_with, complete_look
    from app.ai.compat import get_product, list_products
    from app.ai.feed_tryon import closet_picks

    _ensure_synthetic()
    products = sorted(list_products(), key=lambda p: p["id"])
    rng = random.Random(SEED + 1)
    anchors = rng.sample(products, 40)
    users = ["u_adam", "u_eval_gym", "u_eval_biz"]
    cl_stable = cp_stable = n = 0
    cl_clash = cp_clash = cp_dupcat = 0
    cl_items = cp_items = 0
    t0 = time.perf_counter()
    for uid in users:
        closet = store.list("closet_items", user_id=uid)
        catalog = rng.sample(products, 300)
        for a in anchors[:15]:
            arep = _as_closet_shape(a, "catalog")
            cls = [complete_look(a, closet, catalog, style_text="") for _ in range(runs)]
            cps = [closet_picks(uid, a, k=4) for _ in range(runs)]
            n += 1
            cl_stable += all(json.dumps(c["items"], sort_keys=True) == json.dumps(cls[0]["items"], sort_keys=True) for c in cls)
            cp_stable += all([x["id"] for x in c] == [x["id"] for x in cps[0]] for c in cps)
            by_id = {c["id"]: c for c in closet}
            for it in cls[0]["items"]:
                cl_items += 1
                rep = _closet_repr(by_id[it["id"]]) if it["source"] == "closet" and it["id"] in by_id else \
                    _as_closet_shape(get_product(it["id"]) or {}, "catalog")
                cl_clash += clashes_with(arep, rep)
            cats = [x["category"] for x in cps[0]]
            cp_dupcat += len(cats) != len(set(cats))
            for x in cps[0]:
                cp_items += 1
                cp_clash += clashes_with(arep, _closet_repr(by_id.get(x["id"], {})))
    return {
        "anchors": n, "complete_look_stable_pct": round(100 * cl_stable / n, 1), "closet_picks_stable_pct": round(100 * cp_stable / n, 1),
        "complete_look_clash_pct": round(100 * cl_clash / max(cl_items, 1), 1),
        "closet_picks_clash_pct": round(100 * cp_clash / max(cp_items, 1), 1),
        "closet_picks_dup_category_pct": round(100 * cp_dupcat / n, 1),
        "latency_per_anchor_ms": round(1000 * (time.perf_counter() - t0) / (n * runs * 2), 1),
    }


def eval_fit_score() -> dict:
    """Rules-only Fit Score on 300 random outfits and on 45 complete_look outfits vs the v2 targets."""
    from app.ai.complete_look import _as_closet_shape, complete_look
    from app.ai.compat import get_product, list_products
    from app.ai.outfit_score import score_outfit

    products = sorted(list_products(), key=lambda p: p["id"])
    by_cat: dict[str, list] = {}
    for p in products:
        by_cat.setdefault(p["category"], []).append(p)
    rng = random.Random(SEED + 2)
    rand = []
    for _ in range(300):
        items = [_as_closet_shape(rng.choice(by_cat[c]), "catalog") for c in ("top", "bottom", "shoes")]
        rand.append(score_outfit(items, use_ai=False)["score"])
    cur = []
    catalog = rng.sample(products, 400)
    for a in rng.sample(products, 45):
        cl = complete_look(a, [], catalog)
        items = [_as_closet_shape(a, "catalog")] + [_as_closet_shape(get_product(i["id"]) or {}, "catalog") for i in cl["items"]]
        cur.append(score_outfit(items, use_ai=False)["score"])

    def spread(xs):
        return {"median": statistics.median(xs), "pct_80plus": round(100 * sum(x >= 80 for x in xs) / len(xs), 1),
                "pct_90plus": round(100 * sum(x >= 90 for x in xs) / len(xs), 1), "stdev": round(statistics.pstdev(xs), 1)}

    return {"random": spread(rand), "random_targets": {"median": 49, "pct_80plus": 5, "pct_90plus": 0},
            "curated": spread(cur), "curated_targets": {"median": 77}}


def compare(before: dict, after: dict) -> str:
    rows = [("pair top-5 Jaccard (↑)", "pair", "top5_jaccard"), ("pair Spearman (↑)", "pair", "spearman"),
            ("pair bad closet ref % (↓)", "pair", "bad_closet_ref_pct"), ("pair clash % (↓)", "pair", "clash_pct"),
            ("pair same-category % (↓)", "pair", "same_category_pct"), ("pair empty pairs_with % (↓)", "pair", "empty_pairs_with_pct"),
            ("pair latency p50 s (↓)", "pair", "latency_p50_s"), ("pair latency p95 s (↓)", "pair", "latency_p95_s"),
            ("pair $ per call (↓)", "pair", "usd_per_call"),
            ("complete_look stable % (↑)", "rules", "complete_look_stable_pct"), ("complete_look clash % (↓)", "rules", "complete_look_clash_pct"),
            ("closet_picks stable % (↑)", "rules", "closet_picks_stable_pct"), ("closet_picks clash % (↓)", "rules", "closet_picks_clash_pct"),
            ("closet_picks dup category % (↓)", "rules", "closet_picks_dup_category_pct")]
    out = ["| metric | before | after |", "| --- | --- | --- |"]
    for label, sec, key in rows:
        out.append(f"| {label} | {before[sec].get(key)} | {after[sec].get(key)} |")
    for name in ("random", "curated"):
        b, a = before["fit_score"][name], after["fit_score"][name]
        out.append(f"| fit score {name} median / %80+ / %90+ | {b['median']} / {b['pct_80plus']} / {b['pct_90plus']} | {a['median']} / {a['pct_80plus']} / {a['pct_90plus']} |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--skip-pair", action="store_true")
    ap.add_argument("--compare", nargs=2)
    args = ap.parse_args()
    if args.compare:
        b, a = (json.load(open(f)) for f in args.compare)
        print(compare(b, a))
        return
    res: dict[str, Any] = {"rules": eval_rules(args.runs), "fit_score": eval_fit_score()}
    if not args.skip_pair:
        res["pair"] = eval_pair(args.runs)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_case"} for k, v in res.items()}, indent=1))
    if args.out:
        json.dump(res, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
