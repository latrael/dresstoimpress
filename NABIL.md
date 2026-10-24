# NABIL.md: data and commerce status

What Adam and Ryan need from my layer (Apify ingestion, product DB, feed, cart, Nessie checkout). I update this file whenever something changes, and the newest changes go at the top of the changelog.

**Last updated:** Thu Oct 23, 2026

---

## TL;DR

- **Product schema below is a proposal.** We lock it at the Friday 6 PM schema meeting, so please read it before then.
- **Sizes: mostly solved.** The multi-store actor gives no sizes, but single-store actors return real per-size stock for H&M and Zara, and for ASOS through product URLs. See "Apify findings" below. Uniqlo and Mango aren't covered yet.
- **Products are a snapshot.** We scrape them once at ingest and the feed serves them from the DB. Nothing is scraped live during the demo.
- **Demo retailer may change.** The demo script uses an H&M top. That holds only if H&M sizes work, and I'll confirm by Saturday noon.

---

## Product schema (proposal)

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

### Single-store actors that DO return sizes (tested Oct 23, 5 items each)

| Retailer | Actor | Sizes format | Notes |
|---|---|---|---|
| H&M | `gauzy_penguin/HM-Product-Scraper` | `[{size, stock, in_stock}]` | Searches by keyword, US store, about 5s per run, $0.004/item. **Best H&M option.** |
| H&M | `mrdoe/hm-product-scraper-us` | `[{name, inStock}]` | Takes a category URL and shows real out-of-stock sizes, but it's slow (about 2 min) and uses residential proxies. |
| Zara | `parseforge/zara-scraper` | `[{size, availability, sku}]` | Takes a category URL with `fetchProductDetails: true`, about 9s per run. **Our free Apify plan caps it at 10 items per run.** |
| ASOS | `nifty.codes/asos-listingdetails-scraper` | text, e.g. `"XS - UK 4-6, S - UK 8-10"` | Needs product URLs, so it's pass 2 only. **It returns the UK store, prices in GBP**, and takes about 30s per URL. |

**Uniqlo: `abotapi/uniqlo-com-scraper` works with no proxy.**
- **Input that worked:** `{"mode":"search","country":"us","categories":["women t-shirts"],"maxItems":N,"fetchDetails":true,"proxy":{"useApifyProxy":false}}`
- **Per-colour, per-size stock** in `variants[]`: `{colorName, sizeName, stockStatus, stockQuantity, inStock}`.
- **Low stock shows up as `inStock: false`.** Count a size as available when `stockStatus != "STOCK_OUT"`, and build the size list from `variants`, not from `availableSizes`.
- **Cost:** a $0.08 fee per run plus about $0.003 per item, so batch large runs; 100 items is about $0.36. It has clean product-only images per colour (`colors[].imageUrl`).
- `rl1987/uniqlo-api-scraper` crashed, and `mrdoe/uniqlo-product-scraper-us` returned 0 items.

**Mango: sizes, but no stock flags, on the free plan.**
- `mrdoe/fashion-multi-scraper-us` works with a **live** `mangoCategoryUrl`, e.g. `https://shop.mango.com/us/en/c/women/dresses-and-jumpsuits/e6bb8705`. It returns `sizes: ["4","6","8"]` as plain strings, so treat every size as in stock.
- Other live women's category URLs follow the same pattern: tops `227371cd`, jeans `164d8c42`, coats `d1b967bc`, t-shirts `8e23bdfb`, sweaters `f9a8c868`, new-now `56b5c5ed`.
- `abotapi/mango-com-scraper` has real per-size stock, but it **needs a paid plan** (residential proxy).

**H&M (`gauzy_penguin`) deep check, confirmed:**
- **Stock is real.** `stock` is just a flag (2 = in stock, 0 = sold out). It agrees with `mrdoe` on the same product. Fast: 50 items in about 3s, with no proxy needed.
- **Kids and baby items mixed in.** For "dress", 32 of 50 results were kids. Filter `category` to `ladies_*` / `men_*`, and request about 2x the items you need.
- **The same style in other colours comes back as separate items.** Ids share their first 7 digits.
- **Images are 2333x3500 and 1–3.5 MB.** Add `?imwidth=657` to resize.
- **@Adam: adult items have no clean garment-only photo.** `model_image` shows a person wearing the item, so try-on needs background removal or a model that accepts a photo of a worn garment.

**Dead ends:**
- Zara: `shahidirfan` and `karamelo` returned no sizes. `abotapi` needs proxy access, which our free plan doesn't include.
- ASOS: `shahidirfan` returned `"Available online"` in place of sizes.

## Risks

- **No retailer returns sizes yet.** If pass 2 fails, we cut down to whichever stores work.
- **Zara and H&M block scrapers.** Their product pages may need residential proxies.
- **Rule #1: no code before the Friday opening.** Until then this file is design only.

## Changelog

- **Oct 23 (evening):** Uniqlo works through `abotapi/uniqlo-com-scraper` with real stock. Mango works through the multi-scraper with a live URL (sizes, no stock flags). H&M stock data confirmed real.
- **Oct 23 (later):** Found actors that return sizes for H&M (`gauzy_penguin`), Zara (`parseforge`, capped at 10 items on the free plan) and ASOS (`nifty.codes`, UK store only).

- **Oct 23:** Proposed the schema and pipeline. Ran the Apify size test: no retailer returns sizes, and Uniqlo and Mango returned nothing.
