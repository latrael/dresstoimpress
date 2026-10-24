# Ryan: Flutter app status

Reviewed October 23, 2026 (Pacific). Branch: `RyanFrontendking`.

## Current ownership and references

Ryan explicitly approved plain Flutter and owns every app screen and all design.
Adam maintains AI/backend hosting and the shared `app/lib/core`; Nabil maintains
commerce. Earlier FlutterFlow and split-screen assignments are superseded.

Design references: `WireframeSketch.pdf` (both pages), Ryan's accepted Quick Browse
mock-up, and `frontend/QUICK_BROWSE.md`. Preserve the ivory/burgundy layout, bounded
photo carousel, dots, price overlay, details, sizes and Add to Cart. Home has a
suggested grid and persistent search; Home / Discover / Social navigation stays
outside the product carousel. Do not invent retailer descriptions or model stats.

## Team review and branch integration

Read all distinct Markdown file versions on staging, adam/ai-pipeline, nabil,
flutter-starter and Ryan's branch. Full review includes progress, app plan, schema,
backend README, both backend lanes' status and directional handoffs, old requests,
and local frontend specifications. Newer staging/Adam ownership notes supersede
old SwiftUI / FlutterFlow / optional-reference-only plans.

Reviewed staging 5c320be, Adam e27baa9, Nabil e2ea844 and starter 1b4aff2.
Merged staging and flutter-starter into RyanFrontendking. The only conflict was
an older NABIL_TO_RYAN.md added on Ryan's branch; kept staging's newer handoff.
No backend or core implementation was edited.

## Implemented

The real project now runs from `app/`, rather than a temporary preview:
- Home suggested grid opens the selected product in Quick Browse.
- Persistent search filters the currently loaded suggestions; it is not full
  catalog search or natural-language onboarding yet.
- Photo-only horizontal paging and active dots; vertical product paging and
  detail scrolling; mouse, touch and trackpad input supported.
- Retailer/name/description fallback, optional pairing reason, correct sale price,
  actual size labels and stock. Save/double-tap uses wishlist PUT; unsave DELETE.
- Shared core Feed/wishlist/cart adapters and image proxy routing. Browsing never
  calls `/swipe`. Failed account reads preserve the visible feed and block writes
  until retry, so unknown saved/cart state isn't silently overwritten.
- Cart grouped by retailer, removal, subtotals, total, explicit sandbox checkout,
  receipts, payment-status distinctions and order history. Stock-change 409 errors
  retain the cart and identify unavailable items.
- Device-local connection settings. Explicit demo mode uses 12 catalog snapshot
  products with local cart/wishlist and a receipt labeled as no payment processed.
- Initial Social feed and Shop this fit entry use the shared routes; posting,
  comments and full social interactions remain pending.

## Verification

Flutter 3.47.6 / Dart 3.13.5. `flutter analyze` clean and eight tests pass, including
original gesture checks plus shared API/cart flow, checkout 409, partial account
failure and image-proxy URL preservation.

Private backend details entered only into device-local connection settings, never
Git or handoffs. Live checks: unauthenticated health 200/ok, authenticated feed with
limit 5 returned five products with galleries/sizes, image proxy 200 image/jpeg.
The actual browser app connects, loads the live feed and shows retailer photos.
Mouse-driven gallery paging and the description gesture boundary were verified in the live browser. Live wishlist save also succeeded. Live size-M cart add and removal also succeeded, and the test wishlist membership was restored. Vertical paging reached a single-photo Uniqlo item with its real description and disabled unavailable sizes. No live checkout has been executed.

## Core gaps to Adam

The published starter at 1b4aff2 differs from its README: imageUrl only resolves
relative paths and doesn't proxy retailer images. The app currently wraps the
already documented `/img?url=` route in StoreController; please provide the core
helper later. Core also lacks Nabil's newer users/onboarding/search routes and
Style DNA apply. pubspec currently has http/shared_preferences, without image_picker.
No speculative backend changes or second API transport were introduced.

## Next work

- Finish remaining feature flows after the verified Feed/cart checkpoint.
- Size-advice input, personal try-on slide (collage labeled Outfit board), complete
  the look/Fit Score, product details.
- Onboarding, full search/paging after core catches up with Nabil's new routes.
- Fit Check creation/likes/comments, Closet and Profile/Style DNA.
- iPhone verification on Adam's Mac; Xcode can wait on Ryan's machine.

Read and write all handoffs on staging. Publish implementation on RyanFrontendking;
PRs target staging, never main. No service credentials or private tunnel details
belong in code, screenshots, docs or Git.
