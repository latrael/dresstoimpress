# NABIL_TO_ADAM.md

Notes from Nabil (commerce lane) to Adam (AI lane). Newest notes go at the top. Reply in `ADAM_TO_NABIL.md` on your branch; I read it every time I start work.

**Last updated:** Sat Oct 24, 2026, ~2:45 PM PT. Lives on `staging` (via PRs from `nabil`).

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
