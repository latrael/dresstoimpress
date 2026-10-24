# Ryan -> Nabil: Quick Browse backend handoff

Requested by Ryan on October 23, 2026. This document is a frontend request, not a
claim that the additions below are already in the API.

Reviewed Nabil's branch at `27f8fdf`, including `NABIL.md`, the commerce router,
ingest normalization and raw fixtures. Shared AI/schema branch was `2bada98`.
Refresh these before implementing; preserve newer work if they have advanced.

## What Ryan is building

The app is in FlutterFlow, project **Niche** (`niche-4k1al0`), with local mock data
first. Ryan's Git branch is **`RyanFrontendking`**, not `ryan`.

Ryan wants Quick Browse to follow his wireframe:

- A bounded product-picture area, with an Instagram-style horizontal carousel.
- One position dot per picture; active dot follows the current picture.
- Horizontal swiping is restricted to that picture area. It does not move the
  description, size picker, Add to Cart button, or bottom navigation.
- Below the pictures: product name, retailer, readable description, size options,
  and Add to Cart. Keep real stock rules and require a size.
- Double-tap on the picture saves the item. The explicit save control remains.
- Vertical browsing moves between products; it is not a discard/cart gesture.

Ryan owns these FlutterFlow interactions. Nabil does not need to build the UI.

## P0: expose a real product gallery without losing the current Product shape

The shared Product only exposes `image_url`. Nabil's H&M raw fixture already has
`images[]` plus `model_image`, but the frontend cannot use that full gallery yet.

Please implement an additive, documented field on Product:

```json
{
  "image_url": "https://retailer.example/garment.jpg",
  "images": [
    {"url": "https://retailer.example/garment.jpg", "kind": "product"},
    {"url": "https://retailer.example/model.jpg", "kind": "retailer_model"}
  ]
}
```

- Coordinate the shared model change with Adam and document it in
  `docs/schema.md`; merge through `staging`. Keep all existing field names.
- Make `images` optional/default empty so existing products/AI/seed data keep
  working. Keep `image_url` as the backward-compatible primary image.
- Retain distinct images from the same product **and same color variant** in
  ingest. Include the retailer model image when available; de-duplicate URLs
  while preserving useful order. Never borrow another product/color's photo.
- When a product only has `image_url`, return a single-image gallery or document
  that the app must construct one. No duplicate slides to fill a carousel.
- Keep retailer model photos distinguishable from product-only photos. Missing
  model photos are fine. Do not infer model measurements from an image.
- Expose the gallery consistently in `/feed`, `/products/{id}`, and nested cart
  Product objects. Re-normalize saved raw data where possible; no paid re-scrape
  is required just to test the change.
- Do not include personal try-on results in the global product catalog.
  `/tryon` is user-specific and returns `{image_url,cached,mode}`. The frontend
  appends it locally and labels `mode:collage` as an outfit board.

If a richer gallery already exists in newer work, use/document that shape instead
of introducing a second one; add the final JSON example to this document.

## P0: product descriptions

Please expose an additive `description: string | null = null` on Product, following
the same shared-model review process. Use actual retailer text when available;
leave it null when absent. The app can show an honest unavailable state.

- Preserve source descriptions from raw ingest if supplied. Avoid invented fabric,
  fit, care instructions, body measurements, or size advice.
- Normalize description content to readable plain text; do not require FlutterFlow
  to render arbitrary retailer HTML.
- Return the description through feed, detail, and nested cart Product objects.
- A pairing `reason` is not a product description. Keep these fields separate.
- Mock descriptions in Ryan's fixtures are explicitly sample copy; do not load
  them as authentic retailer descriptions.

## P1: saving must be independent of photo swipes and feed removal

Current `/swipe` writes a swipe record, and `/feed` excludes every swiped product.
That makes it unsuitable for a photo-carousel event. The frontend will NEVER call
`/swipe` for a photo change or passive vertical browsing.

Please add explicit idempotent wishlist operations (or document equivalent newer
routes), preserving existing `/swipe` clients:

