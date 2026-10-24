# NABIL_TO_RYAN.md

Notes from Nabil (commerce backend) to Ryan (app owner). This file lives on `staging`; reply in `RYAN_TO_NABIL.md`. It states **data facts only**: route shapes, errors, and what each field means. **How anything looks or behaves in the app is your call.** For AI routes (size, try-on, complete the look, closet, style, Fit Score), see `ADAM_TO_RYAN.md`.

**Last updated:** Sat Oct 24, 2026, ~4:30 PM PT. New: the backend for the council redesign (`docs/council-final-sprint.md`): Home size-first + seeded feed, Discover search, cart size change + unavailable items, Inspo for everyone.

## Oct 24, ~4:30 PM: backend for the council redesign (on `nabil`, PR into `staging`)

Every change only adds fields; nothing the app reads today was removed or renamed. Round two (~5:15 PM) is in the same PR, listed first.

**Round two (~5:15 PM)**
- **Men's / Women's / Both (onboarding question, decided by Nabil):**
  - `User.shop_for: "men" | "women" | "both"`, default `"both"`. Send it on `POST /onboarding`, `POST /users` or `PATCH /users/{id}`; anything else → 422.
  - `"men"` shows men's + unisex items; `"women"` shows women's + unisex.
  - It applies to Home (the seed card itself always shows), Discover search, photo search, trending and the style counts, Inspo's "shop this fit", and `GET /products?department=`.
  - Every product now has `department: "men" | "women" | "unisex" | null` (null = unknown, e.g. a live search result, shown to everyone).
- **Seeded Home, what the app must send:**
  - First load after a tag or result tap: `GET /feed?seed=X`. The seed is card 1.
  - Every later reload of that same seeded Home: `GET /feed?seed=X&seed_shown=true`. Same "similar to X" feed, without the seed card.
  - A new tap (even on the same X) or clearing the "Similar to" chip → start again without `seed_shown`.
