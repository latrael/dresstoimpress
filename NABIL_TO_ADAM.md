# NABIL_TO_ADAM.md

Notes from Nabil (commerce lane) to Adam (AI lane). Newest notes go at the top. Reply in `ADAM_TO_NABIL.md` on your branch; I read it every time I start work.

**Last updated:** Sun Oct 25, 2026, ~5:15 AM PT. Lives on `staging` (via PRs from `nabil`).

---

## Sun 12:30 AM: Sprint #4 (`docs/sprint-4.md`): your part is §10, the data behind the new reels Home

The new Home post is a 3-slide carousel: the item → **the try-on on you, already loaded** → **a 2×2 grid of your own closet pieces that go with it**. What it needs from you:
- **`closet_picks(user_id, product, k=4)`:** rules only (free and instant), one closet piece per square, different categories, accessories allowed, in the slot order in §10.1. I put it on every `/feed` card.
- **`tryon` status per card:** `ready | pending | none | needs_photo | unavailable`, from the try-on cache.
- **`prefetch_tryons(user_id, items)`:** a background pool of 2 with de-duplication, reusing `try_on` and its cache key and the v5 source photo. I add `POST`/`GET /feed/{user}/tryons`.
- **Budget (decide):**
  - `MAX_TRYONS=150` for the whole server would run out fast.
  - Please bring the Gemini cost per image, and propose the new cap + ~20 prefetches per user per day.
  - After the cap, the card falls back to the collage.
- **Core:** parse `heroImageUrl`, `closetPicks` and `tryOn`; add `prefetchTryOns` and `tryOnStatus`. **Ship mocks early**, so Ryan can build Home on them.

**I'm doing:** `hero_image_url` (classifying catalog photos; only Uniqlo is labelled `product` today), the `/feed` fields, the routes and the tests.

---

## Sun 5:15 AM: FYI, I de-flaked one of your tests (test-only change) + #82 is merged

- **`tests/test_closet_v2.py::test_posting_a_fit_check_adds_its_pieces_to_the_closet`** failed about 1 run in 3 after #84.
  - **Cause:** a closet thread spawned by an *earlier* test (real `service._spawn`) finishes late and writes a `u_c` piece into the next test's fresh store. The `== []` "not yet" assertion then sees it.
  - **Change:** the test now uses its own user `u_hook`. 8 of 8 runs of the file pass; full suite 737.
  - **If you'd rather fix the root:** a fixture that joins pending `_spawn` threads (or makes `_spawn` inline) for closet tests.
- **#82 is merged:** unliking through the old like routes now clears the stored emoji (your #78 edge).

---

## Sun 4:30 AM: catalog gap closed (shoes + accessories from 5 more stores). **Please reload the snapshot** + one note on #78

**Your ask from the rec eval** ("shoes = 168, all H&M; 7 of 8 stores have no shoes/accessories") is done:

| | Before | After |
| --- | --- | --- |
| Products | 3,188 | **3,476** |
| Shoes | H&M 168 | H&M 168 · **Princess Polly 60** · **Kith 48** (sneakers) · Stüssy 1 |
| Accessories | H&M, Uniqlo, + 9 | H&M, Uniqlo · **Brandy Melville 65** · **Stüssy 41** · **Edikted 38** · **Princess Polly 38** |
| Product-only `hero_image_url` | 941 | **1,167** |

- **Source:** 7 capped `autofacts/shopify` collection pulls, 340 raw items, ~$0.34 of Apify. Raw files are in `seed/raw/shopify_*_20261025.json.gz`.
- **Tagging:** Claude tagged 289 of 291. The new photos are labelled for ~$0.02.
- **Ingest fixes** (`ingest_shopify.py` / `ingest.py`):
  - Kids' sneakers are dropped (`PS` / `GS` / `TD` / toddler / infant).
  - Lifestyle goods are dropped (Kith × BMW trays, teddy bears, car plates; Stüssy camping tables; underwear packs).
  - Princess Polly's `SHOE US 7` becomes size `7`.
  - New category words: sneaker / boot / derby / footwear, ring / earrings / necklace / cuff / clip / tote / backpack / headwear, sarong.
  - Covered by `test_shoes_and_accessories_pull`.
- **Please, on the server:** `git pull` → `python -m scripts.load_products` (no `--replace`) → restart → warm one `/feed` per team account. Complete the Look and `closet_picks` should stop reaching for the same H&M shoes.

**Note on #78 (reactions), your code:**
- It works with my like routes: a like with no reaction counts as 😍, and the feed shows counts only, so no user ids leak.
- **One stale-state edge:** a user reacts 🔥, then unlikes through the old `POST/PUT …/like`. That removes them from `likes` but leaves them under 🔥 in the stored `reactions`, so `reaction_map` hides it. If they like again via `PUT …/like`, they come back as 🔥 instead of 😍.
- **Fix:** have my like routes call `set_reaction(post, user_id, None)` on unlike. I'll make that change once #78 is merged, so we don't conflict.

---

## Sun 3:35 AM: your #73 conflicts with staging (my #70). Resolve `llm.py` by **taking staging's version**

**The conflict:** #73 was branched before #70 merged, and GitHub says `CONFLICTING` (`llm.py` and `tests/test_prompts_deterministic.py`). We both fixed the same dead-Claude bug.

**Please keep #70's fix rather than `_claude_create`'s `extra_body` path.** I tested it against the live API just now:
- `messages.create(model="claude-haiku-5-5", thinking={"type": "disabled"}, extra_body={"temperature": 0}, …)` → **400 `temperature: Extra inputs are not permitted`**, in 0.5 s.
- The same call without it → 200.
- So with `extra_body`, **every** Claude call makes one guaranteed failing round trip first. That's +0.5 s and double the request count against rate limits, and it's ×2 when the schema retry fires.
- Haiku 5.5 only takes its default sampling, and API `2026-10-21` rejects the field on every model. So there's no case where sending it helps.

**How to resolve:**
1. `git merge origin/staging` on `adam/rec-eval`.
2. In `llm.py`, take staging's `claude_json` create call (thinking off, no `temperature`). You can keep `_claude_create` as a helper if you like, minus the `extra_body` try.
3. In `test_prompts_deterministic.py`, keep staging's assertion that no `temperature` / `top_p` / `top_k` reaches Claude, plus your v5 changes.

Everything else in #73 looks good to me (rules-first shortlist, validators, `eval_recs.py`, `PAIR_VERSION` v5), and it touches nothing in commerce.

**🔴 For the whole team:** your PR says **Gemini is at 402 (credits depleted)**, so live try-ons are down: slide 2 falls back to the collage for everyone. Gemini also covers for Claude, so with Claude now fixed the text side is fine, but **try-ons need Gemini credits before the demo.** Please say in `ADAM_TO_NABIL.md` how much is needed and who's topping it up. I've flagged it to Nabil.

---

## Sun 3:20 AM: **Nabil: Adam now picks up all new tasks for Ryan.** Ryan's #71 is merged; here's what's open, in order

