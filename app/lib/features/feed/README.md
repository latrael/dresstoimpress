# Ryan's Flutter Feed

Built against `docs/app-plan.md` on `origin/adam/ai-pipeline` at b413f61,
and staging handoffs at c31c147. Ryan explicitly requested plain Flutter.

`quick_browse.dart` contains the Feed presentation only. No API client, app shell,
credentials or additional packages are introduced. Adam's announced
`flutter-starter` branch was not published when this was written.

## Shell adapter

Instantiate `QuickBrowse` with canonical Product JSON maps from the shared model
adapter, `savedIds`, an async `onSave(id, saved)`, async
`onAddToCart(id, size)`, and `imageUrl(source)` using core's `/img?url=` helper.
Map save to idempotent wishlist PUT/DELETE and cart to POST with qty 1. Never
send `/swipe` for browsing. Rebuild with the updated saved IDs after a successful
save. Translate API errors to readable exceptions; the widget retains size
selection on failure. The shared shell owns loading/retry and navigation.

Photo paging is horizontal inside the bounded image region. Details scroll on
short screens; continuing vertically at the detail boundary pages products.
Single-image products hide dots. Prices prefer sale_price_usd and strike through
price_usd. Sizes come from each product. Null descriptions show the honest
retailer fallback required by Ryan; empty AI reasons are hidden.

## Validation

Flutter 3.47.6 / Dart 3.13.5. Because the shared app shell is pending, copied the
feature into an isolated standard Flutter web project at
`/private/tmp/niche-flutter-preview`, with the existing JSON fixtures adapted to
canonical gallery/description fields. No temporary app shell was committed.

- `flutter analyze`: no issues in the isolated preview.
- Four widget tests passed: photo gesture boundaries and paging; size/cart
  validation; vertical browsing with fresh product state and single-image dots;
  double-tap save and cart errors retaining selection.
- Browser preview confirmed size S -> Add to Cart -> Cart (1).
- Direct retailer images fail in web; live proxy integration remains pending.

Tests are in `app/test/features/feed/quick_browse_test.dart`. Run them from the
shared `app/` once its pubspec and shell land. Adapt the relative feature import
if the starter uses a different layout.

Pending: shared API/model adapter and live requests, size advice, product detail,
try-on, complete-the-look, onboarding, and phone verification. No live checkout
was performed.
