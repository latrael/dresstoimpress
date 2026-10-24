# Reference Dart API client (optional)

**This is not the app.** Ryan's own project is the app. This folder is a reference Dart client and models for every backend route. Copy from it if it's useful.

- `lib/core/api.dart`: one async method per route, with:
  - the `X-DTI-Key` header on every route except /health, /static and /img
  - `ApiError`: the `detail` text, plus the `unavailable` list on a checkout 409
  - a multipart upload helper that sends the image's real Content-Type
- `lib/core/models.dart`: `fromJson` for every response shape. It reads the snake_case keys, and optional fields are nullable.
- `lib/core/config.dart` / `settings.dart`: server URL + key saved in shared_preferences. **Never commit the URL or key**; the repo is public.
- `lib/main.dart`: a one-screen "paste URL + key → Test connection" check.

`lib/core/api.dart`, `models.dart` and `settings.dart` import nothing from Flutter, so they also run under plain `dart run`. That's how they were checked against the live backend.

Try it: `cd app && flutter pub get && flutter run -d chrome`. Flutter 3.29+ is needed.

Rules carried over from the handoffs:
- Never call `/swipe` for photo swipes or vertical browsing. Hearts use `PUT` / `DELETE /wishlist/{user}/items/{id}`.
- Charge the sale price when it's lower (`Product.effectivePrice`), with `price_usd` struck through.
- `TryOnResponse.isOutfitBoard`: label the image "Outfit board" when it is one.
- Web: retailer image hosts don't send CORS headers. Use `Image.network(url, webHtmlElementStrategy: WebHtmlElementStrategy.prefer)`, or the backend proxy `GET /img?url=`.