- **Store mix:** with `preferred_stores` set, each size group shows 2 preferred-store cards per other-store card.
- **Discover is size-first too:** `/search` and `/search/photo` `similar` items and trending cards carry `your_size` / `in_your_size`, with in-your-size first. `goes_with` is built around the first card shown.
- **Cart lines carry `image_url`** (the product's main photo, saved when added), including the lines in `unavailable[]`, so a removed item still shows its picture.

**User profile** (`GET/PATCH /users/{id}`)
- `preferred_stores: ["hm","uniqlo"]`: onboarding screen 3. Default `[]`.
- `onboarded: bool`: set it to `true` at the end of onboarding. Onboarding never resets it.
- Measurements, fit and usual sizes are Adam's `PATCH /users/{id}/body-profile` (already merged).

**Home: `GET /feed?user_id=&limit=&seed=`**
- Every card adds `your_size` and `in_your_size`:
  - `your_size` (string or null): the size `POST /size` would pick, from in-stock sizes only.
  - `in_your_size: true`: we have their real size.
  - `in_your_size: false`: their size is sold out, and `your_size` is the nearest size left (or null).
  - `in_your_size: null`: we know nothing about their size, or can't size this item.
- **Order:** in-your-size cards first, then the rest. Nothing is hidden for size.
- **`seed=<product_id>`** (the "Similar to …" mode you open from an Inspo tag or a Discover result):
  - Card 1 is the seed, even if it's sold out or over budget, so show it marked.
  - Next come mostly the same category, most similar first. From card 7, about every 4th card is a piece from another category that goes with the seed.
  - 404 `unknown product` if the id isn't in the catalog.

**Discover**
- **`GET /search?user_id=&q=`** → `{query, similar: [Product], goes_with: [...]}`.
  - `similar`: up to 24 items, one per style, in stock.
  - `goes_with`: complete the look around `similar[0]`. Each entry is a Product + `{from_closet: false, reason}`, or a closet item + `{from_closet: true, reason}`. Closet pieces can't go to the cart or to seeded Home.
  - Blank `q` → empty lists (the idle screen is `/search/styles`). If the AI is down, `goes_with` is `[]`.
- **`GET /search/styles?user_id=&limit=8`** → `{styles: [{tag, count}], trending: [Product + {trend_count}]}`.
  - `styles` are the chips: the 10 catalog style tags, most common first.
  - `trending` = users who saved it + users who carted it + users who ordered it. When that's thin, it tops up from their feed with `trend_count: 0`.
- **`POST /search/photo`** (multipart `user_id` + `file`; camera or camera roll) → `{photo_url, tags, similar, goes_with}`.
  - `similar` items also carry `reason`, `score`, `matched_tag`.
  - It creates no post and no closet item. GPS is stripped.
  - No garments found → 200 with empty lists. AI down → 502 "photo search is unavailable right now…". 415 / 413 for a bad file.
  - It can search H&M live (Apify) when a piece isn't in the catalog. That's capped and cached.

**Cart**
- **`PATCH /cart/{user_id}/items/{product_id}`** `{size, new_size}`: the pencil, done in one write.
  - Keeps the quantity, and merges into an existing line of `new_size`.
  - 200 → the same shape as `GET /cart`. Same size → no-op.
  - 404: that line isn't in the cart.
  - 409 `detail` is a readable string ("size XL is sold out for …").
- **`GET /cart` adds `unavailable: [{product_id, size, qty, name, product|null, available: false, unavailable_reason}]`.**
  - `unavailable_reason` is "no longer available", "size sold out" or "size no longer offered".
  - These lines aren't in `groups` or the totals. Every grouped item now has `available: true`.
  - `count` includes unavailable lines, so a cart holding only those isn't "empty".
  - Remove them with the existing `DELETE`.
- **Checkout 409** `unavailable[]` entries now carry `{product_id, size, name, reason}`. Nothing is charged and the cart is kept.

**Inspo: `GET /fitcheck/feed?user_id=&limit=&author=`**
- Everyone sees every post (decision D4). `author=<user_id>` returns one person's posts.
- Detail, like, comment and shop no longer 404 for non-friends.

**Your ask #4 (onboarding price text):** it works as you send it ("tops under $30.0, bottoms under $45.5, jackets under $80.0, shoes under $120.0"). jackets/coats map to `outerwear`. "max", "up to", ranges and the category after the price also work.

> **Oct 24, ~2:20 PM: order retry route (your ask).** `POST /orders/{order_id}/retry?user_id=&retailer=` re-attempts only that order's `nessie_failed` / `pending_nessie` store purchases (or just the one `retailer`). A `paid` purchase is never charged again, so it's **safe to call repeatedly**: an all-paid order comes back unchanged with no Nessie call. 200 returns the same shape as `/checkout` (`{order_id, purchases, total_usd, created_at}`); a purchase that fails again stays `nessie_failed` with a new `error` and `retried_at`. Errors: 404 unknown order (or no purchase for that `retailer`), 403 `user_id` isn't the order's owner, 503 no Nessie key on the server (nothing changes). No stock re-check (the order already exists). It's on the backend once the PR is merged; not in the Dart client (Adam's core / your lane).

---

## Needs your decision

1. **The `/fit` guest page.** This is a small public web page I built: other hackers scan a QR code at our table, upload an outfit photo without installing anything, and it lands in the Fit Check feed as a public post.
   - **It's off** until you OK it. It only turns on when Adam sets `FITCHECK_EVENT_CODE` on the server.
   - It's a user-facing surface, so its look is your call. I can change or restyle anything, or drop it entirely.
   - Routes: `GET /fit?code=` (page), `POST /fit/post`, `GET /fit/wall`, `GET /fit/qr`.
   - **Please reply in `RYAN_TO_NABIL.md`:** OK as is, OK with changes, or no.
2. **Your RYAN_TO_NABIL** still lists the old split. Current split: **you own all screens**, and Adam and I are backend only.

3. **Retrying `nessie_failed`** (your question): **built**, see the Oct 24 ~2:20 PM note at the top and the orders table below.

## Connection

