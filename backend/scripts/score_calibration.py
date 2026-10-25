"""Fit Score v2 calibration check: score distribution on random vs curated outfits from the snapshot catalog.

    cd backend && python -m scripts.score_calibration [--n-random 300] [--n-curated 30] [--seed 7] [--raw]

Targets (docs in app/ai/outfit_score.py): random median 60-75, %>=80 under 35, %>=90 under 3;
curated median 78-89, clearly above random. `--raw` prints the pre-calibration raw as well, to refit CALIBRATION.
tests/test_score_calibration.py runs a small fixed version of this.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from app.ai.outfit_score import STYLES, score_outfit
from app.ai.colors import normalize_color

SEED_PRODUCTS = Path(__file__).resolve().parents[1] / "seed" / "products.json"


def _item(p: dict[str, Any]) -> dict[str, Any]:
    return {"category": p.get("category"), "color": (p.get("colors") or [""])[0], "pattern": p.get("pattern"),
            "formality": p.get("formality"), "style_tags": p.get("style_tags", []),
            "label": p.get("label") or p.get("name")}


def load_catalog(path: Path = SEED_PRODUCTS) -> dict[str, list[dict[str, Any]]]:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for p in json.loads(path.read_text()):
        if p.get("category") in ("top", "bottom", "shoes", "outerwear", "accessory"):
            by_cat.setdefault(p["category"], []).append(_item(p))
    return by_cat


def random_outfit(rng: random.Random, cat: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One top, one bottom, shoes, optional outerwear / accessory; styles whatever the pieces happen to be."""
    out = [rng.choice(cat["top"]), rng.choice(cat["bottom"]), rng.choice(cat["shoes"])]
    if rng.random() < 0.4:
        out.append(rng.choice(cat["outerwear"]))
    if rng.random() < 0.3:
        out.append(rng.choice(cat["accessory"]))
    return out


def _accents(items: list[dict[str, Any]]) -> int:
    return len({normalize_color(it["color"])["name"] for it in items
                if normalize_color(it["color"])["family"] not in ("neutral", "unknown")})


def curated_outfit(rng: random.Random, cat: dict[str, list[dict[str, Any]]], style: str | None = None) -> list[dict[str, Any]]:
    """Same dominant style tag on every piece, <= 3 colours (<= 1 accent), formality within one step,
    at most one print, one extra piece."""
    style = style or rng.choice(STYLES)
    pool = {c: [it for it in its if style in it["style_tags"]] for c, its in cat.items()}
    for _ in range(400):
        base = [rng.choice(pool["top"] or cat["top"]), rng.choice(pool["bottom"] or cat["bottom"]),
                rng.choice(pool["shoes"] or cat["shoes"])]
        extra_pool = pool["outerwear"] + pool["accessory"]
        out = base + ([rng.choice(extra_pool)] if extra_pool and rng.random() < 0.7 else [])
        forms = [it["formality"] for it in out if it["formality"] is not None]
        if forms and max(forms) - min(forms) > 1:
            continue
        if _accents(out) > 1 or len({it["color"].lower() for it in out}) > 3:
            continue
        if sum(1 for it in out if it["pattern"] in ("striped", "plaid", "graphic", "floral")) > 1:
            continue
        return out
    return base


def summarize(scores: list[int]) -> dict[str, float]:
    s = sorted(scores)
    n = len(s)
    q = lambda p: s[min(n - 1, int(p * n))]  # noqa: E731
    return {"n": n, "mean": round(sum(s) / n, 1), "p10": q(0.10), "p50": q(0.50), "p90": q(0.90),
            "pct_80": round(100 * sum(x >= 80 for x in s) / n, 1), "pct_90": round(100 * sum(x >= 90 for x in s) / n, 1)}


def run(n_random: int = 300, n_curated: int = 30, seed: int = 7, catalog: dict | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    cat = catalog or load_catalog()
    rand = [score_outfit(random_outfit(rng, cat), use_ai=False) for _ in range(n_random)]
    cur = [score_outfit(curated_outfit(rng, cat, STYLES[i % len(STYLES)]), use_ai=False) for i in range(n_curated)]
    return {"random": summarize([r["score"] for r in rand]), "curated": summarize([r["score"] for r in cur]),
            "random_raw": summarize([r["raw_score"] for r in rand]), "curated_raw": summarize([r["raw_score"] for r in cur]),
            "random_styles": sorted(((r["primary_style"] for r in rand)), key=str)}


def meets_targets(res: dict[str, Any]) -> list[str]:
    r, c = res["random"], res["curated"]
    fails = []
    if not 60 <= r["p50"] <= 75:
        fails.append(f"random median {r['p50']} not in 60-75")
    if r["pct_80"] >= 35:
        fails.append(f"random %>=80 {r['pct_80']} not under 35")
    if r["pct_90"] >= 3:
        fails.append(f"random %>=90 {r['pct_90']} not under 3")
    if not 78 <= c["p50"] <= 89:
        fails.append(f"curated median {c['p50']} not in 78-89")
    if c["p50"] < r["p50"] + 10:
        fails.append("curated median must exceed random by at least 10")
    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-random", type=int, default=300)
    ap.add_argument("--n-curated", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--raw", action="store_true", help="also print the pre-calibration raw distributions")
    a = ap.parse_args()
    res = run(a.n_random, a.n_curated, a.seed)
    for k in ("random", "curated") + (("random_raw", "curated_raw") if a.raw else ()):
        print(f"{k:12s} {res[k]}")
    from collections import Counter
    print("primary styles (random):", dict(Counter(res["random_styles"]).most_common()))
    fails = meets_targets(res)
    print("targets:", "all met" if not fails else "; ".join(fails))


if __name__ == "__main__":
    main()
