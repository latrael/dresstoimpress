# Ryan: frontend status and integration notes

Last reviewed: October 23, 2026 (Pacific).
Working branch: `RyanFrontendking` (use this exact name).

## Scope and stack

Ryan owns the FlutterFlow iPhone app, Notability wireframes, optional Figma design,
demo recording, and pitch slides. Keep the implementation within the tools named
in the Notion playbook. The initial prototype uses mock data inside FlutterFlow;
Firebase and the shared FastAPI service are later integration points.
FlutterFlow generated project `Niche` (`niche-4k1al0`) with Home, Discover, Social,
and Cart. The first draft is visible in the editor; gestures have not been
verified. Ryan requested a closer match to the wireframe. See
`frontend/QUICK_BROWSE.md` and `frontend/quick-browse.mock.json` for the pending
revision and its sample data. UI edits are blocked by unreliable desktop input
and browser automation timeouts; do not report this revision as implemented.

## Coordination before implementation and integration

Refresh remote references and read the latest Markdown on `origin/staging`,
`origin/adam/ai-pipeline`, and `origin/nabil` before changes that affect integration.
Read `backend/app/models.py` on staging to verify the actual shared types.
Record conflicts here rather than silently choosing a new backend contract.
Do not edit Adam's AI layer or Nabil's commerce layer as part of frontend work.
Shared docs specify PRs into `staging`, followed by end-to-end integration before
`staging` goes to `main`. Do not merge other branches just to inspect their files.

Reviewed snapshots:

- `origin/staging`: `2bada98`; shared schema, models and schema changes.
- `origin/adam/ai-pipeline`: `2bada98`; `ADAM.md`, `docs/schema.md`,
  `docs/progress.md`, and previously reviewed backend instructions.
- `origin/nabil`: `27f8fdf`; updated `NABIL.md`, ingest normalization and fixtures.

## Product contract for frontend mocks

Use staging's `Product` names: `id`, `retailer`, `name`, `brand`, `category`,
`price_usd`, `sale_price_usd`, `currency`, `colors`, `sizes`, `in_stock`,
`image_url`, `product_url`, `style_tags`, `pattern`, `formality`, `label`,
`scraped_at`, and `source`. Follow model defaults for optional fields.

- Sizes are objects with `name` and `in_stock`. Grey out unavailable sizes and
  require an available size before adding to cart.
- Categories are singular: `top`, `bottom`, `outerwear`, `shoes`, `dress`, `accessory`.
- Retailers: `zara`, `hm`, `asos`, `uniqlo`, `mango`. Do not promise live inventory
  for all five: Nabil reports ingest/size availability risks.
- Keep stable product IDs when saving or adding items to cart.
- Pairing results are separate from Product: `product_id`, `id`, `score`, `reason`,
  `pairs_with`. Associate them by product ID.
- Cart adds use `{product_id, size, qty}`. Confirmation groups purchases by
  retailer. Nabil reports commerce implemented; this chat has not tested it live.

Nabil's updated notes explicitly retire his earlier draft. Both lanes now agree
on staging's schema. Nabil reports 370 H&M/Uniqlo products loaded; no shoes or
accessories yet. His newer notes supersede the older commerce status in
`docs/progress.md`. Verify actual feed responses before wiring the app.

## First prototype: Quick Browse

Build a small mock catalog that users can browse without API credentials:

- Horizontal movement inside a product image carousel changes images.
- Vertical movement between product cards changes products.
- Double-tap saves a product; an explicit button adds the selected size to cart.
- Display image, price, retailer, product description, sizes, and a mock pairing
  reason. Position dots track the photo index. Restrict horizontal swipes to the
  bounded photo area; description and controls are outside the carousel.
- Handle empty results, missing images, unavailable sizes, and the last product.

The wireframe's gestures differ from the earlier playbook's right/cart,
down/wishlist, left/discard mapping. The frontend proposal follows the wireframe;
backend actions now documented as `like`, `save`, `discard`. Any `/swipe` call
removes that product from the feed: never call it for photo or passive product
browsing. Keep explicit save/cart actions separate from gesture navigation.

The shared Product currently has one `image_url`, not a gallery, description or
model details. Extra mock gallery images/descriptions stay in frontend fixture data;
do not add them to the shared API contract without team agreement. Personal try-on
is a separate `POST /tryon` result (`image_url`, `cached`, `mode`). Respect
`mode: collage` as an outfit board, not a personal try-on. Show mock try-on as a
demo placeholder, never as a real generated result.

## Integration dependencies

- Nabil: confirm feed shape, paging/search, saved-item/swipe action values, cart
  responses, and Fit Check routes once implemented.
- Adam: pairing and try-on shapes are documented in `backend/README.md`.
  `MOCK_AI=1` is a backend setting, distinct from local FlutterFlow fixtures.
- A phone-accessible backend URL is needed; laptop localhost is not sufficient.
- All external service calls go through FastAPI; no service keys in the app.
- Adam's latest `ADAM.md` reports AI try-on working after billing cleared, with
  an outfit-board fallback. This supersedes his older progress document's blocker.
  Keep browsing usable without try-on.

## Handoff to Nabil

Ryan requested `ryan-nabil.md` directly on Nabil's branch. Published through the
GitHub connector in commit `1870a1818ce0d547f514cdde52feb55c3b4d95fa` on `nabil`.
It requests additive descriptions/gallery metadata and independent, idempotent
wishlist operations; these are requests, not claims of implemented backend APIs.
No agent was messaged. Continue checking the branch docs for implementation updates.
