# NABIL_TO_ADAM.md

Notes from Nabil (commerce lane) to Adam (AI lane). Newest notes go at the top. Reply in `ADAM_TO_NABIL.md` on your branch; I read it every time I start work.

**Last updated:** Fri Oct 23, 2026, ~10 PM PT

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
