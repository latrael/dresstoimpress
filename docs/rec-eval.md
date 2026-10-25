# Recommendation robustness: eval, changes, market-readiness

Sun Oct 25, 2026, ~2 AM PT. Adam's lane. Harness: `backend/scripts/eval_recs.py` (run it before and after any change
to `pair()`, `complete_look`, `closet_picks` or Fit Score).

```
cd backend && set -a; . ./.env; set +a
PAIR_REUSE=0 .venv/bin/python -m scripts.eval_recs --out data/eval_after.json --runs 3    # real Claude, ~$0.05
.venv/bin/python -m scripts.eval_recs --compare data/eval_before.json data/eval_after.json
```

**What it measures.** 20 cases (u_adam, u_nabil + 3 synthetic closets: minimalist, gym, business) × 4 fixed
30-product pools (seed 7), each ranked 3× with the pair caches off. Stability = top-5 Jaccard and Spearman between
runs. Validity = % cards whose `pairs_with` clashes with the product (athletic↔formal, ≥3 formality steps) or is the
same category, % reasons naming a closet item the user doesn't own. Plus `complete_look` / `closet_picks` stability
and clashes on 45 anchors, and the rules-only Fit Score on 300 random top+bottom+shoes trios and 45 complete-look outfits.

## Before → after (Claude Haiku 5.5, 60 calls per run)

| metric | before | after |
| --- | --- | --- |
| pair top-5 Jaccard (↑) | 0.61 | **0.75** |
| pair Spearman (↑) | 0.52 | **0.74** |
| pair clash % (↓) | 11.0 | **0.0** |
| pair same-category pairing % (↓) | 19.0 | **0.0** |
| pair bad closet ref % (↓) | 0.0 | 0.0 |
| pair empty pairs_with % | 0.0 | 1.5 |
| pair latency p50 / p95 s | 3.99 / 4.85 | 3.96 / 4.55 |
| pair $ per call | 0.00087 | 0.00077 |
| complete_look stable % / clash % | 100 / 0 | 100 / 0 |
| closet_picks stable % / clash % / dup-category % | 100 / 0 / 0 | 100 / 0 / 0 |
| Fit Score random trios: median / %80+ / %90+ (targets 49 / 5 / 0) | 75 / 31 / 0 | 75 / 31 / 0 |
| Fit Score complete-look outfits: median (target 77) | 87 | 87 |

Weight sweep: `PAIR_LLM_WEIGHT=0.3` gave Jaccard 0.68 / Spearman 0.64 on the same cases, 0.5 gave 0.75 / 0.74, so
run-to-run noise on 20 cases is about ±0.06; 0.5 stays the default. The validity gains (0% clashes, 0% same-category)
are exact, not statistical.

## What changed (`backend/app/ai/service.py`, `llm.py`, `prompts.py` v5)

1. **Rules first, Claude second.** Every candidate is scored by the outfit rules (free, deterministic). Claude only
   re-ranks and explains a shortlist of `PAIR_SHORTLIST` (20, ≥ k) rules-ranked candidates instead of 30–50. Final
   score = `PAIR_LLM_WEIGHT` (0.5) × Claude + 0.5 × rules; ties break on rules score, then product id. Same inputs
   → same order. Prompt is ~40% smaller.
2. **Hard validators on every card.** `pairs_with` drops closet items that clash with the product or share its
   category. If Claude's pairing was built on a clashing item, its reason was about that item too, so the rules'
   reason and pairing replace it. The rules fallback goes through the same filter (it was 9% clashes on its own).
3. **Claude calls were silently dead since #67.** `anthropic` 2.x's `messages.create()` no longer takes
   `temperature`; every call raised, fell back to Gemini, which is **out of prepaid credits (402)**, so the whole
   feed ran on rules. Fixed: temperature goes through `extra_body` and is dropped if the SDK/model rejects it.
   **Gemini is still at 402: try-ons, clean shots and photo tagging fail until credits are topped up.**
4. Caches: `PAIR_VERSION` v5 so banked v4 rankings are not mixed with the new scores.

Not changed: the Fit Score calibration curve. The eval says random catalog trios get a median of 75 and 31% land
at 80+, against the v2 targets of 49 / 5%. The curve was deliberately softened in #60 ("coherent everyday
outfits read as wearable") and tests pin it; the targets written in `outfit_score.py` are stale. Decide as a team
whether the badge is a percentile or a "wearable" grade before touching it.

## Market-readiness (frank)

**Demo-ready.** Rules + validators mean nothing on a feed card is a hard clash, no reason names a garment the user
doesn't own, and re-opening the feed gives the same order. `complete_look` and `closet_picks` are deterministic and
clash-free. Cost is negligible: ~$0.0008 per ranking call, ~$0.04 per image.

**What breaks with real users.**
- **Cold start:** an empty closet puts `pair()` on rules + style text only; reasons become generic ("Matches your
  style"). ~1 in 2 new users will never upload a closet. Need a 3-question style quiz → synthetic closet seed.
- **Catalog coverage:** 3,188 products, but shoes are 168 (all H&M), 7 of 8 stores have no shoes or accessories,
  and women 1,727 / men 1,170. `complete_look` will keep recommending the same few H&M shoes.
- **Latency:** 4 s per uncached ranking (Haiku, 20 candidates). Hidden today by the 10-min cache and the reason
  bank, but a first feed load after a closet change is 4–8 s; the hero image + try-on prefetch add more. Needs the
  ranking to be precomputed per user when the closet changes, not on request.
- **Quality ceiling:** the LLM still swaps ~1 of 5 top picks between identical calls (Jaccard 0.75). Pointwise
  scores from a 20-item list are the limit of this approach; listwise or pairwise re-ranking with a fixed candidate
  order, or 2–3 cheap samples with rank aggregation, is the next step if consistency matters more than $0.002.
- **Rules bias:** `outfit_rules` rewards colour harmony and same-style tags, so a minimalist closet gets a
  minimalist-only feed; nothing explores. Add a small exploration slot (1 in 10 cards).
- **Single points of failure:** one Anthropic key, one Gemini key with prepaid credits, one Mac behind a Cloudflare
  quick tunnel. Gemini is already at 402.
- **No ground truth:** stability and rule-validity are proxies. We have no click/purchase data to know whether the
  ranking is *good*; `/swipe` logs exist and should feed an offline NDCG once there are a few hundred swipes.

## Next steps

1. Top up Gemini credits (or point try-on at another image model) — try-on is dark right now.
2. Precompute the per-user ranking on closet/swipe change (background), serve from cache; target < 300 ms feed.
3. Cold-start: 3-question style quiz → synthetic closet; exploration slot in the feed.
4. Catalog: shoes + accessories from at least 3 more stores (Nabil's scrapers), balance men/women.
5. Fit Score: decide percentile vs wearable grade, then re-fit `CALIBRATION` with the harness; wire `/swipe` into
   an offline NDCG so ranking changes are judged on behaviour, not proxies.
