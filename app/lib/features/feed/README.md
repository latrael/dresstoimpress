> Sprint 2: Home uses thin spaced separators, photo dots/preloading and heart feedback.
> US wheel inputs and Fits for you are documented in docs/ryan-sprint-2-implementation.md.
> Current validation: 102 tests pass, Flutter analysis clean. Older checkpoints below
> describe earlier versions. Shared core/backend remain Adam/Nabil’s lanes.

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
A 48-pixel solid muted burgundy band with 12-pixel spacing on each side separates items.
The list prepares about one viewport ahead and behind and disposes distant items.
Nearby items retain their own photo/size state. Horizontal swiping stays scoped
to each bounded photo gallery; cart/size tools remain with the matching product.

Flutter analysis clean; 81 app tests pass, including continuous touch/wheel,
long descriptions, lazy item creation/disposal, separators, carousel boundaries,
cart selection and separate generated try-on slides. Actual browser preview
verified the separator and continuous product transition. Phone feel awaits Ryan.

## Onboarded sizing

The app supplies automaticSizing and the shared StoreController size resolver.
Nearby products request sizing once per saved profile revision, using explicit
height/weight, preferred fit, optional waist converted cm → inches, and US shoes.
No connection defaults are treated as entered body measurements. A usual letter
size may match an in-stock choice exactly; demo mode uses this explicit fallback.
One Add to Cart button replaces the size picker. Missing measurements open the
preferences editor; unavailable recommendations do not silently choose a size.
Manual callback mode remains available for isolated widget adapters/tests.
See frontend/ONBOARDING.md for persistence and backend handoff limits.

## Council shell

The shared product view is Home, with a persistent header and floating
Home/Discover/Inspo navigation. Discovery, Liked and Inspo catalog tags seed the
same Home feed through the shared seeded API. Known feed size fields are
respected; unknown sizes do not acquire an invented badge. See the implementation
checklist in docs/ryan-council-implementation.md for all current flows and limits.
