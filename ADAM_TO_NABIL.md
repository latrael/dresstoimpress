# ADAM_TO_NABIL.md

Replies from Adam (AI lane) to Nabil (commerce lane). Newest at the top. Nabil's notes: `NABIL_TO_ADAM.md`.

**Last updated:** Fri Oct 23, 2026, ~9:45 PM PT · newest section is on `adam/ai-pipeline` (PR into `staging`), older ones are on `staging`

---

## Oct 23, ~9:45 PM: overseer check of all branches (full report: `docs/progress.md`)

Adam's session checked every branch, PR, test suite and handoff:
- **Your branch is in good shape.** `nabil` (74b7499): **247 tests pass**. The secret scan is clean on all branches and in history.
- **The `/fit` guest page passed review:** off unless `FITCHECK_EVENT_CODE` is set, rate-limited, guest cap, AI tagging under the budget cap, escaped output.
- **Ryan built his Flutter Feed** (`RyanFrontendking`, 4 widget tests) and was waiting on the shared shell. That's now PR **#9** (`flutter-starter`), and his Feed passes analyze + tests inside it.

**Deviations that touch you:**
1. PR #3 went `nabil` → `main` directly. It's fixed, but please keep PRs into `staging` only.
2. **The `/fit` guest page is a user-facing web page,** and Ryan owns all design. Please get his OK on it (in RYAN_TO_NABIL / NABIL_TO_RYAN) before we turn on `FITCHECK_EVENT_CODE` at the table.
3. **NABIL_TO_RYAN has some display guidance** ("show it with the original struck through", "hide the dots", "show `message`"). Please keep notes to Ryan to data facts (shapes, errors, what a field means) and leave how it displays to him. I've removed the same kind of guidance from my own docs.
4. PR #7 contains #8's commits, since you merged `adam/ai-pipeline` in. That's fine: merge #8 first, then #7; there are no conflicts.

**Asks, in order:**
1. Review **#8** and **#9**. Merge #7 after #8.
2. Ryan's OK on `/fit`.
3. Devpost write-up, the README for sponsor judges and the demo script (your track).

After merges, Adam's session restarts the shared server and re-runs the smoke test.

---

## Oct 23, ~9:15 PM: how we proceed from here (please reply in NABIL_TO_ADAM.md)

**Also new:** `pair()` now always returns `k` results with a reason. When Claude ranks fewer, rules-based picks fill the rest. The smoke test's feed still shows 5 of 8 cards with a reason, so `/feed` must be mixing in unranked candidates. Could it prefer the ranked ones, and only use unranked candidates when the ranked ones run out?

**Where things stand:**
- **Backend:** done and live on Adam's Mac through the tunnel. Smoke test 10/10, including your real Nessie checkout, plus 418 tagged products.
- **Fit Check:** 3 demo posts are seeded on the shared server (`seed_fitcheck`), so u_demo's Fit Check feed isn't empty.
- **The risk is now the app.** FlutterFlow is out (API calls need a paid plan), so Ryan continues his FlutterFlow work as **plain Flutter** (`docs/app-plan.md`) and completes the screens himself. iOS comes afterward.

**What Adam does (only he can):**
- Keeps the Mac awake with the tunnel running, and reposts the URL in the group chat if it changes. Keeps the Anthropic credits topped up (thanks for flagging those errors).
- Stays on the AI backend. Keeps `app/lib/core` (API + models) in sync when routes change.
- Builds the iPhone version on his Mac (Xcode, free Apple ID) for the demo.
- Merges PRs when you're both busy. Note: our agents can open PRs but can't merge them; a human has to click Merge.

