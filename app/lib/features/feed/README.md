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

## Overnight additions

Optional size-advice, try-on and complete-look callbacks are supplied by the shell.
A try-on result adds a product-local gallery slide and an honest mode label; it
never changes the catalog. Measurements, size selection and other actions stay
outside the bounded image area. Demo omits service-dependent controls.
Full app validation: 31 tests, analyze clean and release web build. Shared live
and phone acceptance remain pending (RYAN.md).

## Continuous browsing

Ryan replaced boundary-gated swiping with a single lazy vertical product list.
Product details and subsequent products share the same scroll; there are no nested
vertical scrollers, page snaps, arrows, thresholds, or release confirmations.
A 48-pixel faded burgundy band with 12-pixel spacing on each side separates items.
The list prepares about one viewport ahead and behind and disposes distant items.
Nearby items retain their own photo/size state. Horizontal swiping stays scoped
to each bounded photo gallery; cart/size tools remain with the matching product.

Flutter analysis clean; 36 app tests pass, including continuous touch/wheel,
long descriptions, lazy item creation/disposal, separators, carousel boundaries,
cart selection and separate generated try-on slides. Actual browser preview
verified the separator and continuous product transition. Phone feel awaits Ryan.
