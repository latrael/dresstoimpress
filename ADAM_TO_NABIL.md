# ADAM_TO_NABIL.md

Replies from Adam (AI lane) to Nabil (commerce lane). Newest at the top. Nabil's notes: `NABIL_TO_ADAM.md`.

**Last updated:** Sat Oct 24, 2026, ~2:05 AM PT · on `staging`

---

## Overnight log (Adam's session, every 20 min; newest first)

- **5:12 PM: read sprint-2. Adam's lane, status:**
  - **B1:** on the shared server, `load_products` (no `--replace`) → `tag_catalog` → `warm_demo --tryons 0` is queued; it runs right after my second women's H&M batch finishes (≈ +150 items, already paid). After that I'm **not** running any more Apify jobs: the dataset recovery (B2 step 0) and the expansion runs are yours, as the doc says. Thanks for catching that the Uniqlo "502" was only the HTTP wait timing out.
  - **Sizing PR:** `adam/measure-sizing` is getting cross-department sizing added (men's measurements on women's charts and the other way round), and the PR opens when that's done. You review the 3-line change in `commerce/router.py`.
  - **B4 + B5 stage 2:** `Product.summary` (Haiku 1–2 sentences, or a one-liner from attributes for H&M), the department fallback (name/URL rules, then the tagger, never overwriting a set value), and `blurb()` preferring `summary`: PR `adam/summary-dept` coming. Backfill will be `python -m scripts.tag_catalog --summaries-only` and `--departments-only`.
  - **In flight too:** `POST /onboarding/photos` (+ `shop_for` detection from the body photo), and closet pieces matched to real catalog photos + brand.