| Method | Suggested path | Behavior |
| --- | --- | --- |
| PUT | `/wishlist/{user_id}/items/{product_id}` | Ensure saved; repeat safely |
| DELETE | `/wishlist/{user_id}/items/{product_id}` | Ensure unsaved; repeat safely |
| GET | `/wishlist/{user_id}` | Existing saved products, with gallery/description |

Store wishlist membership independently of feed-dismissal records. Saving should
not dismiss the item currently on screen or remove it from later feed loads.
Keep legacy `/swipe action=save` behavior backward compatible or explicitly
document/migrate it; don't silently invalidate existing clients or saved items.
If wishlist saving informs Adam's style memory, record the save without a feed
dismissal record and avoid duplicate memory writes on repeated PUT calls.
Provide a way for the app to initialize saved state (GET wishlist IDs is enough).

## Existing behavior to preserve

- Product names stay `price_usd`, `sale_price_usd`, `product_url`, `colors[]`,
  singular `category`, `sizes[{name,in_stock}]`, stable IDs and retailer enums.
- Cart add remains `{product_id,size,qty}` with unavailable-size validation (422).
- Cart and checkout remain grouped by retailer. If stock changes, return a clear
  failure that lets the frontend keep the chosen item/size and show the message.
- Prices: use `sale_price_usd` when present; if showing a discount, strike through
  the original `price_usd`, not the sale price. NABIL.md's current wording appears
  reversed; please clarify it in the doc.
- Current realistic demo retailers are H&M and Uniqlo. Do not block the carousel
  on adding Zara, ASOS, shoes, or accessories.
- External service keys stay on FastAPI; none in FlutterFlow or Git.

## Verification and handoff back to Ryan

Add meaningful backend checks for the changes:

1. Existing Product payloads still validate without `images` or `description`.
2. Ingest keeps the correct distinct garment/model images for a product/color.
3. Feed/detail/cart return the agreed gallery and description fields.
4. Saving twice creates one membership; unsaving twice is safe; wishlist updates
   are visible via GET and do not remove the product from the feed.
5. Existing cart stock validation and legacy swipe behavior still pass.

Update `NABIL.md` and this document with:

- Implemented response examples (one multi-photo product and one single-photo
  fallback), exact wishlist routes, and error bodies.
- A phone-accessible FastAPI base URL when available, plus the correct demo user
  ID. `localhost` on a laptop will not work on Ryan's phone.
- Whether changes are on `nabil`, merged to `staging`, and ready to integrate.
- Remaining limitations, especially products missing descriptions/gallery data.

Ryan will keep the app on local fixtures until these shapes are available. His
frontend implementation notes and mock JSON live under `frontend/` on
`RyanFrontendking`. No request here requires modifying that branch or FlutterFlow.

---

## Implemented (Nabil, Oct 23 ~10:45 PM): on `nabil`, PR into `staging`

All P0 and P1 items are done. Full shapes, examples and error bodies are in [`NABIL_TO_RYAN.md`](NABIL_TO_RYAN.md).
- **Gallery:** `images[{url, kind}]` is filled in for all 418 products; `images[0]` is the same as `image_url`. H&M has 2–6 `retailer_model` photos each; Uniqlo has 1 `product` photo each. Every photo is the same product and colour, with no duplicates.
- **Description:** plain text. Uniqlo 117 of 128 have one; H&M is always `null`, because the scraper returns no text.
- **Wishlist:** `PUT/DELETE /wishlist/{user_id}/items/{product_id}` (repeat-safe, and doesn't remove the item from the feed), `GET /wishlist/{user_id}`, and `GET /wishlist/{user_id}/ids`. Legacy `/swipe action=save` still works.
- **Price wording:** corrected in NABIL.md. Show `sale_price_usd` and strike through `price_usd`.
- **Stock changes:** cart add gives a specific 422 message, and checkout gives 409 with the `unavailable` list, charging nothing.
- **Base URL:** Adam's tunnel, shared privately along with the `X-DTI-Key` header. Demo user `u_demo`.
