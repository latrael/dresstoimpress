# Quick Browse: Ryan's accepted design

Status: implemented in plain Flutter under `app/lib/features/feed/`. Ryan approved
its mock-up and requested continuing with the original two-page WireframeSketch.pdf.
Earlier FlutterFlow-specific implementation notes are superseded.

## Layout and gestures

1. Compact header with cart access; persistent Home / Discover / Social navigation.
2. A bounded picture area roughly in the upper half of the screen. Horizontal
   PageView includes pictures only, with contain fit, no autoplay and no wrapping.
3. Price overlay at the picture's lower right. Show the sale price when lower,
   striking through the original price. Exactly one currency symbol.
4. Position dots immediately below the picture; no dots for a single image.
5. Retailer and product name, readable description or honest retailer fallback,
   and pairing reason only when supplied. Do not invent fabric or model stats.
6. Product-provided sizes, unavailable choices disabled, then Add to Cart.
7. Description, sizes, cart button, search and navigation stay outside the photo
   carousel. Horizontal drags there do not change photos.
8. Scroll product details to the bottom first. A fresh upward gesture past that
   boundary reveals an up-arrow/progress cue before the next product. A deliberate
   touch drag confirms on release; trackpad/wheel confirms after the burst settles.
   Small edge movements and momentum from reading details do not change products.
   One gesture advances at most one item. Reset new-product state.
9. Double-tap a photo saves; explicit heart remains. Save uses independent wishlist
   PUT/DELETE. Photo changes and passive product browsing NEVER call `/swipe`.
10. Failed images stay bounded and leave controls usable.

Page 1 of the PDF also defines Home's suggested grid, persistent search and entry
into Quick Browse. Page 2 shows retailer model photos and personal try-on slides.
Personal try-on is an explicitly requested generated slide; never put personal generated images in the
shared catalog. A collage response is labeled Outfit board.

## Shared data and app integration

Use `app/lib/core/models.dart` and the shared API client. Product names remain
snake_case over the wire, with `images[{url,kind}]`, nullable `description` and
`sizes[{name,in_stock}]`. The app adapter bridges typed models to Quick Browse.
H&M descriptions are absent; Uniqlo usually has one image. No duplicated slides or
borrowed garments. Model kinds do not reliably identify garment-only H&M photos.

Live web images use backend `/img?url=`; relative static paths resolve against the
backend base. Secrets are entered in local connection settings, never source.
Demo mode uses a small committed catalog snapshot, with local-only cart/save.
The older JSON fixture remains an explicitly mock historical design asset.

## Verification

Thirty-eight Flutter tests cover original gestures/cart and the overnight feature flows.
Connected mode uses paged catalog search; explicit demo mode stays local. Run `cd app && flutter analyze && flutter test`. Backend health/feed
and image proxy were also verified with private runtime settings. The app loads
live photos. Phone and live checkout verification remain separate checks.

## Overnight product tools

Find my size opens measurements and the backend's fit choices. It returns a
recommendation with confidence/reason; only an available size can be selected.
Try it on appends a generated photo inside the existing image section. A returned
collage is labeled Outfit board, not a photo of the user. Complete the look opens
owned/catalog suggestions and Fit Score. These controls stay outside horizontal
photo swipes; product details scroll to expose controls on smaller screens.
No model measurements, real descriptions or personal photos are invented.

38 tests pass and Flutter analysis is clean. The overnight release web build succeeded. Overnight backend checks used
mock AI and synthetic local fixtures. Shared live / phone / personal-photo quality
acceptance remains pending; see RYAN.md and the staging morning report.