**What we need from you:**
1. **Merges:** review and merge **#8** (Style DNA + app plan) into `staging`. Your #7 has no conflicts with them.
2. **No app screens for you (or Adam).** Ryan owns the whole Flutter app and is continuing from his FlutterFlow work. You stay on commerce: make `/feed` prefer ranked cards (item at the top), keep Nessie checkout solid, and own the README for sponsor judges, the Devpost write-up and the demo script.
3. **Fit Check seed tags:** `seed_fitcheck` writes tags with only `label` / `retailer` / `product_id`. Please also copy `category`, `color` (the product's `colors[0]`), `pattern` and `style_tags` from the product. Then the Fit Score badge (`POST /ai/fit-score {items: post.tagged}`) has something to score, and shop-the-fit matching is stricter. Your file; Adam won't touch it.
4. **Saturday noon checkpoint:** feed → size → add to cart → checkout `paid`, on a phone. If it's at risk, one of us takes one whole tab from Ryan (agreed in the group chat), never a half-shared screen.

**Order of work tonight:** merge #8 → Ryan gets his Flutter project running against the live backend: Feed → Cart. You: the `/feed` ranked-first fix + seed tags. Adam: AI polish + the iPhone build.

---

## Oct 23, ~8:55 PM: we both tagged the catalog, so PR #6 keeps the name-hinted snapshot

Our passes crossed (your PR #5 and my PR #6). I compared them product by product:
- **Your snapshot:** 37 labels describe what the H&M model wears, not the product. "Baggy Jeans" became "light blue striped shirt", and "Relaxed-Fit Sweater" became "beige wide-leg cargo pants".
- **Mine has 0 of these,** because the tagger gets the product name as a hint.

So PR #6 keeps my `seed/products.json`. It takes your vocabulary finding, though: the tagger itself now drops off-vocabulary style tags ("casual", "retro") for products, closet and Fit Check, and the snapshot is filtered. Your `ingest.tag()` filter stays as a second guard.

PR #6 already contains your PR #5 merge, so it's clean against `staging`. Thanks for the credit-balance heads-up; Adam's checking it.

**After merging:** nothing to run on the Mac (its store already has this snapshot). Elsewhere: `python -m scripts.load_products --replace`.

---

## Oct 23, ~8:45 PM: your PR #3 asks are done; backend is live with your catalog

**Branches:** you merged PR #2 and #3 into `main`. I fast-forwarded `staging` to `main` (it was only behind, with nothing of its own), so `main` = `staging` again. My new work is in **PR `adam/ai-pipeline` → `staging`**. Please merge it; I'm not allowed to merge my own PRs.

**Your asks:**
1. **Memory sees `PUT /wishlist` saves.** `memory._from_store` now reads swipes and the `wishlist` collection (`{user_id, product_id, saved_at}`) together, newest first. The newest action per product wins, so a save followed by a discard counts as a discard.
2. **`_save_upload` keeps its name.** It's in a comment in the router too.
3. **Catalog loaded and tagged on the Mac:**
   - I ran `load_products` (418 products). It also dropped the 5 picsum demo products, as designed.
   - Then I tagged everything with a new script, `scripts/tag_catalog.py`, and committed the result (`export_products`): **418/418 labeled**, ~$0.07.
   - Difference from re-running your ingest: it passes the **product name as a hint** (`tag_product(url, hint=name)`). H&M photos are model shots, and without the name the tagger sometimes describes the model's jeans instead of the tee being sold. Your `ingest.tag()` still works unchanged. I suggest adding `hint=p["name"]` there too (your file, your call).
   - Two stale test products (`hm:1234567001:...` from a fixture run, `test:tee:white`) were sitting in the Mac's store, and they're removed. `tests/conftest.py` now gives tests a temp `DATA_DIR` and blanks every real key, so no test can write to the demo store or hit Apify / Nessie / Claude again.

**Things that touch your code:**
- **Fit Check live search uses your H&M actor.** `jordan-byte~fashion-multi-scraper-us` returns 404 now, so `finder.live_search` calls your `ingest.fetch_hm` + `normalize_hm`.
  - Results get your ids, so a live hit that's already in the catalog keeps the catalog (tagged) copy.
  - New hits are saved with `source: "live_search"` (so `export_products` skips them).
  - Capped at `LIVE_SEARCH_MAX=6` items and cached per query. Please don't rename those two functions.
- **`shop_fit` runs the per-item searches in parallel:** 3 fresh items ~8 s (was ~19 s).
- **`JsonStore.put` writes a temp file and renames it.** In-place writes let a concurrent reader see an empty file. That reset `ai_usage` during the tag pass and could have 500'd a feed request. Your `load_products.delete()` still works. There's now also a real `store.delete(collection, id)` for both stores, if you want to use it.
- **The real Nessie checkout works through the tunnel** (`paid`).
- **`ClosetItem.duplicate_of`** is a new optional field. It's in docs/schema.md.

**Verified:** 193 tests pass; `smoke_e2e` through the tunnel → 10/10.

---

## Decided: shared backend runs on Adam's Mac

- Adam's Mac hosts it (Anthropic + Gemini keys, working Google billing, real try-on). Tunnel URL + shared key go to you and Ryan **privately**; never commit them (public repo).
- New on `staging`: `/static` now serves only `uploads/` and `tryon/` (it used to expose the JSON store), and with `API_SHARED_KEY` set every route except `/health` and `/static/...` needs header `X-DTI-Key`. Your routes are covered automatically; nothing to change. Tests: `scripts/smoke_e2e.py --key ...`.
- **Tagging without sharing the Anthropic key:** when your snapshot + `scripts/load_products` PR lands on `staging`, Adam runs the tag pass on his Mac (where the server lives anyway) and pushes the tagged snapshot. If you'd rather tag before snapshotting, say so and Adam sends the key privately.

## Ready for the first merge `staging` → `main`?

Adam's side says yes: `pytest -q` → 101 passed (your commerce + ingest + AI), and `python -m scripts.smoke_e2e` against a running server → 10/10 (feed with reasons, size, AI try-on, complete the look, swipe → cart, cart by store, checkout, Fit Check). Checklist in `ADAM.md`.
**Please confirm** in `NABIL_TO_ADAM.md`: nothing local unpushed, and OK to merge. Then Adam opens the PR `staging` → `main`.

## Answers to your questions

1. **Fit Check posts:** your shape `{id, user_id, photo_url, caption, tagged: [FitTag], created_at, likes: [], comments: []}` works. Store `tagged` exactly as `/ai/tag-fit` returns it: `FitTag` now also carries `category`, `color`, `pattern`, `style_tags`, `brand` (they were being dropped before, which weakened strict matching). Then `GET /fitcheck/{post_id}/shop` = `ai.service.shop_fit(viewer_id, post["tagged"])`, no extra fields needed.
2. **`APIFY_TOKEN`:** private is right; the repo is public. `.env` is gitignored on all branches.
3. **Shared backend host:** proposal is Adam's Mac (the Anthropic + Gemini keys and the Google billing are there; real try-on works). Adam is confirming the tunnel. When your snapshot PR lands, Adam runs `python -m scripts.load_products` there.
4. **`POST /complete-look`:** the app calls it (where and how is Ryan's call). `/feed` shouldn't.

## Your points that touch my code

- **`/feed` → `pair(..., k=min(50, limit*3))`:** measured ~7 s on the first load (Claude writes one reason per ranked item). Suggest: keep a wide pool via `candidate_product_ids` (up to 50) but pass `k=min(24, limit*2)`, so Claude sees 50 and writes ~24 reasons; top up with your unranked cards as you do now. Repeat loads hit the 10-minute cache.
- **Swipes collection:** great, thanks. `pair()` and the memory fallback read it as written (`action` = cart/wishlist/discard).
- **Colour-variant collapse in the feed:** good; `pair()` doesn't care.
- **Tags at ingest:** easiest is to tag on your machine before you snapshot, so the committed snapshot already has `label`/`pattern`/`formality`/`style_tags`. Adam sends you the Anthropic key privately; it's Haiku and the backend hard-stops at `AI_BUDGET_USD` ($5). ~370 × $0.0002 ≈ $0.07.
- **`to_canonical` turning unknown categories into `top`:** fixed. It now raises `ValueError("unknown category ...")`. `Product(**p)` in ingest is fine too.
- **Try-on images:** noted. The try-on prompt now names the garment slot and ignores models/logos/size text in reference photos, so H&M model shots work (verified on a Uniqlo model shot). Garment-only Uniqlo images are still the safest for the demo.

## New on `staging` for Ryan's request (`ryan-nabil.md`)

Added to `Product` (both optional, existing data still validates):
- `images: [{url, kind: "product" | "retailer_model"}]`, same product + colour only, `image_url` stays the primary. `to_canonical` fills a single-photo gallery when only `image_url` exists.
- `description: string | null`, real retailer text as plain text, else null (never a pairing reason).

Over to you for the ingest side: H&M `images[]` + `model_image` (as `retailer_model`), Uniqlo per-colour images, descriptions from raw when present, and the idempotent wishlist routes Ryan asked for (`PUT`/`DELETE /wishlist/{user_id}/items/{product_id}`). Ryan's branch is `RyanFrontendking`.
