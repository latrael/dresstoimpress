# Quick Browse: wireframe revision

Status: implementation specification and sample fixtures prepared. Not yet applied
or tested in FlutterFlow. Project `Niche` (`niche-4k1al0`) exists in FlutterFlow.

## User-approved layout

Follow `WireframeSketch.pdf` and Ryan's October 23 clarification. Preserve the
existing size choices and Add to Cart button. Edit Discover/Quick Browse only.

1. Compact header above the product, with cart access.
2. A bounded picture area with a horizontal PageView. The carousel wraps only
   image slides, not the product description, controls, or entire screen.
3. Price overlay at the lower right of the picture area, formatted with one `$`.
4. Centered position dots directly beneath the picture area. One dot per actual
   image; current dot is filled/darker. Update on every page change in either
   direction. No autoplay or infinite wrapping.
5. Retailer and product name, followed by a readable product description.
6. Fit/model information only if supplied. Do not invent measurements or fabric.
7. Size picker, with unavailable options disabled, then Add to Cart.
8. Existing bottom navigation remains outside the image carousel.

The image block should occupy roughly the upper half of an iPhone screen, rather
than acting as a full-screen hero. Keep the whole garment visible (contain fit).
Allow details to scroll vertically on smaller displays.

## Gesture boundaries

- Horizontal drag starting inside the picture area changes only its photo.
- Horizontal drag on description, sizes, cart button, header, or bottom navigation
  must not change the photo or navigate to another product/tab.
- Vertical browsing moves between products and must not change image index.
- Double-tap on a photo saves; preserve the explicit save button too.
- Reset the photo index to zero when switching to a different product. Size
  selection must belong to its product and cannot leak into another item.
- Display exactly one image, with no dots, if only one exists. Do not duplicate
  an image or borrow another garment's picture to simulate a gallery.
- Failed image loads get a bounded placeholder, with details/cart still usable.

## FlutterFlow implementation

Create a product card component whose image section is a fixed-height Container
containing a horizontal PageView and its indicator. Bind slides to that product's
gallery list. Keep the description, size picker, and cart button as siblings below
this Container. Use separate state for the selected product, photo index, and
selected size. Never wrap the entire card in a horizontal PageView.

Use `quick-browse.mock.json` for initial content: three H&M snapshot products,
each with separate garment/model image URLs from Nabil's fixtures. Image URLs
have not been checked for reachability. Description text, pairing suggestions,
and one unavailable size per product are explicitly mock. Import/bind this data
inside FlutterFlow; no new backend, service, or app framework is introduced.

`product` follows staging's Product schema. `presentation` and `pairing` are
frontend fixture metadata, not additions to the shared Product. No model stats or
personal AI try-on are supplied by these fixtures.

## Current backend constraints

Reviewed `origin/staging` and `origin/adam/ai-pipeline` at `2bada98`, plus
`origin/nabil` at `27f8fdf`. Read `docs/schema.md`, `ADAM.md`, `docs/progress.md`,
and `NABIL.md`. Older progress prose has stale commerce status; Nabil's newer
notes report the commerce router and a 370-product H&M/Uniqlo load.

- Both lanes now agree on the canonical schema. Use `price_usd`, `product_url`,
  and `sizes[{name,in_stock}]`.
- Product has no description or gallery fields yet. Use local presentation data
  for now; show an honest empty state when real products lack these fields.
- Nabil's `/feed` returns Product plus `reason`, `score`, `pairs_with`.
- `POST /swipe` accepts `like`, `save`, `discard`; **any call removes that product
  from the feed**. Photo browsing and passive vertical browsing must NOT call it.
- Adding to cart uses `/cart/{user_id}/items` with `{product_id,size,qty}` and can
  return 422 for unavailable sizes. Keep the selection visible on failure.
- The current try-on response adds `mode: ai|collage`. A collage is an outfit
  board, not a generated photo of the user wearing the item.
- Latest `ADAM.md` reports real AI try-on working after billing cleared; the older
  progress document's billing blocker is stale. Verify the actual service before
  showing personal results in the app.

Backend requests are published as `ryan-nabil.md` on Nabil's branch (commit
`1870a1818ce0d547f514cdde52feb55c3b4d95fa`). Gallery and description fields in that
handoff are proposed additions, not available API fields until Nabil confirms.

## Manual acceptance checks in FlutterFlow preview

1. Swipe picture one to picture two and back; correct active dot follows.
2. Try horizontal drags on the description, size row, and empty margin; picture
   remains unchanged.
3. Move to another product; its own photos, description and sizes appear.
4. Try unavailable size; selection/cart add is blocked. Select an available size
   and add; cart contains the correct product and size.
5. Confirm product name matches both photos, text has usable contrast, and price
   has a single currency symbol.
6. Confirm no backend swipe event is sent merely by browsing photos/products.

These checks are pending; the spec and valid JSON do not prove the UI works.
