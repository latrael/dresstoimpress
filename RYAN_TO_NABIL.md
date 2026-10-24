# RYAN_TO_NABIL.md

Ryan's frontend handoff. Read and reply through **staging**. Implementation branch: `RyanFrontendking` (Ryan explicitly requested keeping this branch).

## Plain Flutter pivot — October 23, 2026

Ryan explicitly authorized moving from FlutterFlow to plain Flutter. Read staging `NABIL_TO_RYAN.md` (latest ~11:15 PM notes) and `ADAM_TO_RYAN.md`, plus the newer `ADAM_TO_RYAN.md` and `docs/app-plan.md` on `adam/ai-pipeline` at b413f61. Nabil's branch handoff matches staging. Adam's newer plan assigns Ryan Feed, Nabil Cart/Fit Check, Adam core/Closet/Profile/shared AI.

Flutter 3.47.6 and Dart 3.13.5 installed on Ryan's Mac as a standalone SDK. Xcode/Android setup deferred. Browser preview works without Xcode.

## Implemented in Ryan's lane

`app/lib/features/feed/quick_browse.dart`: bounded horizontal photo PageView and position dots, vertical product browsing, product description/fallback, optional pairing reason, sale price, product-defined sizes, unavailable-size blocking, Add to Cart, explicit heart and photo double-tap save. No `/swipe` calls. Keeps selection when cart errors occur. API and image URL callbacks injected; no duplicate core client or app shell.

Four Flutter widget tests pass (gesture boundaries/dots; size/cart validation; vertical browse/new-product state/single-image dots; double-tap save/cart error retention). `flutter analyze` is clean in an isolated preview project. Browser confirmed size S -> Add to Cart -> Cart (1). This is mock behavior, not a live integration result.

## Acknowledged — original five backend requests satisfied

Nabil confirms gallery ingest, descriptions/nulls, consistent Product fields across feed/detail/wishlist/cart, idempotent wishlist and route documentation. No further schema changes requested.

- H&M has 2–6 images, all retailer_model; description null. Do not infer garment/model ordering from that flag.
- Uniqlo has 1 image; hide dots. Show actual description when present.
- Price prefers sale_price_usd with price_usd struck through.
- Save uses wishlist PUT/DELETE and must not remove feed items.
- Cart POST remains `{product_id,size,qty:1}`; preserve selection on 422.
- Checkout 409 detail is an object and preserves the cart. Nabil owns that UI.

## Integration still pending

Adam's announced `flutter-starter` branch / app shell was not in remote heads at the time of this check. Our files are limited to the Feed feature and its tests; a disposable preview shell lives outside Git. Integrate these with core's models, wishlist/cart APIs and image helper when the starter is published. Direct retailer photos fail in browser, as Adam warned: production must use `/img?url=` through core.

Private backend URL and X-DTI-Key remain private and are not committed. No live requests or checkout verified on Ryan's machine. Need Settings -> health/feed connection once shared starter and private settings are available.

Remaining Ryan work: live Feed adapter, size advice, product detail, try-on (label collage as Outfit board), complete-the-look/Fit Score, onboarding, and phone verification. FlutterFlow pages are an earlier design draft, not the active implementation.

## Coordination

All new handoffs go to staging. Implementation PRs target staging, never main. No additional packages or core changes introduced. The original wireframe and `frontend/QUICK_BROWSE.md` remain the design reference; their FlutterFlow-specific status paragraphs are historical.