**1. 🔴 The shared server is on old code (checked 3:05 AM through the tunnel).**
- `/ai/usage` → `last_claude_error: "...unexpected keyword argument 'temperature'"` and `max_tryons: 150`. So it doesn't have #69 or #70: **Claude is still failing over to Gemini.** Feed reasons are the rule-based "Goes with your …".
- `/feed?user_id=u_nabil`: **0 of 20 cards** have a product-only `hero_image_url`, so the #68 snapshot isn't loaded.
- **Please, on the server:**
  1. `git pull` (staging `47450e3`: #69 #70 #71).
  2. `pip install -r requirements.txt`.
  3. `python -m scripts.load_products` (no `--replace`).
  4. Restart.
  5. Warm the reason banks: one `GET /feed?user_id=` for u_adam / u_nabil / u_ryan / u_demo. The first is ~7 s, then ~40 ms.
- **Check afterwards:** `/ai/usage` has no new `last_claude_error`, `max_tryons: 400`, and some cards have `hero_image_url != image_url`.

**2. The per-user prefetch cap is already biting.**
- At 3:08 AM I prefetched 2 of u_nabil's posts. Both came back at once as `unavailable` + collage (`gemini_images` stayed at 78), while u_adam's cards are `ready`/`ai`. **u_nabil has used his 20 pre-renders for today.**
- Ryan's Home prefetches the next 3 on every post you land on, so **~20 posts of scrolling uses the whole day's budget**, even for posts the user never reaches.
- **Before the demo:**
  - Reset `prefetch_usage` for `u_demo` (or raise `PREFETCH_PER_USER_DAY` for the demo; there's plenty of headroom with `MAX_TRYONS=400`).
  - Don't let anyone scroll `u_demo` the night before.
  - Optional: count only renders that actually start, not cached hits.
- **Speed:** with your measured 15–20 s per render and a pool of 2, the 3rd prefetched post is often still `pending` when reached. A pool of 3 (or prefetching posts 1–5 on load) would hide it. Your call on cost.
- The collage itself looks right: the user's own photo + the product + their closet pieces, labelled as a board.

**3. Ryan's open asks from #71 (now yours):**
- **Pixel 9 Pro hardware pass:**
  - Screenshots of Home / Discover / Inspo;
  - edge-back gesture vs. tab swipes;
  - haptics on likes, chips and Add to cart;
  - no black band at the top;
  - the nav pill above the gesture bar.
  - Ryan's capture is **simulator only** (`docs/sprint-4/after-home-iphone16-simulator.png`).
- **A real photo-owning account, ready / AI / collage + preloaded post 2 onward:**
  - Partly done above: the collage path is verified on u_nabil; AI-ready is verified on u_adam by you.
  - Still open: a fresh account with a body photo + closet, scrolled at normal speed after the deploy. Is slide 2 `ready` on posts 2–4?
- **Physical iPhone 16:** I built Ryan's #71 for Nabil's iPhone. I'll install it as soon as the phone is connected, so Nabil can do the iPhone acceptance himself.

**4. Done on my side tonight (for reference):**
- #68: hero photos + `/feed` reel fields + prefetch routes.
- #70: the Claude `temperature` fix + `/feed` timings.
- Devpost + demo script updated for the reels Home: warming steps, the 20/day cap, the slide-by-slide script and fallbacks.

---

## Sun 2:45 AM: 🔴 since #67, **every Claude call fails** (silently, over to Gemini). Fixed in my PR; plus the warm `/feed` timing you asked for

**The bug.**
- #67 sends `temperature=0` on every Claude call (`llm.claude_json`). Claude Haiku 5.5 only accepts its **default** sampling, so a non-default `temperature` is a **400**, on any API version.
  - On top of that, API version `2026-10-21` (four days ago) rejects `temperature` / `top_p` / `top_k` on every model, even at default values.
  - SDK 2.x (what a fresh `pip install` gets, `anthropic>=0.40` is unpinned) doesn't even accept the argument: `TypeError: Messages.create() got an unexpected keyword argument 'temperature'`.
- **Effect:** `ai_json` catches it and falls over to Gemini. So on the shared server, **tagging, feed reasons, vibe search, closet digitize and body scan have been running on Gemini, not Claude**, since #67. No error shows anywhere.
- **Repro:** `ai_json('Reply with JSON only: {"ok": true}')` with `AI_TEXT_PROVIDER=claude` → `BadModelOutput: claude: ... unexpected keyword argument 'temperature'`.

**The fix** (`app/ai/llm.py`, my PR):
- The Claude call no longer sends `temperature`. Gemini keeps `temperature=0` + `seed`.
- Claude's determinism is your per-prompt schema check, which stays.
- `tests/test_prompts_deterministic.py` now asserts the Claude call sends **no** `temperature` / `top_p` / `top_k` (a regression guard). The comments in `llm.py` / `prompts.py` say why.
- **Verified live:** a direct call returns `{"ok": true}` in 1.4 s, and `/feed` gets real Claude reasons ("White graphic tee pairs cleanly with your black bottom"). 713 tests pass.

**Warm vs cold `/feed`** (local, real Claude, real 3,188-product snapshot, 12-piece closet, 20 cards):

| Path | Time |
| --- | --- |
| Cold (no cache, no bank: a new user, or the first load after a closet / style change or a `PAIR_VERSION` bump) | **6.8 s** (Claude writes ~24 reasons) |
| Warm (10-min exact cache) | **34–42 ms** |
| Cache expired but the reason bank is fresh (< 1 h) | instant from the bank; Claude re-ranks in the background |

Your 7.5 s after the restart was the cold path: #67 bumped `PAIR_VERSION` v3 → v4, which emptied every bank. (It was probably also slower because it was Gemini answering after Claude failed.)

**Asks:**
1. **Merge my PR, then restart the shared server.** Run `pip install -r requirements.txt` there; it's fine on either SDK major now.
2. **After every restart or deploy that bumps `PAIR_VERSION`, warm the reason banks** for u_adam / u_nabil / u_ryan / u_demo: one `GET /feed?user_id=<u>` each (or `scripts.warm_demo --tryons 0`). The first Home load of the demo shouldn't be the 7 s one.
3. **Optional, your call:** for stricter Claude JSON, structured outputs (`output_config.format` with a JSON schema) would replace the retry-on-bad-shape loop. Not needed for the demo.
4. **Everything from my 1:45 AM list still stands** (deploy + `load_products`, live try-on numbers ✓ thanks, budget ✓ 400, warm the demo account, closet quality, Ryan's adapters).

---

## Sun 1:45 AM: sprint-4 §10 is wired end to end (your #66 + mine). **What's next for you**, in order

**Thanks for #66.** I wired `/feed` and the two routes to your real functions, with your signatures:
- `closet_picks(u, card, k=4)`;
- `tryon_status(u, card, picks)`, with the card's own picks, so slide 2 is the try-on of exactly the pieces on slide 3;
- `prefetch_tryons(u, [products])`.

**On `staging` from me (merged):**
- **`app/commerce/reels.py`:**
  - Every `/feed` card (plain and `?seed=`) has `hero_image_url`, `closet_picks` and `tryon`. A failing helper degrades to `[]` / `{"status": "none"}` and never fails the feed.
  - `POST /feed/{u}/tryons` (≤ 5 ids, de-duped, 404 unknown, 422 for 0 or more than 5) and `GET /feed/{u}/tryons?ids=`.
- **`/feed` timing:** 41 ms median for 20 cards, with your real functions, a 16-piece closet and a body photo.
- **Catalog photos labelled:**
  - `scripts/classify_images.py` used Haiku on a contact sheet per product to label 10,809 photos (product / model / detail / other), for ~$0.21.
  - The labels are cached in `seed/image_kinds.json`; `ingest.save` re-applies them. `ProductImage.kind` gains `detail` / `other`; `Product.hero_image_url` is new.
  - **Coverage: 941 / 3,188 products have a real product-only hero photo:** Kith 164/164, Stüssy 94/94, True Classic 179/180, H&M 430/1,255, Uniqlo 67/798, Princess Polly 7/345, Brandy Melville 0/178, Edikted 0/174 (those stores only shoot on models; cards fall back to `image_url`). Princess Polly's `…-modelinfo-…` filenames are forced to `model`: tight crops fooled the AI on 4 of 11.
- **Tests:** `tests/test_reels.py` covers the routes and the card fields: stubbed, plus one test on your real functions. 691 pass with yours.

**Your next steps:**
1. **Deploy, now (Ryan needs it live for slides 1–3).** On the shared server, `git pull` staging, then `python -m scripts.load_products` (no `--replace`; this brings in `hero_image_url` + the photo labels), then restart.
   - **Check:** `GET /feed?user_id=u_nabil` cards have `hero_image_url`, `closet_picks` and `tryon`, and `POST /feed/u_nabil/tryons {"product_ids": [<first card id>]}` returns `pending`.
2. **A real end-to-end try-on check on the shared server** (a team account with a body photo and a few closet pieces):
   - prefetch the first 3 posts;
   - poll until `ready`;
   - **post in `ADAM_TO_NABIL.md`:** seconds per render and dollars per render, plus whether the result really shows slide 3's pieces.
   - **If the render takes over ~10 s:** prefetch on feed load for posts 1–5, not 1–3, and tell Ryan.
3. **Budget sanity (§13.5):**
   - `MAX_TRYONS` is still 150 **server-wide**, and `PREFETCH_PER_USER_DAY` is 20. Four of us testing Home can use ~80 a day, plus Fit Creator / manual try-ons.
   - **Check `GET /ai/usage`** (`gemini_images`) after step 2 and tell the team how many are left before the demo. If it's tight, raise `MAX_TRYONS` on the server's `.env` (no code change), or drop prefetch to posts 1–2.
4. **Warm the demo account before the demo.** Prefetch (or `scripts.warm_demo`) the first ~6 Home posts of the account we demo with, so slide 2 is instant on stage. Do it after its closet and body photo are final, because the picks are part of the cache key.
5. **Closet quality for slide 3.** `closet_picks` is only as good as the closet's `category` / `colors` / style tags.
   - Run `scripts/redo_closet.py` for any team account whose closet predates #59.
   - Spot-check that a bottom gets top / shoes / outer / accessory and that **no catalog photo** shows (sprint-3 §1.2).
6. **Support Ryan's Home (§6):** Ryan asked you for "exact feed core adapters" (`RYAN_TO_ADAM.md`, a4f96e5).
   - The fields and methods are in your #66 core.
   - Make sure `prefetchTryOns` / `tryOnStatus` are what his Home calls, and that the mocks cover `ready`, `pending` → `ready`, `needs_photo` and `unavailable` + collage, plus 4 and 2 picks.
7. **Later / held:** login stays held until the team OKs it (sprint-3 §4); I'll ask before touching core for it.

**What I need back:** one line when step 1 is live, and the step 2 + 3 numbers (render time, cost per render, images left).

---

## Sat 11:30 PM: your 10:45 asks: review done (one fix in `service.py`), Nessie re-tested on the fresh DB, Devpost updated

**1. Review of grouped shop the look: the route shape is good, but I fixed one bug in `service.py`; please look.**
- **The bug:** `_shop_fit_rows` took the top N matches per tag from the whole catalog, and the `shop_for` filter only ran afterwards. Inspo is one feed for everyone, so viewers often see the other department's fits and their groups came back half empty. Claude also wrote reasons for cards that were then thrown away.

  Real catalog, top 6 per piece:

  | Piece | Viewer | Before | After |
  | --- | --- | --- | --- |
  | white baby tee | women | 2/6 | 6/6 |
  | baggy jeans | women | 3/6 | 6/6 |
  | black hoodie | men | 2/6 | 6/6 |

- **The fix:**
  - `_shop_fit_rows(..., keep=None)` and `shop_fit(..., keep=None)` are new. `keep` is applied to `list_products()` *before* `find_products`, and again to each tag's hits (that covers a pinned `product_id` and live results). `shop_fit_grouped` passes it down.
  - With no `keep`, behaviour is the same as before, so `/ai/shop-fit` is unchanged.
  - The flat and grouped `/fitcheck/{id}/shop` routes and my `/search/photo` (`keep = buyable and dept`) now pass it.
- **Tests:** `test_keep_filters_catalog_before_matching` in `test_shop_grouped.py`. Two stubs (`test_department`, `test_feed_size`) now accept `keep`.
- **FYI:** `/ai/shop-fit` ignores the viewer's `shop_for` entirely. That's fine as long as the app uses `/fitcheck/{id}/shop`.

**2. Nessie checkout re-tested on the shared server (11:29 PM, throwaway `u_test_checkout`): 4/4 store purchases `paid`.**
- H&M only, Uniqlo only, and a mixed H&M + Uniqlo cart. All are confirmed in Nessie's purchase list.
- Empty cart → 400 and a sold-out size → 422 when added; nothing was charged. The cart is empty again.
- The ids are in `docs/devpost.md`.
- **Notes:**
  - The rebuild dropped the user → Nessie account mapping (expected), so `u_test_checkout` got a new account.
  - Nessie only has H&M and Uniqlo merchants so far. A Shopify store creates its merchant on the first purchase (`ensure_merchant`).

**3. Devpost updated:** Fit Score v2, try-on edits only the garment on your best own photo, shop the look per piece, closet outfits + own photos only, the Niche icon, 672 tests, and the new Nessie evidence.

**4. Inspo feed/detail now send only the 2 newest comments** plus `comment_count`, shaped like the paged items (with `author`). Ryan gave the explicit ready signal after #56, and I checked the app's model and the comment sheet: counts come from `comment_count`. Nothing to change in core.

**5. Login:** still waiting on the council's pick (sprint-3 §4). Nothing is shared yet.

**Please, after merging:** restart the shared server so the comment trim and the shop fix go live.

Not done: `scripts/redo_closet.py` (it's optional, and it rewrites a user's closet; say which users if you want me to run it).

---

## Sat 7:50 PM: ⚡ the JSON store now caches in memory: `/feed` 70 s → 0.17 s. **Please restart the shared server on this code**

**What we measured** (real 3,188-product snapshot, MOCK_AI, TestClient, medians):

| | before | after |
| --- | --- | --- |
| **`GET /feed?user_id=u_demo`** (with body_profile) | **~70,400 ms** | **166 ms** |
| `GET /search?q=jeans` | 158 ms | 38 ms |
| `GET /products?q=tee` | 23 ms | 7 ms |
| `store.get("products", id)` | 18 ms | 0.01 ms |
| `store.put("products", …)` (6 MB file) | 37 ms | 19 ms |

**Why `/feed` was so slow:**
- `ai.service.pair()` → `get_product(pid)` → `store.get("products", …)` runs once per candidate.
- Each call re-parsed the 6 MB `products.json`, ~3,000 parses per request.
- The live server has this today, so this is probably most of the "slow app" feeling.
- The remaining 166 ms is mostly `pair()` fetching candidates one by one plus `_size_fields`. Batch it if you want it faster; it's your call.

**What changed (`app/store.py`, `JsonStore` only; Firestore untouched):**
- **The cache:** a per-file cache of the parsed dict, keyed by (inode, mtime_ns, size). Every read `stat`s the file, so writes from other processes (your scripts while the server runs) are seen on the next read; every write replaces the file with a new inode.
- **Writes:** `put`/`delete` still load-modify-write under the lock from a fresh view. A direct `_write` (e.g. `rebuild_db`) drops the cache entry.
- **What reads return:** `get()` and `_load()` return deep copies. **`list()` returns shallow copies of each doc**: a deep copy of all products costs as much as the old parse.
  - **Rule:** don't mutate nested lists/dicts of a doc from `list()` in place (`p["style_tags"].append(…)`); build a new dict (`{**p, …}`), which all current code already does. Doing it in place would only change that process's in-memory view until the file changes.
- **Memory:** each process holds the parsed products (~150 MB RSS in the benchmark).
- **Test gotcha:** a test module that imports `app.store` at module level breaks `test_ai`, because the store is created before `test_ai` sets `DATA_DIR`. Import it inside the tests.

**Also in this PR (sprint-3 Inspo):** `PUT /fitcheck/{id}/like` (idempotent), `GET /fitcheck/{id}/comments` (paged), and `photo_w`/`photo_h` on posts. Core methods for Ryan, please: `likePost(id, liked:)`, `comments(id, before:, limit:)`, and `FitPost.photoW/photoH`. Contracts are in `NABIL_TO_RYAN.md` 7:50 PM.

## Sat 7:20 PM: database rebuild is ready; please run it on the shared server (sprint-3 §6, council said do it now)

`scripts/rebuild_db.py` (PR from `nabil`). **Dry run by default.** I ran it on Nabil's backup: 3,188 products, 8 stores, Inspo empty, 4 blank team users, backup kept.

**On the shared server, from `backend/` with the env loaded:**
```
python -m scripts.rebuild_db           # dry run: read the counts first
python -m scripts.rebuild_db --yes     # copies DATA_DIR to data.bak-<time>, then resets
python -m scripts.tag_catalog --summaries-only    # free: summary_cache is kept
# restart uvicorn, then:
python -m scripts.warm_demo --tryons 0
```
- **Kept:** the snapshot products (exactly; live-search, seed and server-only ingests are dropped), `tag_cache`, `summary_cache`, and the Nessie merchant ids.
- **Reset:** users, closets, fits, Inspo posts (**Inspo starts empty**, decided), carts, orders, saves, swipes, pair/try-on caches, `uploads/` + `tryon/` (body photos too), `ai_usage`, Nessie per-user accounts. Unknown collections are listed and left alone.
- **Re-created:** blank `u_adam`, `u_nabil`, `u_ryan`, `u_demo`, so the one-tap Welcome buttons still open a profile. Everyone re-onboards; whoever demos re-does the body scan + closet so the size badges and pairing work.
- **Firestore:** it works there too (deletes per doc, and backs up the reset collections to JSON).
- **`.venv` note (6:25 PM above):** if your server checkout used the symlink, re-create it before restarting.

## Sat 6:25 PM: ⚠️ `backend/.venv` got committed as a symlink to your machine (#51); fixed, but read this before you pull

- **What happened:** commit `97e9536` (closet v2 merge) added `backend/.venv` → `/Users/adamw/dresstoimpress/backend/.venv` as a tracked symlink. `.gitignore` said `.venv/`, which only matches directories, so the symlink slipped in.
  - On everyone else's machine, pulling `staging` **replaced their real (ignored) `.venv` with your dead link**. Nabil's venv was wiped (rebuilt now).
  - Ryan will hit the same if he runs the backend.
- **The fix (PR from `nabil`):** `git rm --cached backend/.venv`, and `.gitignore` now says `.venv`, which also matches symlinks.
- **⚠️ For you, before restarting the shared server:** pulling the fix makes git **delete the symlink in that checkout**. If the server's checkout uses it, re-create it right after the pull. It's ignored now, so it won't be committed again:
  ```
  ln -s /Users/adamw/dresstoimpress/backend/.venv backend/.venv   # from the server's checkout root
  ```
  Or point uvicorn at the venv by its full path.

## Sat 6:10 PM: after #47, two sizing bugs still show in the demo, with root causes (your `ai/sizing.py`)

I re-ran the catalog sizing check on merged `staging` (532 tests pass), with a woman 165 cm / 58 kg, 34-27-37 in:

| Store / category | Result | Should be |
| --- | --- | --- |
| **Princess Polly tops** | **`12`, `in_your_size: true` on 136 of 179** | ~`4`–`6` |
| Princess Polly bottoms | `6` (54 of 80) | ✅ |
| **Brandy Melville** | no size on 161 of 169 (`XS/S`, `S/M`) | `XS/S` / `S/M` |

1. **Number-sized tops and dresses (PP, also H&M women's numeric dresses):**
   - **Cause:** in `_recommend`, women's US numeric sizes are only handled in **step 4, which is bottoms only** (`category == "bottom"`). A top with sizes `0`–`12` falls to **step 6** (`# Fallback if non-bottom item only has numeric sizes`). That calls `_nearest_numeric_size(float(waist_in), numeric_candidates)`, which compares the **size number to the waist in inches**, so 27 → the biggest size, `12`.
   - **Suggested fix:** in step 6, when `_is_womens_numeric(sizes)`, map each size through a bust chart when `chest_in` is given (US 0≈32, 2≈33, 4≈34, 6≈35, 8≈36, 10≈37.5, 12≈39 in). Otherwise use `WOMENS_US_WAIST` / `WOMENS_US_HIP` exactly as step 4 does, rather than raw numbers. Even just reusing step 4's hip/waist mapping for non-bottoms gives `6` here.
2. **Combined sizes `XS/S`, `S/M`, `M/L`, `L/XL`:**
   - **Cause:** they aren't in `LETTER_TO_IDX`, so `available_letters` is empty and the item ends at "unsupported size format".
   - **Suggested fix:** when scanning sizes, split on `/` and give the label the index of its smaller letter (or both). The nearest-letter search then picks `XS/S` for an `S` body.
3. **`One Size`** (14 Brandy items): no badge yet. Suggest `your_size: "One Size"`, `in_your_size: true` when it's in stock.

These are user-visible on Home: a "your size: 12" badge on most Princess Polly tops for an average woman. Worth fixing before the dry run if you can. I didn't touch your file; tell me if you'd rather I open the PR.

## Sat 6:05 PM: review of `adam/measure-sizing` (your ask): ✅ OK to merge my part

**Your 3-line change to `_size_pick` (passing chest/hip/inseam + `usual_size` through) is approved.** I trial-merged `adam/measure-sizing` with today's `staging` (incl. #44's 3,188 products):
- **Merge:** clean, no conflicts.
- **Tests:** 530 pass.
- **Speed:** sizing every product on the Home path takes ~0.03 s for 2,000 items, so `/feed` stays fast.
- **Errors:** none on any store's size names.

**Findings from sizing the whole new catalog** (test bodies: man 178 cm / 72 kg / 39-32-38 in, woman 165 cm / 58 kg / 34-27-37 in; for your sizing PR, none block it):
1. **Princess Polly tops come out at `12` for the 165/58 woman** (31 of 40 tops, `in_your_size: true`). PP sizes **tops** in US numeric `0`–`12` (dress sizes), and it looks like the numeric path treats them as large. Expected ~`4`–`6` for a 34" bust. PP bottoms give `6` for a 27" waist, which is about right.
2. **Combined sizes aren't matched:** `XS/S` (137 Brandy Melville items), `S/M`, `M/L`, `L/XL`. Only 14 of 178 Brandy items get a size. Suggest: a combined size covers both letters.
3. **`One Size`** (now 14 Brandy items; my normalizer maps "Regular Fit" / "Oversized Fit" to it): no badge today. Suggest `your_size: "One Size"`, `in_your_size: true` when it's in stock.
4. **`usual_sizes` letter → numeric:** a usual top size `M` gives nothing on numeric-only stores (Princess Polly, 0 of 345). A letter→US-numeric map would cover it.
5. **Stüssy `XL` picks are fine:** they're `in_your_size: false` (their size sold out, nearest left), as designed.

**Also on `nabil` now (PR to follow):**
- Non-apparel is dropped by every normalizer (Uniqlo storage bags, keychains).
- Brandy's "Regular Fit" → "One Size".
- The snapshot is re-exported (still 3,188, tags kept). Re-running `load_products` (no `--replace`) picks it up; it's optional for the dry run.

## Sat 5:55 PM: sprint #2 catalog: 418 → 3,188 products, 8 stores (PR #44): **please load before the 18:30 dry run**

**3,188 products** (2,983 in stock): H&M 1,255, Uniqlo 798, Princess Polly 345, True Classic 180, Brandy Melville 178, Edikted 174, Kith 164, Stüssy 94. Every product has sizes with stock + a department (women 1,727 / men 1,170 / unisex 291), and all are AI-tagged.

**Cost:** Apify ~$2.97 for the sprint (the 3 runs you thought were lost were recovered for $0); tagging $0.73 with your `tag_catalog`. Raw pulls are in `seed/raw/`. Your files are unchanged except as noted.

- **New stores (Shopify, `autofacts/shopify`):** Princess Polly, Edikted, Brandy Melville (women), True Classic (men), Kith (men, plus women by product), Stüssy (unisex). The normalizer is `app/commerce/ingest_shopify.py`.
  - `Retailer` in `models.py` gains `princesspolly, edikted, brandymelville, trueclassic, kith, stussy` (the schema change Nabil OK'd).
  - Nessie merchants added; `/img` allows `cdn.shopify.com` (`main.py`, one line).
- **Your core, `app/lib/core/api.dart`:** please add `cdn.shopify.com` to `imageProxyHosts`, or web builds show no photos for the new stores. `GET /stores` → `[{id, name, count, departments}]` is new, if you want a core method for Ryan's onboarding chips and cart headings.
- **Sizing: the new stores' size names, for your charts:**
  - Princess Polly: women's numeric `0`–`12` ("US 4" → "4").
  - Edikted / Kith / Stüssy tops: `XS`–`XXL`.
  - Brandy Melville: `XS/S`, `One Size`.
  - True Classic: `S`–`3XL`, waist `30`–`40`, and waist×length like `32x30`.
  - Stüssy bottoms: waist `26`–`36`.
- **Pipeline changes in `ingest.py` (mine):**
  - Re-ingest keeps `label` / `pattern` / `formality` / `style_tags` / `summary`.
  - `run_actor` starts async, polls and pages, so a 502 never loses a paid run.
  - `--max-charge` is $2 per run by default (your `finder.py` live search gets the cap too).
  - `--from-dataset <id>` ingests a finished run.
- **Shared server, after #44 merges, before the 18:30 dry run** (no Apify; in this order):
  1. Pull `staging` and **restart** (new routes `GET /stores`, new `Retailer`s, the Shopify normalizer).
  2. `python -m scripts.load_products` **without `--replace`**: it upserts the 3,188 and keeps your extra ingests. The JSON store rewrites its file on every put, so expect 30–60 s.
  3. **`python -m scripts.tag_catalog --summaries-only` right after.** The snapshot has no `summary`, so the load replaces products and drops the summaries you wrote. They're cached per product id + `SUMMARY_VERSION`, so your 734 come back free; the ~2,500 new ones cost about $0.10 at your rate. `--departments-only` isn't needed: every snapshot product has a department.
  4. `warm_demo --tryons 0`, so `u_demo` / `u_adam` feed reasons cover the new items. Not `reset_demo`.
  5. Spot check: `GET /stores` lists 8 stores, and `GET /feed?user_id=u_adam` shows men's items from more than H&M/Uniqlo.
- **Still yours in the app:** `imageProxyHosts` += `cdn.shopify.com` in `app/lib/core/api.dart` (or web builds show no photos for 6 of the 8 stores), and a core method for `GET /stores` so Ryan can drop the hard-coded H&M/Uniqlo lists.
- **Sizing PR:** please include the new stores' size names above. Brandy Melville is mostly `XS/S` and `One Size` (no chart to match: treat as one size); True Classic uses `32x30` waist×length.

## Sat 4:30 PM: council-redesign backend, and what touches your code

All of this is on `nabil` (PR into `staging`). Full contracts are in `NABIL_TO_RYAN.md` (4:30 PM). **None of your files changed**; I only import from them. 370 tests pass.

- **Home `/feed` is size-first.** Each card gets `your_size` / `in_your_size`, using your `recommend_size` + `_usual_size`. The body-profile part of `POST /size` lives inside the route function, so I mirrored those ~8 lines as `_size_pick` in `commerce/router.py`; calling the route once per card was too slow. **Ask:** pull that part out as e.g. `size_for(product, body_profile)` in `ai/` so `/size` and `/feed` can't drift apart. I'll switch to it.
- **Seeded Home `/feed?seed=`:** after card 6, the cross-category "goes with it" picks use your `outfit_rules.score_product` (seed as anchor, ≥ 0.5). One `pair()` call per request, used for reasons only.
- **Discover `/search` + `/search/photo`** reuse `tag_fit`, `shop_fit`, the `/complete-look` route function and `_save_upload`. Two things for you:
  - **Complete-the-look wording:** in search, its reasons say "goes with your Baggy Barrel Jeans", but the user doesn't own the item they searched for. Search needs neutral wording, e.g. a flag that makes the anchor "this".
  - **Photo search can trigger `shop_fit`'s live H&M search** (Apify, capped at 6, cached), same as "shop this fit". Nabil OK'd it.
- **Sizing gave a women's numeric size (8)** for 178 cm / 72 kg on H&M women's jeans. I'm adding `Product.department` (men/women/unisex, from the raw scrapes; no new Apify spend) and `User.shop_for` (men/women/both, an onboarding question) to filter Home and Discover. Once that lands, sizing could use `department` too.
- **`preferred_stores` and `shop_for` are on User now:** your P1 `pair()` work can read them.
- **Your 3 PM audit:** the stuck cart (removed product → hidden, then a 409 at checkout) is fixed: the cart returns `unavailable[]` and checkout's 409 names the items. The atomic size change (Ryan's #3) is `PATCH /cart/{user_id}/items/{product_id}`. #20 (retry) is merged, so `Api.retryOrder` is unblocked.
- **After merge:** restart the shared server for the new routes, **and run `python -m scripts.load_products --replace`** (snapshot only, no re-tagging). The snapshot now has `department` on all 418 products. Until you reload it, the server's products have no department, so the men's/women's filter shows everything.

**Round two (~5:15 PM):** `Product.department` (212 women / 159 men / 47 unisex, from the raw scrapes) and `User.shop_for` (men/women/both) are in.
- **Sizing could pick the chart from `department`:** women's H&M bottoms use 0/2/4…, men's use 30/32…. Uniqlo's raw `sizeGender` shows 14 of the unisex items sized on the men's chart and 4 on the women's.
- **The filter runs after your engines:** I drop other-department items from `shop_fit` (Fit Check shop + photo search) and from complete-the-look's `goes_with`. That can leave a tag or slot empty. Filtering inside the engine (pass `shop_for` in) would fill it with a same-department match instead.
- **`ingest.normalize_hm` now sets `department`,** so live H&M search results get one too.

---

## Sat 2:45 PM: real Fit Check photos, a GPS leak, and PR #20

- **Uploads keep GPS (your `_save_upload`, `ai/router.py`).** iPhone JPEGs carry EXIF GPS. `_save_upload` writes the bytes as-is, and `/static/uploads/...` needs no key, so anyone with a photo URL can read where it was taken. That covers Fit Check posts *and* closet uploads from the app. **`post_real_fits` now re-encodes each photo** (EXIF dropped, rotation kept, max 1600 px) before upload, so the real fits are safe either way. The app path isn't fixed yet: a 5-line `ImageOps.exif_transpose` + re-save in `_save_upload` would do it. Your file, your call before the freeze.
- **`post_real_fits` tested on Nabil's backup (localhost):** 3 real photos of Nabil, all posted with 5–6 AI tags each, seeds removed. Nabil runs it on the shared URL next, as `--users u_nabil` (all 3 photos are him). **If you already replaced the seeds there, tell him**, since re-running posts again.
- **`shop_fit` on those photos, for your quality pass (not blocking):** jeans, tees, sneakers and shoes match well. Weak spots: a *striped collared shirt* gets graphic tees; a men's burgundy V-neck gets an H&M *off-the-shoulder* (women's) sweater first; *wristwatch / bracelet* get pendant necklaces (no watches in the catalog).
- **PR #20 (`POST /orders/{id}/retry`)**, the retry contract Ryan asked for. Paid purchases are never re-charged, and it's safe to call repeatedly. Not merged; team call.

---

## ☀️ Morning report (Nabil's agent, overnight Sat Oct 24, final at 8:05): **Plan confirmed**, with 2 changes

**Final checks at 7:35:** PR #14 shows MERGEABLE, staging + #15 + #14 merges clean with **275 tests passing**, and the backup server has been up all night on localhost. Staging and the handoffs were checked every 15 minutes, and no new asks for Nabil came in after 2:05 AM.

**Plan confirmed.** Changes:
1. The backup server runs on Nabil's laptop **on localhost only**. The agent wasn't allowed to open a public tunnel, and it doesn't have your `API_SHARED_KEY` (it's secret and was never shared). So Nabil starts the tunnel and swaps in your key at 9:15; it's one command, below.
2. The checkout evidence ran on the **backup** server, not the shared one, for the same reason (no shared URL or key overnight). It's the same code and the real Nessie API, so the evidence is equally real.

Everything is in **PR #14** (`nabil` → `staging`). Not merged; that's for 9:15.

### Done
| Item | Result |
| --- | --- |
| Backup server | Installed, seeded (`seed_demo` → `load_products --replace` → `seed_fitcheck`) into an **isolated data dir outside the repo**, running on `127.0.0.1:8000` with a temporary key. **`smoke_e2e`: 10/10** (feed 8/8 with reasons, size, try-on collage, complete the look, cart, checkout `paid`, Fit Check tag + shop). Without the key: 401. |
| Checkout evidence for Capital One | 3 checkouts as `u_test_checkout` (H&M only, Uniqlo only, mixed). **4/4 purchases `paid`, and all 4 appear in Nessie's `GET /accounts/{id}/purchases`.** The cart was emptied afterwards. The ids are in `docs/devpost.md` (sandbox ids, not secrets). |
| `docs/devpost.md` | Full draft: inspiration · what it does · how we built it (with your `ai-writeup.md` short version folded in) · challenges · accomplishments · learned · next. Sponsor-track table with evidence, plus the Nessie id table. **[confirm]** marks app-dependent claims. |
| `docs/demo-script.md` | A 3-minute script: hook, then the flow (who talks, what's on screen, which route), a fallback per step, the close, and a judge Q&A crib. |
| `scripts/post_real_fits.py` | Posts a photo folder over HTTP (`--base/--key`) as u_adam/u_nabil/u_ryan in turn, through multipart `POST /fitcheck` (AI pre-fills the tags). It then deletes `fc_seed_1..3`, **only if every photo posted**. Supports `--dry-run`, `--keep-seeds` and an optional `captions.txt`. |
| New route (my lane) | **`DELETE /fitcheck/{post_id}?user_id=`**, owner-only (403 otherwise, 404 if gone). The script needs it to remove the seeds over HTTP. **254 tests pass** (248 + 6 new). |

### Not done / needs a person
- **Public URL for the backup:** blocked for the agent by design. Nabil does it at 9:15.
- **Sponsor tracks to tick:** the team's call. The evidence for each is in `docs/devpost.md`. **Moss: not live** (Adam confirmed at 2:15 AM), so `devpost.md` now says don't tick it. Notability / Figma: Ryan to confirm. **Visa: never.**
- **Ryan's retry question** (`nessie_failed`): not built. The proposal is `POST /orders/{order_id}/retry`, which retries only that order's failed stores and is safe to repeat. It needs the team's OK; I didn't build it unasked.
- **`/fit`:** still off. Ryan hasn't approved it.

### Adam: after you merge #14
Restart the shared server (it adds `DELETE /fitcheck/{id}`). No reseed needed.

### Nabil at 9:15 (in order)
> The shared tunnel has been down since ~1:25 AM (Adam restarts it at 8:45, with a new URL). That makes step 2, your backup going public, the real fallback if 8:45 goes wrong.

1. **Merge order (agreed with Adam at 8:10): #15 → #14 → #13** (#13 needs Ryan's OK). **Merge PR #14** after review (its tests pass: 254). **Checked together with Adam's #15:** staging + #15 + #14 merges with no conflicts, and **275 tests pass** (re-checked at ~2:00 against the latest #15). Either order works.
2. **Backup server goes public** (it's already running on localhost):
   - Put Adam's `API_SHARED_KEY` in `backend/.env`.
   - Restart: `cd backend && pkill -f "uvicorn app.main"; DATA_DIR=~/dti-backup/data .venv/bin/uvicorn app.main:app --port 8000`
   - Tunnel: `cloudflared tunnel --no-autoupdate --url http://localhost:8000` (cloudflared is installed now).
   - Set `PUBLIC_BASE` to that URL, restart, and run `.venv/bin/python -m scripts.smoke_e2e --base <url> --key <key>`. DM the URL to Adam.
3. **9:30 real fits:** take 3 photos as JPEGs into a folder, then:
   - `python -m scripts.post_real_fits <folder> --dry-run --base <shared> --key <key>`
   - then run it again without `--dry-run`.
   - Fix tags with `PATCH /fitcheck/{id}/tags`, and check that "shop this fit" makes sense.
4. Read `docs/devpost.md` and `docs/demo-script.md`, and resolve the **[confirm]** marks with Ryan.

---

## Oct 24, ~1:05 AM: overseer check: all my items done

1. **PR #7 conflict fixed** with your exact commands. I merged `staging` and took `staging`'s copies of `ADAM_TO_NABIL.md`, `ADAM_TO_RYAN.md` and `docs/app-plan.md`. 0 conflicts, **247 tests pass**, pushed.
2. **`/fit` guest page:** asked Ryan in `NABIL_TO_RYAN.md` (OK / OK with changes / no). **Don't set `FITCHECK_EVENT_CODE` until he says yes.**
3. **NABIL_TO_RYAN is rewritten as a data-only reference:** shapes, errors and meanings. All the display guidance is removed.
4. **PR targets:** noted. Everything from me goes into `staging` (Nabil had OK'd #3 → `main` at the time; staging-only from here).
5. **Merges:** #8 and #9 are in `staging`. **#7 is merged into `staging` too** (it touches only my docs, README and commerce code). Please restart the shared server, then:
   - `python -m scripts.seed_fitcheck`, for the richer tags
   - re-run the smoke test
   - leave `FITCHECK_EVENT_CODE` unset until Ryan OKs `/fit`

---

## Oct 24, ~12:50 AM: built; ready for review in PR #7 (merge #8 first)

- **`/feed` puts ranked cards first:** the ranked list is de-duped and mixed on its own, and the unranked list is appended only if the page isn't full. There's a test for it.
- **`seed_fitcheck` tags** now carry `category`, `color`, `pattern`, `style_tags` and `brand` from the product. Re-run `python -m scripts.seed_fitcheck` on your Mac so Fit Score has data.
- **`GET /products`** (search and paging), **`POST /users`**, **`GET` / `PATCH /users/{id}`** and **`POST /onboarding`**. A rules parser fills `style_text` + `price_ranges`, which feed your `_in_budget` and `pair()`.
- **Public QR page `/fit`, `/fit/post`, `/fit/wall`, `/fit/qr`** (`app/commerce/fitcheck_web.py`). It reuses `fitcheck._auto_tags` and your `_save_upload`.
- **⚠️ Your `main.py`:**
  - I wired in the two new routers and added an `_is_open(path)` helper. The plain `"/fit"` prefix would also have opened **`/fitcheck/*`** without the key; I caught it in a smoke test.
  - Now `/fit` is matched exactly, plus `/fit/...`, and a regression test checks `/fitcheck/feed` still needs `X-DTI-Key`. Please review that block.
- **To turn the QR page on, set in your `.env`:**
  - `FITCHECK_EVENT_CODE=<any secret>`. Without it, `/fit*` returns 404.
  - Optional: `FITCHECK_RATE` (5), `FITCHECK_RATE_WINDOW` (600 s), `FITCHECK_GUEST_MAX` (200).
  - The QR points to `https://<tunnel>/fit?code=<code>`, and `/fit/qr?code=` shows that URL big (no QR library installed). Keep the code private: the repo is public.
- **Tests:** 247 pass (staging + #8 + this).

---

## Oct 24, ~12:20 AM: agreed on the app split; what I'm doing now

- **Agreed: no app screens for me.** Ryan owns the whole Flutter app and I stay on commerce. I'm not taking the Cart / Fit Check tabs; that's withdrawn from the earlier plan. If the noon checkpoint is at risk, we'll agree a whole-tab hand-off in the group chat, as your plan says.
- **In progress, all on `nabil` and landing in one PR into `staging`:**
  1. **`/feed` shows ranked cards first:** every card `pair()` ranked (with a reason) comes first, and unranked cards only fill the page after them.
  2. **`seed_fitcheck` tags** copy `category`, `color` (= `colors[0]`), `pattern`, `style_tags` and `brand` from the product.
  3. **`GET /products?q=&category=&retailer=&sort=&limit=&offset=`**: search and paging for Ryan.
  4. **Users/onboarding:** `POST /users`, `GET` / `PATCH /users/{id}`, and **`POST /onboarding {text}`**. A rules-only parser turns "Y2K, tops under $40" into `style_text` plus `price_ranges`. **It doesn't touch your `/users/{id}/style*` or `/body-photo` routes.**
  5. **QR guest posting page for Fit Check:** `GET /fit?code=…`, a no-install page where other hackers upload a fit that shows up on our wall.
- **Heads-up on `main.py` (your file):** item 5 needs `"/fit"` added to `OPEN_PREFIXES`, so those routes skip `X-DTI-Key`. They're protected by their own `FITCHECK_EVENT_CODE` (env var, off when unset), a per-IP rate limit and image checks. I'll make that one-line edit in my PR, so please review it there. On your Mac, set `FITCHECK_EVENT_CODE` in `.env` to switch it on.
- **I merged `adam/ai-pipeline` into `nabil`** so my PR builds on yours. **Merge #8 first**, then mine. I tested the two together: 211 pass.
- **README:** the root README section for the sponsor judges is mine (PR #7). The demo script and the Devpost write-up: Nabil is taking Devpost himself.

---

## Oct 24, ~12 AM: your PR #6 asks are done

- **Name hint:** `ingest.tag()` now calls `tag_product(url, hint=p["name"])`, like your `tag_catalog.py`. The vocabulary filter stays, and there's a test for it. Your name-hinted snapshot is the one we keep.
- **`store.delete`:** my private file-editing deletes are gone (wishlist DELETE in the router, and `scripts/load_products.py`). Both use your `store.delete()` now, so nothing writes the JSON files directly.
- **`fetch_hm` / `normalize_hm` keep their names,** since your live search depends on them.
- **New: root `README.md`** has a "Where Apify and Capital One Nessie run" section for the sponsor judges. It credits Claude in one line and links to your `ADAM.md` and the AI section of `backend/README.md`. Please don't duplicate it; add your Anthropic section separately if you want one in the root README.
- 195 tests pass on `nabil`, which is merged with staging at `c31c147`.

---

## Oct 23, ~11:15 PM: you're good to host; catalog tagging is done on my side; staging needs a catch-up

- **Hosting:** confirmed, you host on your Mac. Nabil is DMing you the `NESSIE_API_KEY` and `APIFY_TOKEN` for your `.env` (never commit them). Without the Nessie key, checkout falls back to `pending_nessie`. Ryan gets the tunnel URL and `X-DTI-Key` from you.
- **PR #3 was merged into `main`, not `staging`.** Its base got switched, so `staging` was missing Nessie, Fit Check, the snapshot and `NABIL_TO_RYAN.md`. My new PR from `nabil` into `staging` brings staging level with main, so everyone reads handoffs and branches from the same code.
- **Catalog tagging:** Nabil passed me your Anthropic key, so **I ran the tag pass here**. `seed/products.json` now has `label`, `pattern`, `formality` and `style_tags` for all products, in the same PR. **Skip your tag pass**: just `git pull`, then `python -m scripts.load_products --replace` on your Mac.
- **Still open on your side:** `memory._from_store` should also read the `wishlist` collection. Saves made through `PUT /wishlist` write no swipe, so style memory misses them when Moss is off.

---

## Oct 23, ~10:45 PM: snapshot PR is up; answers to your ADAM_TO_NABIL

**PR #3 into `staging`** (`nabil` is merged with staging at `4e44cdb`, and 136 tests pass):
- **Catalog snapshot:** `backend/seed/products.json` holds **418 products**: H&M 290 (including **48 shoes**, as you asked) and Uniqlo 128. Load it with `python -m scripts.load_products`.
  - Now filled in: `images[]` (H&M 2–6 `retailer_model` shots, Uniqlo 1 `product` shot) and `description` (Uniqlo 117 of 128; H&M none, because the actor returns no text).
  - The raw pulls are in `seed/raw/*.gz`, so anyone can re-normalize with no Apify spend.
- **Real Nessie checkout** (`app/commerce/nessie.py`): one merchant per retailer and one customer/account per user, cached in store doc `nessie`; one purchase per store; `GET /orders/{user_id}`.
  - Nessie quirks: amounts are stored as **integers** (we send `round()`), and **https only**.
- **Fit Check:** `/fitcheck` (post, feed, detail, PATCH tags, `/shop` → your `shop_fit`, like, comment), friends-only. `tagged` is stored through `FitTag(**t).model_dump()`, so your new fields survive. Demo posts: `python -m scripts.seed_fitcheck`.
- **Wishlist split from swipes:** `PUT/DELETE /wishlist/{user}/items/{product}` writes the `wishlist` collection and **no swipe**, so a save doesn't dismiss the item from the feed. It calls `record_swipe(..., "wishlist")` only on the first save.
- **`/feed` now passes `k=min(24, limit*2)`,** as you suggested.
- **Checkout returns 409** if something sold out after it was added to the cart.

**Things that touch your code:**
1. **The memory fallback misses PUT saves.** Without Moss, `memory._from_store` reads only `swipes`, so saves made through `PUT /wishlist` (which write no swipe) don't reach style memory. One fix on your side: also read `store.list("wishlist", user_id=...)` as likes. Docs are `{user_id, product_id, saved_at}`.
2. **`fitcheck.py` imports your private `_save_upload` from `app/ai/router.py`.** Please don't rename it, or tell me if you do. Uploads land in `uploads/`, which your new static mount still serves.

**Your questions and decisions:**
- **Hosting on your Mac:** agreed. Your `.env` will need `NESSIE_API_KEY` (otherwise checkout falls back to `pending_nessie`) and `APIFY_TOKEN`; Nabil is sending both privately. On first checkout, Nessie merchants and accounts get created fresh on your machine; that's fine.
- **Tagging:** yes, please tag on your Mac once PR #3 lands: `python -m scripts.load_products`, then re-run ingest with tagging on, then `python -m scripts.export_products` and push the tagged snapshot. The commands:
  ```
  python -m scripts.ingest --from-file "seed/raw/hm_*.json.gz" --retailer hm
  python -m scripts.ingest --from-file seed/raw/uniqlo_20261023.json.gz --retailer uniqlo
  ```
  They re-normalize from the raw pulls with no Apify spend. About 418 × $0.0002.
- **`staging` → `main`:** OK from me **once PR #3 is merged into staging**. Nothing else of mine is unpushed.
- **Apify:** Nabil got $200 in credits, so live search is fine. Keep the per-item caps, please.

---

## What landed (PR #1, which you merged into `staging`)

- **Ingest:** `app/commerce/ingest.py` and `python -m scripts.ingest` handle H&M (`gauzy_penguin/HM-Product-Scraper`) and Uniqlo (`abotapi/uniqlo-com-scraper`). Everything is validated with `Product(**p)`, not `to_canonical`, because `to_canonical` quietly turns unknown categories into `top`.
- **Catalog:** 370 real products (H&M 242, Uniqlo 128). By category: top 178, outerwear 89, bottom 82, dress 21. **No shoes or accessories yet.** A committed snapshot plus `python -m scripts.load_products` is coming in my next PR, so whoever hosts the server gets the same 370 products.
- **Commerce router:** `/feed`, `/products/{id}`, `/swipe`, `/cart`, `/wishlist`, `/checkout`. Shapes are in `NABIL.md`.

## Things that touch your code

1. **`/swipe` writes the `swipes` collection.** Doc id `"{user_id}:{product_id}"`, fields `{user_id, product_id, action, swipe, size, at}`.
   - `action` uses your words: `cart` / `wishlist` / `discard`. `swipe` keeps the app's words: `like` / `save` / `discard`.
   - Before this, nothing wrote `swipes`, so `memory._from_store` and `pair()`'s "already swiped" logic had no data without Moss.
   - I still call `memory.record_swipe(user_id, product, action)` with your word.
2. **`/feed` calls `pair(user_id, candidate_ids, k=min(50, limit*3))`.** That ranks a wider pool than one page so I can de-duplicate styles and mix stores. With Claude live, that's up to 50 reasons per call. Your 10-minute cache helps, but tell me if you'd rather I keep `k=limit`.
3. **My feed collapses colour variants to one card per style** (same retailer + name). H&M lists each colour as its own article, so without this the feed showed the same "Harper" jeans five times.
4. **Tags at ingest:** the 370 products were loaded with `--no-tag` because I had no AI key then. So `label`, `pattern` and `formality` are empty, and `style_tags` is `[]`. Categories are rule-based.
   - Fix: re-run `python -m scripts.ingest --from-file ...` with your key set, about 370 × $0.0002, roughly $0.07.
   - Can you run it on your machine, or should I put an `ANTHROPIC_API_KEY` in my `.env`?
5. **Images for try-on:**
   - **Uniqlo** `image_url` = a garment-only photo per colour, the best for try-on.
   - **H&M** `image_url` = a model wearing the item (`model_image?imwidth=657`). There's no flat-lay for adult items.

## In progress on my side

- **Real Nessie checkout:** the key works over **https only** (`https://api.nessieisreal.com`). It creates one merchant per retailer, one customer and account per user, and one purchase per store. It also adds `GET /orders/{user_id}`.
- **Product snapshot plus loader,** described above.
- **Next:** `GET /fitcheck/{post_id}/shop` → `ai.service.shop_fit(viewer_id, post["tagged"])`, plus Fit Check post storage.

## Questions for you

1. **Fit Check posts:** I'll store `fitcheck_posts` as `{id, user_id, photo_url, caption, tagged: [FitTag], created_at, likes: [], comments: []}`, with `tagged` coming from your `/ai/tag-fit`. Does that match what `shop_fit` expects, or do you want extra fields?
2. **`APIFY_TOKEN`** for your live search: Nabil will send it to you privately. It is **not** in any committed file, because the repo is public.
3. **Who hosts the shared backend** (ngrok or Render)? You run it on your Mac today. If that's still the plan, run `python -m scripts.load_products` there once my next PR lands.
4. **`POST /complete-look`** (your new endpoint): should `/feed` or the cart screen call it, or does Ryan call it directly?
