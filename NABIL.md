# NABIL.md: data and commerce status

What Adam and Ryan need from my layer (Apify ingestion, product DB, feed, cart, Nessie checkout). I update this file whenever something changes, and the newest changes go at the top of the changelog.

**Last updated:** Thu Oct 23, 2026

---

## TL;DR

- **Product schema below is a proposal.** We lock it at the Friday 6 PM schema meeting, so please read it before then.
- **Sizes are the main risk.** The multi-store Apify actor (`mrdoe/fashion-multi-scraper-us`) returned **no sizes for any retailer** we tested, and returned nothing at all for Uniqlo. Sizes will come from a second pass that scrapes each product's own page.
- **Products are a snapshot.** We scrape them once at ingest and the feed serves them from the DB. Nothing is scraped live during the demo.
- **Demo retailer may change.** The demo script uses an H&M top. That holds only if H&M sizes work, and I'll confirm by Saturday noon.

---

## From Adam (Oct 23, 7:40 PM): schema locked on `staging`, AI endpoints ready

**Schema:** the unified Product shape is in `backend/app/models.py` and explained in [`docs/schema.md`](docs/schema.md). It keeps your `id` format and sizes-with-stock (as `in_stock`, snake_case), with singular categories (`top`) and `price_usd` / `product_url` / `colors[]` / `style_tags[]`. Your example product in the new shape is in `docs/schema.md`. To save products: `p = to_canonical(raw)` from `app.ai.compat` (validates, converts this doc's shape too). Please branch off `staging` and open PRs into `staging`.

**Answers to "What I need from you → Adam":**
- **Tagger endpoint:** `POST /products/tag {image_url}` returns `label`, `category`, `color`, `pattern`, `style_tags`, `formality` (1–5), plus a `tags` object in this doc's shape. Values: pattern `solid|striped|plaid|graphic|floral|other`; style from y2k, streetwear, minimalist, preppy, athleisure, vintage, business, boho, grunge, classic. Cached per image (Haiku, about $0.0002 each).
- **Pairing endpoint:** `POST /pair {user_id, candidate_product_ids[]}` returns `[{id, product_id, score, reason, pairs_with[]}]`, best first. Falls back to a rules-based ranker if Claude is down, so `/feed` never breaks.
- **Also available:** `POST /size` (size advice, never a sold-out size), `POST /ai/shop-fit` (Fit Check post → buyable products), `POST /ai/tag-fit` (outfit photo → item tags). Fit Check live lookups write products with `source: "live_search"`; your ingest stays the main feed.

Status of the AI side: [`ADAM.md`](ADAM.md) and [`docs/progress.md`](docs/progress.md).

---

## Product schema (original proposal; superseded by docs/schema.md)

Every product the feed returns looks like this:

```json
{
  "id": "asos:211172667:ivory",
  "retailer": "asos",
  "name": "Topshop knitted high neck ribbed sweater lace detail in ivory",
  "price": 96.73,
  "currency": "USD",
  "sizes": [{ "name": "S", "inStock": true }, { "name": "M", "inStock": false }],
  "image_url": "https://images.asos-media.com/products/.../211172667-1-white",
  "url": "https://www.asos.com/.../prd/211172667",
  "category": "tops",
  "color": "ivory",
  "tags": {
    "category": "tops",
    "color": "ivory",
    "pattern": "solid",
    "style": ["cozy", "minimal"],
    "formality": "casual"
  },
  "scraped_at": "2026-10-24T02:16:01Z"
}
```

| Field | Notes |
|---|---|
| `id` | `{retailer}:{productCode}:{color}`. It stays the same across scrapes, so it's safe to store in carts, wishlists and OOTD tags. |
| `retailer` | One of `zara`, `hm`, `asos`, `uniqlo`, `mango`. Each retailer maps to one Nessie merchant at checkout. |
| `sizes` | Always a non-empty list. A product without sizes never reaches the feed. |
| `tags` | **Same schema as Adam's closet tagger.** Products and closet items get tagged the same way so pairing compares like with like. |

## Pipeline

```
Apify listing scrape ──> validate ──> tag (Adam's tagger) ──> size scrape ──> products DB ──> /feed
   (pass 1: name,         (drop bad      (cached once        (pass 2: product     (snapshot)
    price, image, url)     price/image)   per product)         page → sizes)
```

1. **Pass 1, discovery:** scrape category pages for name, price, image and url.
2. **Validate:** drop items whose price or image is broken.
3. **Tag:** run every product image through Adam's tagger once and cache the result.
4. **Pass 2, sizes:** scrape product pages, only for items that survive the filters, to get sizes and stock.
5. **Serve:** `/feed` filters by the user's style and price range, then orders by Adam's pairing ranks.

## What I need from you

### Adam
- **Tagger endpoint:** a product image goes in, the `tags` object above comes out. Can the field names and allowed values for `pattern`, `style` and `formality` be agreed Friday at 6?
- **Pairing endpoint:** I'll send the closet plus about 50 candidate product `id`s. I need back a ranked list of `{id, reason}`.

### Ryan
- **Feed cards:** you can rely on `image_url`, `name`, `price`, `retailer` and `sizes` always being present.
- **Size picker:** it's needed before add-to-cart, and sold-out sizes (`inStock: false`) should be greyed out.
- **Cart:** items can come from several retailers. The checkout confirmation is grouped by `retailer`, with one Nessie purchase per store.
- **Mock data:** the JSON example above is safe to build screens against until real data arrives.

## API (planned, all on the shared FastAPI service)

| Method | Path | Returns |
|---|---|---|
| GET | `/feed?user_id=` | ranked list of products |
| GET | `/products/{id}` | one product |
| POST | `/cart/{user_id}/items` | add `{product_id, size}` |
| GET | `/cart/{user_id}` | cart grouped by retailer |
| POST | `/checkout/{user_id}` | one Nessie purchase per retailer, plus a confirmation |

## Apify findings so far

| Retailer | Listing scrape | Sizes? | Notes |
|---|---|---|---|
| Zara | works | no | |
| H&M | works | no | |
| ASOS | works (10/10) | no | No `category` either; the tagger will have to fill it in. |
| Uniqlo | **0 items** | no | Failed twice, so it looks broken. |
| Mango | **0 items** | no | The default URL is a dead summer-sale page. Not retested yet. |

**Next:** find single-store actors that return sizes, test them on about 5 items each and update this table.
**Fallback:** if none work, the feed uses only the retailers we *can* get sizes for. Building our own sizes actor is the stretch goal, and it also doubles as an entry for Apify's $400 Best Actor prize.

## Risks

- **No retailer returns sizes yet.** If pass 2 fails, we cut down to whichever stores work.
- **Zara and H&M block scrapers.** Their product pages may need residential proxies.
- **Rule #1: no code before the Friday opening.** Until then this file is design only.

## Changelog

- **Oct 23:** Proposed the schema and pipeline. Ran the Apify size test: no retailer returns sizes, and Uniqlo and Mango returned nothing.
