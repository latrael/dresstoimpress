# Ryan → Adam: shared Flutter integration and live verification

Updated October 23, 2026 (Pacific). Implementation stays on `RyanFrontendking`; handoffs stay on staging.

## Current plan acknowledged

Ryan owns every app screen and all design. Adam maintains AI/hosting and core; Nabil commerce. Read all distinct Markdown versions across staging (5c320be), Adam (e27baa9), Nabil (now e2ea844), flutter-starter (1b4aff2) and Ryan. Rechecked both PDF pages and retained the Quick Browse mock-up Ryan approved.

## Implemented and verified

Merged staging + flutter-starter into RyanFrontendking. Only conflict was the old added NABIL_TO_RYAN.md; kept staging's newer version. No backend/core edits.

Actual `app/` now runs: Home suggested grid -> selected Quick Browse, persistent loaded-suggestion search, typed-model Feed adapter, wishlist PUT/DELETE, cart add/remove, retailer groups/totals, explicit Nessie-sandbox checkout UI, receipt status distinctions and order history. Initial Social feed + shop entry also wired. Demo mode remains separate/local and never claims a payment.

Ryan provided the private connection details directly; they are in device-local settings only, not this document, source or Git. Live health 200/ok; feed limit=5 returned 5 products; image proxy 200 JPEG. Actual browser loaded live catalog and photos. Verified photo swipe/dot updates, description drag staying outside the carousel, vertical paging to a single-photo product with real description and unavailable sizes, save/unsave, size-M add -> correct H&M cart -> removal. Test cart and wishlist membership restored. **No live checkout executed.**

`flutter analyze` clean; 8 tests pass. Original 4 plus shared-API Home/Feed/save/cart route check (no /swipe), checkout 409 retaining cart, partial account read failure blocking writes, proxy query encoding. Return-to-previous-product test now also verifies photo/size reset. Desktop mouse dragging explicitly enabled after browser check found Flutter's default ignored it.

## Concrete core requests

At published starter 1b4aff2, `Api.imageUrl` only resolves relative static paths; it does not proxy retailer images despite README claims. StoreController currently wraps the already documented `/img?url=` route without changing core. Please add a core proxy helper when convenient.

The published core lacks Nabil's newer product search/paging, onboarding/users methods and Style DNA apply. pubspec also lacks image_picker (currently only http/shared_preferences). Please bring core up to those contracts; the app currently filters loaded suggestions and does not pretend that is full-catalog/natural-language search.

## Remaining

Sizing assistance, personal try-on slide (collage = Outfit board), complete-look/Fit Score, full product detail, onboarding, complete Social, Closet/Profile and phone verification. iPhone still on your Mac. Public /fit guest page remains off pending Ryan's explicit review; no approval inferred.

Frontend status and accepted design spec updated in RYAN.md / frontend/QUICK_BROWSE.md. Implementation PR targets staging only.
