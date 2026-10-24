# NABIL_TO_ADAM.md

Notes from Nabil (commerce lane) to Adam (AI lane). Newest notes go at the top. Reply in `ADAM_TO_NABIL.md` on your branch; I read it every time I start work.

**Last updated:** Sat Oct 24, 2026, ~12:20 AM PT. Lives on `staging` only (via PRs from `nabil`).

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
