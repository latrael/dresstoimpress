# NABIL.md: data and commerce status

What Adam and Ryan need from my layer: Apify ingest, the products DB, `/feed`, `/swipe`, `/cart`, `/checkout` and Fit Check storage. I update this file whenever something changes, and the newest changes go at the top of the changelog.

**Last updated:** Sat Oct 24, 2026, ~12:50 AM PT. Handoffs: [`NABIL_TO_ADAM.md`](NABIL_TO_ADAM.md) · [`NABIL_TO_RYAN.md`](NABIL_TO_RYAN.md) (full route list with shapes)

---

## TL;DR

- **The schema is LOCKED.** The source of truth is `backend/app/models.py` → `Product` (see `docs/schema.md`). My earlier draft (`price`, `url`, `tags{}`, `inStock`) is retired; use `price_usd`, `product_url`, `colors[]`, `sizes[{name, in_stock}]`, `style_tags`, `pattern`, `formality`, `label`, and singular `category`.
- **The feed is built on H&M and Uniqlo.** Both return real per-size stock on our free Apify plan with no proxy, and neither has a run cap. Zara and Mango are optional extras later.
- **Products are a snapshot.** They're scraped once at ingest and the feed serves them from the store. Nothing is scraped live during the demo, except Adam's Fit Check lookups (`source: "live_search"`).
- **The demo's H&M top stays.** H&M sizes and stock are confirmed real.
- **Catalog: 418 products** (H&M 290 including 48 shoes, Uniqlo 128), committed at `backend/seed/products.json`. Load it with `python -m scripts.load_products`. Every product has an `images[]` gallery; Uniqlo also has a `description`.
- **Checkout makes real Nessie purchases** (one per store). **Fit Check backend is live.** **Hosting:** Adam's Mac behind a tunnel, with the URL and `X-DTI-Key` shared privately.

---

**Adam's answers to my earlier asks** (tagger values, `/pair` shape, `/size`, Fit Check endpoints) are in [`ADAM.md`](ADAM.md) and [`docs/schema.md`](docs/schema.md).

## Ingest: H&M + Uniqlo

```
Apify actor (one run per retailer) ──> normalize to Product ──> tag (Adam's POST /products/tag) ──> store "products" ──> /feed
```

| | H&M | Uniqlo |
|---|---|---|
| Actor | `gauzy_penguin/HM-Product-Scraper` | `abotapi/uniqlo-com-scraper` |
| Input | keywords, e.g. `"womens tops, baggy jeans, y2k"`, `Country: en_us` | category names, e.g. `"women t-shirts"`, `country: us`, `fetchDetails: true` |
| Cost | $0.004/item | $0.08/run + ~$0.003/item, so batch into one run |
| One product = | one H&M article (each colour is its own article) | **one colour** of a Uniqlo product |
| `id` | `hm:{article_id}:{color}` | `uniqlo:{productId}:{color}` |
| Sizes / stock | `sizes[].in_stock` (real) | per-colour variants. **`LOW_STOCK` counts as in stock** |
| Image | `model_image?imwidth=657` (a person wearing it) | `colors[].imageUrl` (**garment only**, the best for try-on) |
| Filtering | **drop `kids_*` categories** (up to ~60% of results) | none needed |
| Category | rule-mapped from H&M's category string, tagger as fallback | rule-mapped from `categoryPath`, tagger as fallback |

**Run it** (once `APIFY_TOKEN` is in `backend/.env`):
```bash
cd backend && source .venv/bin/activate
python -m scripts.ingest                 # default keywords/categories → store "products"
python -m scripts.ingest --dry-run       # preview, no save
python -m scripts.ingest --from-file data/raw/hm_*.json --retailer hm   # re-normalize a saved pull, no Apify
```
More flags: `--hm "baggy jeans,y2k" --uniqlo "men jeans,women t-shirts" --per 5`, `--no-tag`, `--show N`. Don't mix retailers in one `--from-file` glob.

**First real load (Oct 23, from the saved raw pulls): 370 products.** H&M 242 (34 maternity, 4 kids and 20 duplicates dropped) + Uniqlo 128 (49 products × up to 3 colours). By category: top 178, outerwear 89, bottom 82, dress 21. There are **no shoes or accessories** in the data yet.

## API (commerce router, Nabil)

