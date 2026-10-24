# Ryan → Adam: plain Flutter Feed

Ryan approved plain Flutter and requested keeping implementation on `RyanFrontendking`. Read your newer `ADAM_TO_RYAN.md` and `docs/app-plan.md` on `adam/ai-pipeline` at b413f61; staging handoffs also reviewed. Our handoffs live on staging.

Standalone Flutter 3.47.6 / Dart 3.13.5 installed; Xcode deferred. Feed code is in `app/lib/features/feed/quick_browse.dart` on Ryan's branch, with adapter instructions in its README and four widget tests in `app/test/features/feed/`. No core/API client, app shell or package changes.

Your announced `flutter-starter` branch was absent from remote heads during setup. To avoid a competing app, tested the Feed in an isolated temporary Flutter web shell outside the repo. Analysis passed and all four gesture/cart tests passed. Browser verified selecting S and mock Add to Cart. Retailer images fail directly in web, so integration must supply core's `/img?url=` helper.

Widget accepts canonical Product maps, saved IDs, async save/cart callbacks and imageUrl callback. Please preserve this Feed file when adding your starter (or provide your starter Feed entry point so Ryan can connect the widget). Save adapter uses wishlist PUT/DELETE, cart adapter uses POST with qty 1. No `/swipe` browsing events. Shared shell owns loading/retry/navigation; no private URL/key committed.

Implemented: horizontal image-only gallery/dots, vertical product browse with detail scrolling, product sizes/disabled availability, descriptions/fallback, optional reason, sale prices, save/double-tap and cart pending/error states. Pending: shared-model/API adapter, size advice, product detail, try-on, complete-look/Fit Score, onboarding and phone/live-backend checks. Full progress is in staging RYAN_TO_NABIL.md. No live checkout performed.
