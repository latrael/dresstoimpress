# NABIL_TO_RYAN.md

Notes from Nabil (commerce lane) to Ryan (app). Newest notes go at the top. Reply in `RYAN_TO_NABIL.md` on your branch; I read it every time I start work. For AI calls (size, try-on, complete the look, closet), see Adam's `ADAM_TO_RYAN.md`.

**Last updated:** Sat Oct 24, 2026, ~12:50 AM PT. Lives on `staging` (via PRs from `nabil`).

---

## Oct 24, ~12:50 AM: new routes are built (on `nabil`, PR #7 into `staging`)

**Onboarding**, a rules parser, free and instant:
```
POST /onboarding {"display_name": "Mia", "text": "Y2K, tops under $40"}     (user_id optional; updates if it exists)
-> {"user": {"id": "u_mia-a1b2", "display_name": "Mia", "style_text": "Y2K, tops under $40",
             "price_ranges": {"top": [0.0, 40.0]}, "body_photo_url": null, "friends": ["u_adam","u_nabil","u_ryan"]},
    "parsed": {"styles": ["y2k"], "budgets": {"top": [0.0, 40.0]}, "unmatched": ""}}
```
- **What the parser understands:** "under/below/max/up to $X", "$20-$60", "between 20 and 60", "around $50", and "everything under $50" (all categories). Category words: tops/tees/hoodies → top, jeans/pants/skirts → bottom, jackets/coats → outerwear, sneakers/boots → shoes, dresses → dress. Plus the 10 style words and some synonyms.
- **Show `parsed`** as confirmation chips. `unmatched` is whatever it didn't understand.
- **Other user routes:** `POST /users {display_name, style_text?, price_ranges?, friends?}` (409 if the id exists), `GET /users/{id}` (404 if missing), and `PATCH /users/{id}` (new `style_text` re-parses and merges the budgets).
- **Adam's routes are unchanged:** `/users/{id}/body-photo` and `/users/{id}/style*`.

**Search and paging:**
```
GET /products?q=blue jeans&category=bottom&retailer=hm&sort=relevance|price_asc|price_desc&limit=24&offset=0
-> {"items": [Product...], "total": 79, "limit": 24, "offset": 0, "next_offset": 24}     (next_offset is null at the end)
```
- Every word in `q` must match name, label, brand, style tags or colours.
- `in_stock=true` is the default. A bad `sort` returns 422.
- `GET /products/{id}` still works for ids that contain `:`.

**`/feed`:** every AI-ranked card (with a `reason`) comes first; unranked cards only fill the rest of the page.

**QR guest page:** not part of the app. Other hackers scan a QR code at our table, which opens `/fit?code=…`, and they can post a fit without installing anything. Their posts are `visibility: "public"`, so they show in everyone's `GET /fitcheck/feed`.

---

## Oct 24, ~12:20 AM: you own the whole Flutter app; new backend routes coming for you

- **Screens:** per Adam's revised `docs/app-plan.md`, **you build every tab** (including Cart / Checkout / Fit Check), continuing your FlutterFlow design in plain Flutter. I'm **not** building app screens, so there's no shared-screen confusion. Nice work on Quick Browse and the 4 widget tests.
- **Cart and checkout behaviours your UI needs** (shapes are below in this file):
  - group the cart by `retailer`
  - checkout `status`: `paid`, or `nessie_failed` → show a retry
  - **409**: `detail` is an *object* (`detail.message` + `detail.unavailable`); keep the cart on screen
  - `GET /orders/{user}` for the receipt history
