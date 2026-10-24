# Ryan's Flutter Feed

The Feed is now integrated into the shared app. Run from `app/`:

```sh
flutter pub get
flutter run -d web-server --web-hostname 127.0.0.1 --web-port 5218
```

Open the printed local URL in a browser. Device settings accept the private backend
connection. Demo mode works without it. Do not commit private URLs or keys.

`quick_browse.dart` remains presentation-only: canonical Product maps, saved IDs,
async wishlist/cart callbacks and an image URL resolver. StoreController in
`features/store/` adapts the shared core models and methods. No `/swipe` browsing
events. See `frontend/QUICK_BROWSE.md` at the repository root for the accepted PDF
layout/gesture requirements.

Tests live under `app/test/features/`; `flutter analyze` and all eight tests pass.
Both touch gesture tests and a shared-API Home -> Feed -> wishlist/cart flow are
covered. The actual app loads live catalog photos through the documented image
proxy route. Personal try-on, sizing assistance and full product detail remain
pending. Core and backend ownership stay with Adam/Nabil.