- **4:45 PM: catalog is too small (452 products, 440 with `department: null`) — Adam asks you to run the ingest for more.** Findings from my run on the shared server:
  - The Uniqlo Apify actor returned **502** (the whole run died before saving anything). Run H&M and Uniqlo as **separate** commands so one failing doesn't lose the other, and retry Uniqlo later.
  - Your `#31` ingest sets `department` from the H&M category code / Uniqlo gender, so re-ingesting also fixes the 440 nulls (same ids → overwritten in place).
  - Suggested, from `backend/` with the env loaded (`set -a; . ./.env; set +a`), in batches of ~6 keywords so each Apify run stays under its 600 s timeout:
    ```
    python -m scripts.ingest --per 30 --uniqlo "" --hm "mens t-shirts, mens shirts, mens hoodies, mens sweaters, mens jeans, mens cargo pants"
    python -m scripts.ingest --per 30 --uniqlo "" --hm "mens trousers, mens jackets, mens coats, mens sneakers, mens boots, mens shorts"
    python -m scripts.ingest --per 30 --uniqlo "" --hm "womens tops, womens dresses, womens jeans, womens trousers, womens skirts, womens jackets"
    python -m scripts.ingest --per 30 --uniqlo "" --hm "womens sweaters, womens sneakers, womens boots, y2k, baggy jeans, streetwear"
    python -m scripts.ingest --per 30 --hm "" --uniqlo "men t-shirts, men shirts, men sweaters, men hoodies, men jeans, men pants, men jackets, men coats, men shorts"
    python -m scripts.ingest --per 30 --hm "" --uniqlo "women t-shirts, women shirts, women sweaters, women jeans, women pants, women dresses, women jackets, women coats, women skirts"
    python -m scripts.tag_catalog        # labels/style tags for the new ones (Claude, ~$0.0004 each)
    ```
    My first batch (men's H&M, 12 keywords × 25) is running on the shared server now; I'll note the result. If `maxItems` on the H&M actor turns out to be a total rather than per keyword, use fewer keywords per run.
  - After ingest: `warm_demo --tryons 0` (env loaded) so u_demo's feed reasons cover the new items. Don't run `reset_demo` (wipes u_demo's scan + closet).
- **4:02 PM (for Nabil's agent): Adam restarted uvicorn on the shared server at ~3:58.** The tunnel did NOT change: same URL and key as the DM, health 200. If a request failed in that minute, retry; no action needed. Server is on `staging` 54063b6 (#31). **Open asks for you:** (a) the two `department: null` H&M items below, (b) when the sizing PR (`adam/measure-sizing`) and the AI Fit Creator PR (`adam/fit-creator`, `POST /fits/create`) open in ~30 min, please review: both touch only `app/ai/*` plus the arguments your `_size_pick` passes. Reply in `NABIL_TO_ADAM.md`.
- **4:00 PM: #31 live (425 tests, smoke 10/10).** `u_demo` now has `shop_for=men`, `preferred_stores=[hm,uniqlo]`, a body scan and a 10-piece real closet. **Two women's items still rank for him:** "Harper High Rise Wide Leg Jeans" and "Mini T-Shirt" (both H&M). Their `department` is probably null in the catalog; if `tag_catalog` / ingest can infer it from the H&M URL or name ("High Rise", "Mini"), that closes it. Sizing from real measurements (chest/hip/waist/inseam charts + usual size) is coming as an AI-lane PR; it only changes the arguments your `_size_pick` passes through.
- **3:45 PM: your #28 is merged and live on the shared server** (b96d942, smoke 10/10, `/search/styles` and size fields answering). Adam's agents had built the same routes in parallel (#27, #29); **closed in your favor**, nothing of yours was touched. Still available if you want AI-parsed queries in `/search`: `from app.ai.vibe import vibe` → `{styles, categories, colors, keywords, source}` (merged in #25, rules fallback, cached). Core for Ryan matching your shapes is PR #30. Note for your `in_your_size`: `u_demo` has no `body_profile` yet, so it's null until the demo body scan runs.
- **3:15 PM: council v2 read; overlap warning + what Adam's lane gives you.** All 7 PRs merged, shared server on `staging` (343 tests, smoke 10/10).
  - **Don't rebuild "Profile on the server".** It exists from #22: `User.body_profile` (`height_cm, weight_kg, chest_in, waist_in, hip_in, inseam_in, shoe_us, fit, usual_sizes{category: size}, build, source, manual[]`), `PATCH /users/{id}/body-profile` (cm in, inches stored; `None` clears), `POST /users/{id}/body-scan` fills the same profile from a photo, `GET /users/{id}` returns it, and `POST /size` with `user_id` already falls back to it (including `usual_sizes`). **You only need `preferred_stores` and `onboarded` on `User` + your `PATCH /users/{id}`.** Keep `body_profile` as the one place for measurements; your soft size ranking should read it (`app/ai/router.py` `_usual_size` + `recommend_size` show the lookup).
  - **Vibe search for your Discover `GET /search?q=`:** the AI PR adds `vibe(q)` (importable from `app.ai`) and `POST /ai/vibe` → `{styles, categories, colors, keywords, source}`. Styles are only our 10 catalog tags, categories only our 6. Rules fallback when the AI is down. Call it when `q` has 3+ words or no direct keyword hits.
  - **Seeded Home `GET /feed?seed=`:** rule-based is fine; `app/ai/finder.py` has `item_type`/`TYPE_GROUPS` and the color words you can reuse for "similar".
  - **Inspo tags get a `box`** (`[x_min, y_min, x_max, y_max]`, 0–1, optional) from the tagger in the AI PR. Your fitcheck code just needs to keep the field through store + `PUT` tag edits; the PR touches your `fitcheck.py` minimally for that. Shout if you'd rather do it.
  - **Body photo delete:** `DELETE /users/{id}/body-photo` (AI PR), for the User screen.
  - Your 2:45 shop_fit notes are done (#19): collared shirts, watches/bracelets, off-shoulder cuts.
- **3:00 PM: your 2:45 note.**
  - **GPS: fixed in PR #22.** `_save_upload` now re-encodes every upload with the EXIF dropped, rotation applied and a 2048 px cap. That covers Fit Check (your `fitcheck.py` uses it), closet, digitize and body photo/scan. HEIC that Pillow can't read is kept as-is.
    - `post_real_fits` stripping too is harmless.
    - The seeds on the shared server have **not** been replaced, so run it there as `--users u_nabil`.
  - **shop_fit quality notes:** noted (gender match, collared vs graphic, watches). I'll look at them if there's time before the freeze.
  - **Ryan's asks for your lane (RYAN_TO_ADAM 2:40):**
    - (3) An atomic cart size change that keeps the quantity and merges into an existing line of the new size.
    - (4) Confirm the onboarding parser recognizes his category price maximums: tops / bottoms / jackets / shoes, as plain text.
  - **App audit, commerce side:**
    - **A cart can get stuck on a removed product.** `_grouped` hides items whose product left the catalog (router.py ~279-281), but checkout returns 409 on them (~335-339), so the user can't see or remove the item.
    - **On `nessie_failed` the cart is emptied** (~360) with no way to retry until #20 merges. I'll add `Api.retryOrder` to core after that.
- **13:45: the shared backend is back at a NEW URL** (Adam DMs it; the 10:25 one is dead). Smoke 10/10. **PR #19 (AI)**: after a swipe, `/feed` no longer waits ~6 s for Claude; it serves banked reasons and re-ranks in the background. `scripts/warm_demo.py` (after `reset_demo`) warms the feed, the Fit Check shops and try-ons. No API changes.
- **10:55 AM: all four PRs merged** (#15 → #14 → #13 → #16). The shared server runs `staging` 096a4cb: 275 tests, smoke 10/10, checkout `paid`. Your `DELETE /fitcheck/{id}` is live, so `post_real_fits` can run against the shared URL once the photos exist.
- **10:35 AM:** Ryan opened PR #16 (app only). It merges cleanly with #15 + #14 + #13, and 275 backend tests pass on the result. The order is #15 → #14 → #13 → #16.
- **10:25 AM: the shared tunnel is back,** with a new URL that Adam DMs you. Smoke test 10/10 through it (checkout `paid`). Your backup server can stay localhost unless the shared one drops again. The merges #15 → #14 → #13 are next.
- **8:10 AM: read your final morning report.** Re-checked after your 8:05 push: `staging` + #15 + #14 + #13 merge with no conflicts, and **275 tests pass**. The 9:15 order is #15 → #14 → #13. The shared tunnel is still down until Adam's 8:45 restart. The full report is at the top of `docs/progress.md`.
- **2:05 AM: fallback drill, for your demo script's fallback column.**
  - **Claude down:** Gemini takes over, and everything still works (smoke 10/10).
  - **Both AI providers down:** feed reasons come from rules, try-on returns an outfit board (`mode: collage`), and the cart, checkout and Fit Check shop still work (10/10).
  - **What fails:** only new photo tagging (closet upload, Fit Check auto-tags). It now returns `502` "photo tagging is unavailable right now, try again in a minute".
  - **Note:** I cleared u_demo's cart, swipes and wishlist on the shared store by mistake at 2:00 (the clean demo state anyway). Your checkout evidence on `u_test_checkout` / the backup server is untouched.
- **2:15 AM: read your morning report.** Plan confirmation and both changes noted.
  - **Moss: NOT live.** No `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` was ever set, so style memory uses swipe + wishlist history. **Don't list the Moss track** unless we get keys and switch it on Saturday.
  - **The shared tunnel died at ~1:25** (Cloudflare dropped the quick-tunnel hostname: NXDOMAIN, 0 connections). Adam restarts it at 8:45, so the URL changes. The server itself is fine.
  - **New in PR #15:** on startup, stored `/static/uploads|tryon` image URLs are rewritten to the new address. That covers users, closet, **`fitcheck_posts.photo_url`** (your data; only that URL shape) and try-ons, so nothing breaks when the hostname changes.
  - **Ryan's `nessie_failed` retry:** your proposal (`POST /orders/{id}/retry`) is a team call. I'm leaving it for the 9:00 standup.
  - **After 9:15:** restart the shared server once #14 is merged (`DELETE /fitcheck/{id}`). I'll do it as part of the tunnel restart.
- **1:55 AM: I see your PR #14** (Devpost draft + demo script). No conflicts with mine, and no asks for me.
  - **For Devpost:** the AI section is ready to paste, in `docs/ai-writeup.md` (in my PR #15; also on `staging`, docs only).
- **1:50 AM: PR #15** (AI quality pass). **One thing touches your route:** `shop_fit()` now returns the post's items in post order, closest match first, with color variants of one style collapsed into one card. So `/fitcheck/{id}/shop` changes order, not shape. Your tests still pass (261 total).
  - Also in #15: budget-first feed ranking, no made-up closet items in reasons, women's numeric sizes, `scripts/reset_demo.py` (run before dry runs), `scripts/ai_quality_check.py`.
- **1:20 AM: PR #13** (`app/ios`, waiting on Ryan's OK). The unsigned iOS build works on Adam's Mac.
- **Shared server:** up and running `staging` @ 4f5df54. Mac on `caffeinate`. I'll fast-forward it after the 9:15 merges.

---

## Sat ~1:15 AM: overnight plan (1–10 AM) is up; please confirm by 9:15

**[`docs/plan-sat/nabil.md`](docs/plan-sat/nabil.md)**: overnight blocks for your agent (only if you started it before bed; prompt in `docs/plan-sat/README.md`), then your 9:00–10:00 list. Anything not done overnight moves to 9:15. Team view: [`docs/plan-sat/README.md`](docs/plan-sat/README.md).
- **9:15–10:15:** backup server on your laptop, with exact commands (same `API_SHARED_KEY`).
- **10:15–11:15:** real Fit Check posts to replace the picsum seeds.
- **11:15–12:00:** 3 test checkouts with Nessie screenshots.
- **12:00:** Checkpoint A, where you confirm the purchase in Nessie.
- **13:30–15:30:** Devpost draft. I'm writing `docs/ai-writeup.md` overnight for the AI section.
- **15:30–17:00:** demo script.
- **17:30:** dry run, where you run the clock.

**Please write "Plan confirmed"** (or your changes) at the top of `NABIL_TO_ADAM.md` by 9:15.

---

## Oct 23, ~11:15 PM: server pulled and tested after #7 / #8 / #9 / #10 (as you asked)

Did your three steps on Adam's Mac. The server runs `staging` @ 28fb0c5, plus PR #11's one-line `/img` fix:
1. **Restarted** on the merged code. **248 backend tests pass.**
2. **`python -m scripts.seed_fitcheck`:** the 3 posts now carry category/color/pattern/style_tags. Fit Score on fc_seed_1 = **85, "Almost there, add shoes"**.
3. **`smoke_e2e` through the tunnel: 10/10.** The feed shows a reason on **8 of 8** cards, your ranked-first fix working with my top-up. Checkout is a Nessie `paid`.

**Your new routes, checked live:**
- `GET /products?q=jeans`: 3 results.
- `GET /users/u_demo`: 200.
- `/fit` and `/fit/wall`: **404** (`FITCHECK_EVENT_CODE` unset, as agreed until Ryan says yes).
- `/fitcheck/feed` without the key: **401**; with it: 200.

**Your `_is_open` block is correct.** I applied the same idea to my `/img`: it was a prefix, so any future `/img*` route would have skipped the key. Now `OPEN_EXACT = ("/fit", "/img")`, with a test. It's in **PR #11**, which also adds your search, users, onboarding and Style DNA apply routes to the app's `core/` (Ryan asked for them).

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
4. **PR #7 now shows a conflict, caused by me.** I published newer copies of my own docs on `staging`, and your branch has older copies from when you merged `adam/ai-pipeline`. Only `ADAM_TO_NABIL.md`, `ADAM_TO_RYAN.md` and `docs/app-plan.md` conflict, none of your code. Fix (checked: 0 conflicts left, **247 tests pass**):
   ```
   git fetch origin && git merge origin/staging
   git checkout --theirs ADAM_TO_NABIL.md ADAM_TO_RYAN.md docs/app-plan.md
   git add ADAM_TO_NABIL.md ADAM_TO_RYAN.md docs/app-plan.md && git commit --no-edit && git push
   ```

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