- **New routes landing in my next PR (I'll confirm here when merged):**
  - **`POST /onboarding {user_id?, display_name?, text}`** for your onboarding screen. It turns "Y2K, tops under $40" into style plus per-category budgets, and returns `{user, parsed: {styles, budgets, unmatched}}` so you can show "Got it: Y2K · tops under $40". Also `POST /users`, and `GET` / `PATCH /users/{id}`.
  - **`GET /products?q=&category=&retailer=&sort=relevance|price_asc|price_desc&limit=24&offset=0`** → `{items, total, limit, offset, next_offset}`, for search and browse-by-category.
  - **`/feed` puts every AI-ranked card (with a `reason`) first;** unranked cards come only after them. Keep hiding empty reasons.
  - **QR guest page (`/fit?code=…`):** not in the app. It's a web page for other hackers at our table, and their posts show up in the Fit Check feed as `visibility: "public"`.
- **Images:** load product photos through the backend's `/img?url=` helper (no key needed), as Adam's plan says. Direct retailer URLs fail in the browser.

---

## Reply to your RYAN_TO_NABIL.md (on staging)

All 5 requests are **implemented**, and the details are in the sections below:

| # | Request | Status |
|---|---|---|
| 1 | Gallery at ingest | ✅ All 418 products. H&M has 2–6 `retailer_model` photos; Uniqlo has 1 `product` photo (garment only), so hide the dots. Same product and colour, no duplicates, and `images[0]` is the same as `image_url`. |
| 2 | Descriptions | ✅ Plain text, otherwise null. Uniqlo 117 of 128 have one. **H&M is always null**: the scraper returns no text, and we don't invent any. |
| 3 | Same fields everywhere | ✅ `/feed`, `/products/{id}`, `/wishlist` and the nested cart `product` all return the stored Product unchanged, so the gallery and description match. |
| 4 | Repeat-safe wishlist | ✅ `PUT/DELETE /wishlist/{user_id}/items/{product_id}` plus `GET /wishlist/{user_id}/ids`. Saving doesn't dismiss the item from the feed, a repeated PUT doesn't add a duplicate memory event, and legacy `/swipe save` still works. |
| 5 | Integration readiness | ✅ Routes, examples and errors are below. The URL and `X-DTI-Key` come privately from Adam, who hosts. |

**New:** products now carry AI tags (`label` e.g. "olive long sleeve t-shirt", `style_tags`, `pattern`, `formality` 1–5). You can show `label` or `style_tags` as chips if you want.

**Remaining gaps:**
- No descriptions for H&M.
- Uniqlo has 1 photo per product.
- Fit Check seed posts use placeholder photos until we take real fits at the venue.

---

## TL;DR

- **Your `ryan-nabil.md` requests are all done:** image gallery, description, repeat-safe wishlist routes and the sale-price fix. Details and examples are below.
- **Backend:** runs on Adam's Mac behind a tunnel. The URL and the `X-DTI-Key` header value come **privately** in the group chat, never in Git. Set the header once on the FlutterFlow API group. Demo user: `u_demo`.
- **Catalog:** 418 real products. H&M 290 (including 48 shoes) and Uniqlo 128. By category: top 178, outerwear 89, bottom 82, shoes 48, dress 21.
- **Checkout makes real Capital One Nessie purchases,** one per store.
- **Fit Check backend is live:** `/fitcheck/...`, listed below.

## Product fields you can rely on

`id, retailer, name, brand, category, price_usd, sale_price_usd, colors, sizes[{name, in_stock}], in_stock, image_url, product_url, images[{url, kind}], description` (plus the tagger fields `style_tags, pattern, formality, label`; Adam is filling these in).

- **Price:** if `sale_price_usd` isn't null, charge and show it, with the original `price_usd` struck through next to it. Otherwise show `price_usd`. (NABIL.md had this backwards; it's fixed.)
- **Gallery `images`:** never empty for ingested products, and `images[0]` is always the same as `image_url`. Every photo is the same product and the same colour; no borrowed photos and no duplicates.
  - **H&M:** 2–6 photos each (most have 5). All are `kind: "retailer_model"`, because H&M's data doesn't flag garment-only shots.
  - **Uniqlo:** exactly 1 photo each, `kind: "product"` (garment only). Show one image with no dots.
- **`description`:** plain text, possibly with `\n` and `- ` bullet lines.
  - **H&M:** always `null`, because the H&M scraper doesn't return text. Show your honest "no description" state.
  - **Uniqlo:** 117 of 128 have real text.

Multi-photo example (H&M):
```json
{"id": "hm:1354978001:dark-blue-las-vegas", "retailer": "hm", "name": "Oversized Printed Hoodie",
 "image_url": "https://image.hm.com/assets/hm/b0/83/b083de23a414fca6ab17c8c16a276875659ac038.jpg?imwidth=657",
 "images": [
  {"url": "https://image.hm.com/assets/hm/b0/83/b083de23a414fca6ab17c8c16a276875659ac038.jpg?imwidth=657", "kind": "retailer_model"},
  {"url": "https://image.hm.com/assets/hm/e0/fa/e0fa993871b40f9c182ea591f6ae6e6ce02370f0.jpg?imwidth=657", "kind": "retailer_model"},
  {"url": "https://image.hm.com/assets/hm/64/e1/64e113fab7213e309b6bad0bb764fb9d40375a3b.jpg?imwidth=657", "kind": "retailer_model"}],
 "description": null}
```
Single-photo example (Uniqlo):
```json
{"id": "uniqlo:E488230-000:brown", "retailer": "uniqlo", "name": "SUPIMA® Cotton T-Shirt | Long Sleeve",
 "image_url": "https://image.uniqlo.com/UQ/ST3/us/imagesgoods/488230/item/usgoods_35_488230_3x4.jpg",
 "images": [{"url": "https://image.uniqlo.com/UQ/ST3/us/imagesgoods/488230/item/usgoods_35_488230_3x4.jpg", "kind": "product"}],
 "description": "- Ribbed binding at the collar helps the neckline keep its shape."}
```

## Routes (all need the `X-DTI-Key` header)

Errors always come back as `{"detail": ...}`.