| Method | Path | What it does |
|---|---|---|
| GET | `/feed?user_id=&limit=20&seed=` | Home: in-stock, in-budget, not-yet-swiped products, ordered by Adam's `pair()`, **in-your-size first**. Each card adds `reason`, `score`, `pairs_with`, `your_size`, `in_your_size`. `seed=` → that product first, then similar (same category first); `&seed_shown=true` on later reloads drops the seed card. Filtered by `User.shop_for`; preferred stores 2:1 |
| GET | `/search?user_id=&q=` | Discover text search → `{query, similar, goes_with}` (goes_with = complete the look around the top result, closet first) |
| GET | `/search/styles?user_id=&limit=` | Discover idle: `{styles:[{tag,count}], trending:[Product+trend_count]}` |
| POST | `/search/photo` (multipart `user_id`, `file`) | Discover photo search → `{photo_url, tags, similar, goes_with}`; no post or closet item created |
| GET | `/products?q=&category=&retailer=&sort=&limit=&offset=` | search and paging → `{items, total, limit, offset, next_offset}` |
| GET | `/products/{id}` | one product |
| POST | `/onboarding` `{user_id?, display_name?, text}` | "Y2K, tops under $40" → user `style_text` + `price_ranges`, plus `parsed` chips |
| POST · GET · PATCH | `/users`, `/users/{id}` | create, read and update a user (Adam owns `/users/{id}/style*` and `/body-photo`) |
| GET · POST | `/fit?code=`, `/fit/post`, `/fit/wall`, `/fit/qr` | **public QR page** for guest Fit Check posts. Needs `FITCHECK_EVENT_CODE`; no `X-DTI-Key` |
| POST | `/swipe` `{user_id, product_id, action, size?}` | `like` (right → cart if a size is given), `save` (down → wishlist), `discard` (left). Feeds Adam's style memory |
| POST | `/cart/{user_id}/items` `{product_id, size, qty}` | add to cart; 422 if the size is sold out |
| GET | `/cart/{user_id}` | cart **grouped by retailer**, with subtotals and a total, plus `unavailable[]` (sold out / left the catalog; not in totals) |
| PATCH | `/cart/{user_id}/items/{product_id}` `{size, new_size}` | change size in one write: quantity kept, merges into an existing line; 404 / 409 |
| DELETE | `/cart/{user_id}/items/{product_id}?size=` | remove an item |
| PUT / DELETE | `/wishlist/{user_id}/items/{product_id}` | save / unsave. Repeat-safe, and does **not** remove the item from the feed |
| GET | `/wishlist/{user_id}` · `/wishlist/{user_id}/ids` | saved products (newest first) · just their ids |
| GET | `/orders/{user_id}` | past orders |
| POST | `/orders/{order_id}/retry?user_id=&retailer=` | re-attempt only this order's `nessie_failed`/`pending_nessie` store purchases; `paid` ones are never re-charged, so it's repeat-safe. 404 / 403 not owner / 503 no key |
| * | `/fitcheck…` | post, feed (**everyone's posts**, `?author=`), detail, PATCH tags, DELETE, `/shop`, like, comment. See NABIL_TO_RYAN.md |
| POST | `/checkout/{user_id}` | one **real Nessie purchase** per retailer (`paid` / `nessie_failed`). 409 if a size sold out since it went in the cart, and nothing is charged |

Shapes:
- **Feed card** = full `Product` + `reason`, `score`, `pairs_with[]`. One card per style (colour variants are collapsed), and stores and categories alternate. If `pair()` returns fewer cards than `limit`, it tops up with unranked cards (`reason: ""`).
- **Cart** = `{user_id, groups:[{retailer, items:[{product_id, size, qty, added_at, product}], subtotal_usd}], total_usd, count}`. It uses `sale_price_usd` when set.
- **Checkout** = `{order_id, purchases:[{retailer, merchant_id, amount_usd, items, status}], total_usd}`. It returns 400 if the cart is empty.
- **Swipe** returns `{user_id, product_id, action, in_cart}`. Any swipe removes the product from that user's feed. `like` with a sold-out size returns 422.

## What I need from you

### Adam
- **FYI on swipes:** `/swipe` now writes the `swipes` collection (`{user_id, product_id, action, swipe, size, at}`, doc id `user:product`). Before this, nothing wrote it, so your memory fallback had no data without Moss. `action` uses your words (`cart`/`wishlist`/`discard`), and `swipe` keeps the app's word (`like`/`save`/`discard`).
- `/fitcheck/{post_id}/shop` → `shop_fit()` is next on my list.
- Otherwise nothing blocking. I'm using `to_canonical`, `tag_product`, `pair()` and `record_swipe()` as documented in `docs/schema.md` and `backend/README.md`.
- FYI: H&M images show a person wearing the item. Uniqlo images are garment-only, so Uniqlo items are the safest for try-on demos.

### Ryan
- **Feed cards:** `image_url`, `name`, `brand`, `price_usd`, `retailer` and `sizes` are always present. When `sale_price_usd` isn't null, it's the price to charge and show; strike through the original `price_usd` next to it. (Corrected: this was reversed before.)
- **Size picker** before add-to-cart: grey out sizes where `in_stock: false`.
- **Cart and checkout confirmation:** group by `retailer` (H&M and Uniqlo for the demo).
- Real products should be in the store tonight. Until then, `python -m scripts.seed_demo` gives you mock data in the same shape.

## Apify findings (reference)

| Retailer | Best actor | Sizes | Stock | Status |
|---|---|---|---|---|
| **H&M** | `gauzy_penguin/HM-Product-Scraper` | ✅ | ✅ | **in the feed** |
| **Uniqlo** | `abotapi/uniqlo-com-scraper` | ✅ | ✅ | **in the feed** |
| Zara | `parseforge/zara-scraper` (`fetchProductDetails: true`) | ✅ | ✅ | extra; **10 items per run on the free plan** |
| Mango | `mrdoe/fashion-multi-scraper-us` + a live `mangoCategoryUrl` | ✅ | ❌ (assume in stock) | extra. Live URLs: `https://shop.mango.com/us/en/c/women/{tops/227371cd, jeans/164d8c42, coats/d1b967bc}` |
| ASOS | `nifty.codes/asos-listingdetails-scraper` (product URLs only) | text | partial | skipped: UK store, GBP prices, ~30s per item |

**Dead ends:**
- `mrdoe/fashion-multi-scraper-us`: no sizes for Zara, H&M or ASOS, and 0 items for Uniqlo.
- Zara: `shahidirfan` and `karamelo` returned no sizes. `abotapi` needs a paid proxy.
- Uniqlo: `rl1987` crashed and `mrdoe` returned 0 items.
- ASOS: `shahidirfan` doesn't return real sizes.
- Mango: `abotapi` needs a paid proxy.

A paid Apify plan or hackathon credits would unlock Zara at full volume and real Mango stock. I'm asking at the booth.

## Risks

- **Nessie** stores amounts as integers (we round), and it's https only. Without a key on the host, checkout falls back to `pending_nessie`.
- **Hosting** depends on Adam's Mac and tunnel staying up through judging.
- **Style keywords are loose** on H&M (it has no y2k tag), so Adam's tagger supplies the real `style_tags`.

## Changelog

- **Oct 24, ~5:15 PM:** `Product.department` (backfilled from raw: 212 women / 159 men / 47 unisex) + `User.shop_for` filter Home, Discover and shop-this-fit; `seed_shown`; 2:1 store mix; Discover size-first; cart lines keep `image_url`. 411 tests.
- **Oct 24, ~4:30 PM:** Council redesign backend: Home size-first + `?seed=`, `preferred_stores` / `onboarded` on User, Discover `/search`, `/search/styles`, `/search/photo`, atomic cart size change, unavailable cart items, Inspo for everyone. 370 tests.

- **Oct 24, ~2:20 PM:** `POST /orders/{order_id}/retry` (Ryan's ask): per-store payment retry, repeat-safe, owner-only.

- **Oct 24, ~12:50 AM:** Onboarding + users, product search and paging, feed puts ranked cards first, Fit Check seed tags, public QR guest page. Caught and fixed a `/fit` prefix that would have opened `/fitcheck/*` without the key. 247 tests. No app screens for Nabil: Ryan owns the Flutter app.

- **Oct 23, ~10:45 PM:** Real Nessie checkout, Fit Check backend, 418-product snapshot (with shoes), galleries and descriptions, repeat-safe wishlist, checkout 409 on a stock change. Apify: $200 in credits secured, $2.43 spent.

- **Oct 23, ~9 PM:** Ingest CLI and commerce router built (84 tests pass). 370 real H&M and Uniqlo products loaded. Merged Adam's staging update; his notes to me are covered here (see ADAM.md).
- **Oct 23, ~8 PM:** Schema locked to `models.py` (on `staging`). Ingest built around H&M and Uniqlo. Commerce router and ingest CLI in progress on `nabil`.
- **Oct 23 (evening):** Uniqlo works through `abotapi` with real stock. Mango works through the multi-scraper (sizes, no stock flags). H&M stock confirmed real.
- **Oct 23 (later):** Found actors that return sizes for H&M, Zara (capped at 10 items) and ASOS (UK only).
- **Oct 23:** First schema and pipeline proposal. The multi-store actor returned no sizes.
