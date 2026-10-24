# RYAN_TO_NABIL.md

Updated October 23, 2026 (Pacific). Handoffs on staging; implementation on `RyanFrontendking`.

## Ownership and latest review

Ryan owns all app screens and all design. Adam is AI/backend hosting + core; Nabil is commerce backend. The old split-screen assignment is withdrawn. Read all distinct Markdown versions across staging, Adam, Nabil, flutter-starter and Ryan. Latest Nabil reread at e2ea844 includes the data-only reference and /fit approval request.

## App progress

Merged staging and shared Flutter starter into Ryan's branch, retaining his accepted Quick Browse layout and using both original PDF pages as references. Home grid, persistent search over loaded suggestions, live Feed + wishlist adapter, cart add/remove/grouped totals, explicit sandbox checkout UI, receipts/status handling and order history implemented. Initial Social feed/shop entry wired, with full Social still pending. No backend/core files edited.

Eight Flutter tests pass and analyze is clean. Tests cover original gestures plus shared API integration/no browsing /swipe, checkout 409/cart retention, partial account read failure and image proxy URL preservation. Desktop mouse dragging also verified in the actual browser. Switching products resets photo/size, including returning to a prior product.

## Live checks passed

Ryan supplied the private connection details directly; entered in device-local settings only. No values in source, Git or this handoff.

- Health 200/ok, authenticated feed limit=5 returned five cards with gallery/size arrays, image proxy returned JPEG.
- Actual app loads live photos, descriptions/fallbacks, product sizes and pairing reasons.
- Saved a real feed product, selected size M, added it, saw the correct H&M group and total in cart, removed it, then unsaved it. Original cart/wishlist membership restored. Saving and browsing did not dismiss the product.
- **No live checkout submitted.** The checkout UI is implemented and the stock-change 409 path is tested with controlled API responses. Phone checkout remains a team checkpoint.

The original five gallery/description/wishlist requests remain acknowledged as complete. No schema change requested.

## Outstanding commerce/core coordination

Your newer product search/paging and users/onboarding routes are not yet methods in the published shared Dart core. Asked Adam to add them; current search filters loaded suggestions and does not claim full-catalog or natural-language matching.

Api.imageUrl in starter 1b4aff2 resolves /static but does not proxy retailer images. Current app wraps the documented /img route; asked Adam for the intended core helper. No new transport was introduced.

Checkout receipts distinguish paid / nessie_failed / pending_nessie. There is no documented per-purchase retry endpoint, so the app doesn't silently repeat a successful store payment when another failed. Please document a safe retry contract if that is needed.

## /fit decision status

Your public guest page proposal was read. **Ryan has not explicitly approved enabling it.** Keep it off until his visual review/decision; this handoff does not give that approval. Continue backend work independently.

## Remaining Ryan work

Size assistance, personal try-on slide (collage labeled Outfit board), complete-look/Fit Score, full product details, onboarding, full Fit Check/Closet/Profile, and iPhone/live-checkout verification. User explicitly allows Xcode to come later on his machine.

Implementation PRs go to staging only. Private connection details and service credentials must never enter public docs or Git.
