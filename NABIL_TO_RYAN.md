# NABIL_TO_RYAN.md

Notes from Nabil (commerce backend) to Ryan (app owner). This file lives on `staging`; reply in `RYAN_TO_NABIL.md`. It states **data facts only**: route shapes, errors, and what each field means. **How anything looks or behaves in the app is your call.** For AI routes (size, try-on, complete the look, closet, style, Fit Score), see `ADAM_TO_RYAN.md`.

**Last updated:** Sun Oct 25, 2026, ~1:30 AM PT. New: the Home reels data is on `/feed` (`hero_image_url`, `closet_picks`, `tryon`).

## Oct 25, ~1:30 AM: the Home reels data (sprint-4 §10) is on `/feed`

The full shapes are in `docs/schema.md` → "Home reels". Every `/feed` card (plain and `?seed=`) now has:
- **`hero_image_url`:** slide 1, the garment alone. It's never null on a card: when the store only has model shots it falls back to `image_url`.
  - Coverage: a real product-only photo for 941 / 3,188 products (all of Kith and Stüssy, 99% True Classic, 34% H&M, 8% Uniqlo, ~2% Princess Polly, none for Brandy Melville and Edikted, which only shoot on models). The rest fall back to `image_url`, so slide 1 always has a photo.
- **`closet_picks`:** slide 3, `[{id, label, category, image_url}]`, 0–4, one per square, from Adam's `closet_picks`. Accessories show here but never go into the try-on render. It's `[]` for an empty closet, so build the "+ add from your closet" tiles.
- **`tryon`:** slide 2, `{status, image_url?, mode?}`.
  - `ready` → show `image_url` (`mode` `ai`).
  - `pending` → shimmer + "Dressing you…".
  - `none` → not started yet.
  - `needs_photo` → the "Add a photo of you" card.
  - `unavailable` → no image (since #92 there's no collage): the "try-on unavailable" card with retry.
  - It's the try-on of exactly the pieces in that card's `closet_picks`.
- **Pre-loading:**
  - `POST /feed/{user}/tryons {product_ids: [≤5]}` → `{id: tryon}` starts the next posts' try-ons. Call it on load for posts 1–3, then for n+1…n+3 as the user lands on post n.
  - `GET /feed/{user}/tryons?ids=a,b` → poll every ~3 s while a visible post is `pending`.
  - Each user has a daily AI pre-render budget (`PREFETCH_PER_USER_DAY`); past it, cards say `unavailable`.
- **Live on the shared server** once Adam deploys (his next step 1). The core fields, methods and mocks are already in Adam's #66 (`heroImageUrl`, `closetPicks`, `tryOn`, `prefetchTryOns`, `tryOnStatus`).

---

## Oct 25, ~12:30 AM: Sprint #4 is the design overhaul; most of it is yours. Please read `docs/sprint-4.md`

The full spec, with file:line pointers, is in `docs/sprint-4.md`. Your items, in order:
1. **Edge-to-edge (§1):** the black band at the top on the iPhone 16 and the Pixel 9 Pro comes from the global `SafeArea` at `main.dart:183`.
2. **Tokens + motion (§3)** and **bundled fonts (§2.3).**
3. **Shell (§4):** the lowercase serif wordmark, 3 icons + an avatar, a more transparent glass nav pill, swiping between tabs.
4. **Home as reels (§6):** one post per screen. A 3-slide carousel (the item → on you → a 2×2 grid of your closet), "see more", Add to cart as the only button.
5. **Onboarding (§5):** a welcome page with the arch animation and an outfit mosaic; slide transitions; animated chips.
6. **Discover (§7):** width-fit photos, opened products use the Home post.
7. **Inspo and the rest (§8):** the restyle.

**Font bank: decided, C (Young Serif + Manrope).** Preview it in `docs/sprint-4/font-banks.html`. Young Serif has one weight, so never bold it; the rules are in §2. The new `/feed` fields (`hero_image_url`, `closet_picks`, `tryon`) are specified in §10; Adam ships core mocks first, so you can build Home before the backend lands. Please post before/after screenshots from both phones (§11).

---

## Oct 24, ~11:30 PM: acted on your READY signal; comments trimmed in post views

- **Every post view (`GET /fitcheck/feed`, `GET /fitcheck/{id}`, `POST /fitcheck`, `PATCH …/tags`):**
  - `comments` = only the **2 newest**, oldest → newest.
  - Each one is now shaped like a paged item: `{id, user_id, author: {id, display_name}, text, created_at}`.
  - `comment_count` = the total. Everything else is unchanged.
- I read your code against it: `models.dart:1216/1221` and `social_feed.dart:229/283/501` take the count from `comment_count`. `comments_sheet.dart` seeds from the preview, loads the page and never lowers the total. Nothing should break, and the preview now shows real names instead of user ids.
- **Shop the look (`GET /fitcheck/{id}/shop`, flat and `grouped=true`):**
  - The men's/women's filter now runs before picking matches, so each piece fills up with items in the viewer's department (e.g. 2/6 → 6/6).
  - Same shape as before.
- **Camera search (`POST /search/photo`):** the same fix, so the similar items are ones you can buy in your department.
- Live on the shared server once Adam merges and restarts.

---

## Oct 24, ~7:50 PM: sprint #3 Inspo backend (`docs/sprint-3.md` 3.1, 3.3, 3.4)

All additive; nothing you use today changes.
- **Instant likes (3.3): `PUT /fitcheck/{post_id}/like` `{user_id, liked: true|false}`** → `{post_id, liked, like_count}`.
  - Setting the same state twice is a no-op, so it's safe to retry or queue. Flip the heart locally, send this in the background, and roll back only on an error.
  - Unliking something never liked → `liked: false`, count unchanged. 404 unknown post. The old toggle `POST …/like` still works.
- **Comment sheet (3.4): `GET /fitcheck/{post_id}/comments?user_id=&limit=20&before=<comment_id>`** → `{post_id, comment_count, comments: [{id, user_id, author: {id, display_name}, text, created_at}], next_before}`.
  - Each page runs oldest → newest, so you can show newest at the bottom.
  - No `before` = the newest page. Pass `next_before` to load older comments; it's null when there are none left.
  - `limit` is clamped to 1–100. 422 if `before` isn't a comment on that post.
  - `POST …/comments` now also returns `author`.
- **Photo sizes (3.1):** every post (create, feed, detail, tags, `/fit/wall`) has `photo_w`, `photo_h` (pixels, or null).
  - Uploads are measured on the server, upright. **JSON posts with a `photo_url` may send `photo_w` + `photo_h`** (both or neither, 1–20000); otherwise they're null.
  - Layout (decided): width-fit, tall photos capped at **9:16** and centre-cropped. With null sizes, measure the image after it loads.
- **Coming later (decided, waits on your comment sheet):** the feed and detail responses will carry `comment_count` + the **2 newest comments** only (a "View all N comments" preview), instead of every comment. I'll switch it once your sheet uses the paged GET. Tell me when.
- **Faster everywhere:** server-side, Home (`/feed`) was taking ~70 s on the 3,188-product catalog; it's now ~0.2 s once Adam restarts the server on this code. Search is ~4× faster too.

## Oct 24, ~5:45 PM: way more clothes (sprint #2)

- **Catalog:** 418 → **3,188 products** (2,983 in stock). Every one has `department` (women 1,727 / men 1,170 / unisex 291) and sizes with stock. Live on the shared server once Adam loads it (before the 18:30 dry run).
  - H&M 1,255, Uniqlo 798.
  - **New:** Princess Polly 345, Brandy Melville 178, Edikted 174 (women's); True Classic 180 (men's); Kith 164 (mostly men's); Stüssy 94 (unisex).
  - Accessories are new too (bags, caps, beanies, belts, jewelry): `category: "accessory"`.
- **`retailer` can now be** `princesspolly, edikted, brandymelville, trueclassic, kith, stussy` as well as `hm, uniqlo`. The app hard-codes H&M/Uniqlo in two places that will show raw ids otherwise:
  - `retailerName()` in `cart_screen.dart`.
  - The Stores step in `onboarding_screen.dart` (+ `store_controller.dart`).
- **`GET /stores`** (key required, like every route) → `[{id, name, count, departments: {men, women, unisex}}]`, biggest first, in-stock counts only. Use `name` for cart headings and the list for the onboarding chips, so new stores show up without an app change. `departments` lets you hide a women's-only store for someone shopping men's.
- **Size names from the new stores:**
  - Princess Polly: `0`–`12`.
  - Brandy Melville: `XS/S`, `One Size`.
  - True Classic jeans/chinos: `32x30` (waist×length).

  These are the exact strings to send back as `size`.
- **Images for the new stores are on `cdn.shopify.com`.** The `/img` proxy allows it; Adam's core `imageProxyHosts` needs it too (asked). Until then, web builds show no photos for 6 of the 8 stores; the phone builds load them directly.
- **To do on your side:**
  1. **Cart headings:** `retailerName()` in `cart_screen.dart` → use `name` from `GET /stores`. Otherwise new stores show as "princesspolly".
  2. **Onboarding Stores step** (`onboarding_screen.dart`, `store_controller.dart`): build the chips from `GET /stores` instead of `['hm','uniqlo']`. Optionally hide stores with no items in the user's `shop_for` department.
  3. The "We currently carry H&M and Uniqlo" line in onboarding is out of date: 8 stores now.
- **Summaries:** Adam's #40 `summary` (1–2 sentences) is on products after he re-runs it post-load; `blurb()` already prefers it.

 (on `nabil`, PR into `staging`)

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
- **Vibe search is in `GET /search`:**
  - A sentence (3+ words, e.g. "fit for a rooftop party") or a query with no keyword hits goes through Adam's `vibe()`. Exact keyword matches still come first.
  - The response adds `vibe: {styles, categories, colors, keywords, source} | null`. You can show it as "Showing: streetwear · black".
- **Your contract questions (RYAN_TO_ADAM 424dcf3):**
  - **Clearing a skipped budget:** `PATCH /users/{id}` replaces `price_ranges` as a whole. Send the dict without the skipped category, or `{}` to clear every budget. `null` / leaving it out keeps the saved one.
  - **`preferred_stores` / `onboarded` / `shop_for`:** `PATCH` changes only the fields you send. `preferred_stores` is replaced as a whole list.
  - **`usual_sizes`:** Adam's `body_profile` (`PATCH /users/{id}/body-profile`), not on User.
  - **An unmatched Inspo tag** (no `product_id`): `GET /search?q=<tag label>` gives you the similarity search.
  - **Trending:** global engagement first (`trend_count > 0`), then your personal feed (`trend_count: 0`). They aren't interleaved; tell me if you want them mixed.
  - **Dart core methods for these routes:** Adam's `app/lib/core`. The contracts above are final for this PR.

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

`id, retailer, name, brand, category, price_usd, sale_price_usd, currency, colors, sizes[{name, in_stock}], in_stock, image_url, product_url, images[{url, kind}], description, style_tags, pattern, formality, label, scraped_at, source, department, summary`

- **Catalog:** 3,188 products from 8 stores (see the 5:55 PM note at the top). By category: top 1,562, bottom 785, outerwear 296, accessory 226, shoes 168, dress 151.
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
- H&M and some Shopify items have no retailer `description`. Adam's `summary` covers them.
- Uniqlo has 1 image per product.
- Shopify images are all `kind: "retailer_model"` (the stores don't mark garment-only shots).
- Fit Check seed posts use placeholder photos.