### Browse
| Call | Returns |
|---|---|
| `GET /feed?user_id=u_demo&limit=20&category=&retailer=` | `[Product + reason, score, pairs_with]`. One card per style, and stores and categories alternate. **Excludes anything already sent to `/swipe`.** The first load takes a few seconds (AI ranking), and later loads come from the cache. |
| `GET /products/{id}` | one Product, or 404 `{"detail":"unknown product"}` |

### Save, separate from the feed (your Quick Browse double-tap)
| Call | Returns |
|---|---|
| `PUT /wishlist/{user_id}/items/{product_id}` | `{user_id, product_id, saved: true}`. Repeat-safe, and **the item stays in the feed**. 404 for an unknown product. |
| `DELETE /wishlist/{user_id}/items/{product_id}` | `{user_id, product_id, saved: false}`. Repeat-safe, never 404s. |
| `GET /wishlist/{user_id}` | `[Product]`, newest first |
| `GET /wishlist/{user_id}/ids` | `["hm:…", "uniqlo:…"]`, to set up the hearts on launch |

### Swipe (only for a deliberate keep/skip; never for photo or vertical browsing)
`POST /swipe {user_id, product_id, action: "like"|"save"|"discard", size?}` returns `{user_id, product_id, action, in_cart}`.
- **Any `/swipe` call removes the product from that user's feed.**
- `like` with a `size` also adds it to the cart. `save` also writes the wishlist.
- A sold-out size gives 422.

### Cart and checkout
| Call | Returns |
|---|---|
| `POST /cart/{user_id}/items {product_id, size, qty=1}` | Cart. 422 `{"detail":"size M is sold out for <name>"}` or `{"detail":"size XXXL is not offered for <name>"}` |
| `GET /cart/{user_id}` | `{user_id, groups:[{retailer, items:[{product_id, size, qty, added_at, product}], subtotal_usd}], total_usd, count}` |
| `DELETE /cart/{user_id}/items/{product_id}?size=M` | Cart. Leave out `size` to remove every size of that product. |
| `POST /checkout/{user_id}` | `{order_id, purchases:[{retailer, merchant_id, amount_usd, items, status, nessie_id}], total_usd, created_at}`. `status` is `"paid"` (a real Nessie purchase) or `"nessie_failed"` (the order is kept; show a retry message). |
| `GET /orders/{user_id}` | past orders, newest first |

**Checkout errors:**
- **400** `{"detail":"cart is empty"}`
- **409** if something sold out after it was added: `{"detail":{"message":"size M is sold out for <name>","unavailable":[{"product_id":"…","size":"M"}]}}`. Nothing is charged and the cart is left as it was, so keep the user's picks on screen and show `message`.
- Note that `detail` is an **object** on 409 but a string everywhere else.

### Fit Check (OOTD)
A post is `{id, user_id, photo_url, caption, tagged:[{label, retailer, product_id, category, color, …}], created_at, likes, comments, visibility}`, plus `author{id, display_name}`, `like_count`, `liked_by_me` and `comment_count`.

| Call | Returns |
|---|---|
| `POST /fitcheck` | JSON `{user_id, photo_url, caption?, tagged?}`, or multipart (`user_id`, `file`, `caption?`). With no tags, the AI pre-fills them from the photo (takes a few seconds). Returns the post. |
| `GET /fitcheck/feed?user_id=u_demo&limit=20` | friends' and own posts, newest first |
| `GET /fitcheck/{post_id}?user_id=` | the post. 404 if it's not visible to this user (friends only). |
| `PATCH /fitcheck/{post_id}/tags {user_id, tagged}` | the owner fixes wrong AI tags; 403 for anyone else |
| `GET /fitcheck/{post_id}/shop?user_id=` | **"Shop this fit"**: buyable Products plus `reason`, `pairs_with`, `score`, `matched_tag` |
| `POST /fitcheck/{post_id}/like {user_id}` | toggles: `{post_id, liked, like_count}` |
| `POST /fitcheck/{post_id}/comments {user_id, text≤280}` | the new comment plus `comment_count` |

Demo data: `python -m scripts.seed_fitcheck` creates 3 posts, from Adam, Nabil and Ryan, that u_demo can see. They use placeholder photos, so we'll swap in our real fits at the venue.

## What I need from you

1. **Your API group:** the base URL plus the `X-DTI-Key` header, both from the group chat. Test with `GET /health` (no key needed) and then `GET /feed?user_id=u_demo&limit=5`.
2. **Tell me in `RYAN_TO_NABIL.md`** if any shape above is awkward for FlutterFlow. For example, if you want the 409 `detail` flattened, or `description` as a single line.
3. **Status of the FlutterFlow input/automation blocker** in your RYAN.md. Is Quick Browse buildable tonight? The Saturday-noon end-to-end run needs feed → save/cart → checkout on the phone.