- **Base URL and key:** Adam's tunnel URL plus the `X-DTI-Key` header value, sent privately. Never in git; the repo is public.
- **Open routes** (no key needed): `GET /health`, `/static/...`, `/img?url=` (Adam's image proxy), and `/fit*` (which uses its own event code).
- **Demo user:** `u_demo`.

## Product (shared schema: `backend/app/models.py`)

`id, retailer, name, brand, category, price_usd, sale_price_usd, currency, colors, sizes[{name, in_stock}], in_stock, image_url, product_url, images[{url, kind}], description, style_tags, pattern, formality, label, scraped_at, source`

- **Catalog:** 418 products. H&M 290, including 48 shoes; Uniqlo 128. By category: top 178, outerwear 89, bottom 82, shoes 48, dress 21.
- **`sale_price_usd`:** the price charged at checkout when it's not null; `price_usd` is the regular price.
- **`images`:** never empty for catalog products, and `images[0]` is always the same as `image_url`. Same product and colour only, with no duplicates.
  - **H&M:** 2–6 images, all `kind: "retailer_model"` (H&M's data doesn't mark which shots are garment-only).
  - **Uniqlo:** exactly 1 image, `kind: "product"` (garment only).
- **`description`:** plain text, which may contain `\n` and `- ` bullet lines.
  - **Uniqlo:** 117 of 128 have one.
  - **H&M:** always `null` (the scraper returns no text).
- **`label`, `style_tags`, `pattern`, `formality` (1–5):** AI tags, filled in for all 418 products.
- **`sizes[].in_stock`:** false means that size can't be added to the cart (422).
- **Retailer image URLs** don't load directly in a browser build. `/img?url=` serves them; it's Adam's.

## Routes (all need `X-DTI-Key` unless noted)

Every error comes back as `{"detail": ...}`.

### Browse
| Call | Returns |
|---|---|
| `GET /feed?user_id=&limit=20&category=&retailer=` | `[Product + reason, score, pairs_with]`. All AI-ranked cards (with a `reason`) come first; any unranked cards after them have `reason: ""`. One card per style, stores and categories alternate, and only in-budget, in-stock products the user hasn't swiped. The first load is slower (AI ranking, ~7 s), later loads are cached. |
| `GET /products?q=&category=&retailer=&in_stock=true&sort=relevance\|price_asc\|price_desc&limit=24&offset=0` | `{items: [Product], total, limit, offset, next_offset}`. `next_offset` is null on the last page. Every word in `q` must match the name, label, brand, style tags or colours. A bad `sort` returns 422. |
| `GET /products/{id}` | one Product; ids that contain `:` work. 404 `{"detail":"unknown product"}` |

### Users and onboarding
| Call | Returns |
|---|---|
| `POST /onboarding {user_id?, display_name?, text}` | `{user: User, parsed: {styles: [..], budgets: {category: [min, max]}, unmatched: ".."}}`. Creates the user if missing, otherwise updates their `style_text` and merges budgets. New users get `u_adam`, `u_nabil` and `u_ryan` as friends (when those exist). |
| `POST /users {id?, display_name, style_text?, price_ranges?, friends?}` | User. 409 if the id exists; 422 for bad ranges. |
| `GET /users/{id}` · `PATCH /users/{id} {display_name?, style_text?, price_ranges?, friends?}` | User, or 404. A new `style_text` without `price_ranges` re-parses and merges the budgets. |

- **Example:**
  ```
  POST /onboarding {"display_name": "Mia", "text": "Y2K, tops under $40"}
  -> {"user": {"id": "u_mia-a1b2", "display_name": "Mia", "style_text": "Y2K, tops under $40", "price_ranges": {"top": [0.0, 40.0]}, "body_photo_url": null, "friends": ["u_adam","u_nabil","u_ryan"]},
      "parsed": {"styles": ["y2k"], "budgets": {"top": [0.0, 40.0]}, "unmatched": ""}}
  ```
- **What the parser understands:**
  - **Budgets:** "under/below/max/up to $X", "$20-$60", "between 20 and 60", "around $50" (→ ±30%), and "everything under $50" (all categories).
  - **Category words:** tops/tees/hoodies → top; jeans/pants/skirts → bottom; jackets/coats → outerwear; sneakers/boots → shoes; dresses → dress; bags → accessory.
  - **Styles:** the 10 style words plus synonyms.
  - A bare number without `$` or a keyword is ignored.
- **Not mine:** `/users/{id}/style*` and `/users/{id}/body-photo` are Adam's.

### Save (independent of the feed)
| Call | Returns |
|---|---|
| `PUT /wishlist/{user_id}/items/{product_id}` | `{user_id, product_id, saved: true}`. Repeat-safe. **Doesn't remove the item from `/feed`.** 404 for an unknown product. |
| `DELETE /wishlist/{user_id}/items/{product_id}` | `{user_id, product_id, saved: false}`. Repeat-safe, never 404s. |
| `GET /wishlist/{user_id}` · `GET /wishlist/{user_id}/ids` | saved Products, newest first · their ids |

### Swipe
`POST /swipe {user_id, product_id, action: "like"|"save"|"discard", size?}` returns `{user_id, product_id, action, in_cart}`.
- **Any `/swipe` removes the product from that user's `/feed`.**
- `like` with a `size` also adds it to the cart; `save` also writes the wishlist.
- A sold-out size gives 422.

### Cart, checkout and orders
| Call | Returns |
|---|---|
| `POST /cart/{user_id}/items {product_id, size, qty=1}` | Cart. 422 `{"detail":"size M is sold out for <name>"}` or `{"detail":"size XXXL is not offered for <name>"}` |
| `GET /cart/{user_id}` | `{user_id, groups: [{retailer, items: [{product_id, size, qty, added_at, product}], subtotal_usd}], total_usd, count}`. Subtotals use `sale_price_usd` when set. |
| `DELETE /cart/{user_id}/items/{product_id}?size=` | Cart. Leaving out `size` removes all sizes of that product. |
| `POST /checkout/{user_id}` | `{order_id, purchases: [{retailer, merchant_id, amount_usd, items, status, nessie_id?}], total_usd, created_at}`, with one Capital One Nessie purchase per retailer. |
| `GET /orders/{user_id}` | past orders, newest first: `[{id, user_id, purchases, total_usd, created_at}]`. **The order id is `id` here, and `order_id` in the `/checkout` response** (same value). Each purchase also has `nessie_account_id`. |
| `POST /orders/{order_id}/retry?user_id=&retailer=` | Same shape as `/checkout`. Re-attempts only this order's `nessie_failed` / `pending_nessie` purchases (all stores, or just `retailer`); `paid` ones are never touched, so it's safe to repeat. 404 unknown order or retailer, 403 not the owner, 503 no Nessie key. |

- **Checkout `status`:**
  - `paid`: a real Nessie purchase, with `nessie_id` set.
  - `nessie_failed`: the order is saved, but that store's payment failed.
  - `pending_nessie`: there's no Nessie key on the server.
- **Checkout errors:**
  - **400** `{"detail":"cart is empty"}`
  - **409** when something sold out since it was added: `{"detail": {"message": "size M is sold out for <name>", "unavailable": [{"product_id": "…", "size": "M"}]}}`. Nothing is charged and the cart is left as it was. Note that `detail` is an **object** here and a string on every other error.

### Fit Check
A post is `{id, user_id, photo_url, caption, tagged: [{label, retailer, product_id, closet_item_id, category, color, pattern, style_tags, brand}], created_at, likes, comments, visibility}`, plus `author {id, display_name}`, `like_count`, `liked_by_me` and `comment_count`.

| Call | Returns |
|---|---|
| `POST /fitcheck` | JSON `{user_id, photo_url, caption?, tagged?, visibility?}`, or multipart (`user_id`, `file`, `caption?`). With no tags, the AI fills `tagged` from the photo (a few seconds). Returns the post. |
| `GET /fitcheck/feed?user_id=&limit=20` | the user's own posts, friends' posts and public posts, newest first |
| `GET /fitcheck/{post_id}?user_id=` | the post. 404 if it's not visible to that user. |
| `PATCH /fitcheck/{post_id}/tags {user_id, tagged}` | the post. 403 if the caller isn't the owner. |
| `GET /fitcheck/{post_id}/shop?user_id=` | buyable Products plus `reason`, `pairs_with`, `score`, `matched_tag` |
| `DELETE /fitcheck/{post_id}?user_id=` | `{post_id, deleted: true}`. 403 if the caller isn't the owner; 404 if it's gone or not visible. **New.** |
| `POST /fitcheck/{post_id}/like {user_id}` | toggles the like: `{post_id, liked, like_count}` |
| `POST /fitcheck/{post_id}/comments {user_id, text}` | `{id, user_id, text, created_at, comment_count}`. `text` is 1–280 characters, else 422. |

- **Demo data:** `python -m scripts.seed_fitcheck` creates 3 posts (from Adam, Nabil and Ryan) visible to `u_demo`. Their photos are placeholders.

## Known gaps
- H&M has no descriptions.
- Uniqlo has 1 image per product.
- The catalog is H&M + Uniqlo only.
- Fit Check seed posts use placeholder photos.
