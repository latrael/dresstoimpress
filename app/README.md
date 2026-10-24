# app/: shared Flutter shell + core

**Ryan owns the app and its design.** This folder gives his features a project to live in and a tested connection to the backend. Everything visual in it is a placeholder for Ryan to replace.

## Current app status

Ryan's app includes Home/Quick Browse, save/cart/checkout/orders, size advice,
personal try-on gallery slides, complete-the-look/Fit Score, text onboarding,
paged catalog search, Fit Check actions, Closet and Profile/Style DNA.
The PDF and accepted Quick Browse remain the design reference. Full verification
and remaining live/phone checks are in `../RYAN.md`. Overnight PR #16 targets
staging for human review; it has not been merged.

For a browser already installed on the machine:

```sh
flutter pub get
flutter run -d web-server --web-hostname 127.0.0.1 --web-port 5218
```

Open the local URL. Demo is explicitly local; Connect switches to the private
backend through device settings. No credentials or private server URL are in Git.

## Shared starter contents (historical description)

- `pubspec.yaml`: package `dress_to_impress`, Flutter 3.47.x. Dependencies: `http`, `shared_preferences`, `image_picker`; dev: `flutter_test`, `flutter_lints`.
- `lib/main.dart`: a bare entry point with a URL + key screen and "Test connection". **Placeholder;** Ryan replaces it with his shell.
- `lib/core/api.dart` (Adam keeps it matching the backend): one async method per route.
  - Sends the `X-DTI-Key` header on everything except `/health`, `/static`, `/img`.
  - `ApiError` carries the `detail` text, plus the `unavailable` list on a checkout 409.
  - Multipart upload that sends the image's real Content-Type.
  - `imageProxyUrl(url)`: retailer images (H&M, Uniqlo, …) → `GET /img?url=` on our backend, which web builds need because those hosts refuse direct loads; `/static/...` → base URL; anything else unchanged. (`imageUrl(url)` only resolves `/static/...`; kept as-is.)
  - Search + paging (`searchProducts`), users (`createUser`, `getUser`, `updateUser`), `onboarding(text)` and Style DNA (`style`, `applyStyle`).
- `lib/core/models.dart`: `fromJson` for every response shape. It reads snake_case keys, and optional fields are nullable. Checked against the live backend: 13/13 routes decode.
- `lib/core/config.dart`, `settings.dart`: server URL + key saved on the device (shared_preferences). **Never commit the URL or key**; the repo is public.

`api.dart`, `models.dart` and `settings.dart` import nothing from Flutter, so they also run under plain `dart run`.

## Ryan's features

Ryan's code goes in `lib/features/...`, with tests in `test/features/...`, on `RyanFrontendking`. His Quick Browse Feed (`lib/features/feed/quick_browse.dart` + 4 widget tests) was checked inside this project unchanged: `flutter analyze` clean, 4/4 tests pass.

## Run

```
cd app
flutter pub get
flutter run -d chrome     # paste the URL + key (from the group chat) in the settings screen
flutter test
```

iPhone: on a Mac with Xcode + the iOS 26 platform installed, plus a free Apple ID (Personal Team): `flutter run` with the phone plugged in.

## Backend facts the core encodes

These come from the handoffs. They're data rules, not design.
- **Browsing:** photo paging or passive browsing never calls `/swipe` (Ryan's rule). Save is `PUT`/`DELETE /wishlist/{user}/items/{id}`; cart is `POST /cart/{user}/items {product_id, size, qty: 1}`.
- **Price:** `sale_price_usd`, when set and lower, is what's charged (`Product.effectivePrice`).
- **Try-on:** `TryOnResponse.isOutfitBoard` is true when try-on returned the collage fallback rather than a photo of the user.
