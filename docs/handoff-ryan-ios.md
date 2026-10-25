# Handoff for Ryan (and Ryan's agent): run the iOS app against the shared server, and what's in `staging`

Sat Oct 24, 2026, ~5:15 PM PT. Written by Adam's session. **Ryan owns the app and its design**; this file only says what exists, how to connect, and what each core method returns. Nothing here asks for a design choice.

Read this first, then `docs/sprint-2.md` (the council's current list), then `ADAM_TO_RYAN.md` (dated log, newest at the top).

---

## 1. Run the app on your iPhone, already connected

The app reads its server and key from compile-time defines (`app/lib/core/config.dart`: `DTI_API_BASE`, `DTI_API_KEY`), so a build made with them opens connected, with nothing to type. Saved values on the device win over the defines, so **delete the old Niche app from the phone first** if it was installed before.

**Adam DMs you the exact command with the URL and key filled in.** Its shape (never commit the real values, the repo is public):

```
cd <your clone>/dresstoimpress && git checkout staging && git pull
cd app && flutter pub get
flutter devices                       # copy your iPhone's id
flutter run --release -d <iphone-id> \
  --dart-define=DTI_API_BASE=<tunnel URL from Adam> \
  --dart-define=DTI_API_KEY=<shared key from Adam>
```

- Camera + photo-library permission strings are already in `app/ios/Runner/Info.plist`, so photo upload, body scan, closet scan, photo search and Inspo posts work on iOS.
- Signing: open `app/ios/Runner.xcworkspace` once, Runner → Signing & Capabilities → your team, if `flutter run` asks.
- **User id:** on the welcome screen create your own account (`POST /users`) or use `u_demo`, the fully set-up demo user: real body scan (170 cm / 70 kg, slim, chest 36 / waist 30.5), `shop_for=men`, stores H&M + Uniqlo, a 10-piece closet digitized from real photos, warmed try-ons.
- **Tunnel URL changes** whenever Adam restarts cloudflared; he DMs the new one. Then either rebuild with the new define, or in the app: User icon → Connection settings → new URL → Test and connect.
- **No Mac build handy:** Safari on the iPhone → `<tunnel URL>/static/uploads/web/index.html` (the web build of current `staging`, refreshed after each merge), then User → Connection settings → URL, key, user id.

**Checks if something fails:**

| Symptom | Cause | Fix |
| --- | --- | --- |
| "Connect to use a private body scan" / "Connect your account to digitize your closet" | App is in demo mode: no key saved on this device | Build with the defines above, or enter URL + key in Connection settings |
| 401 / "Missing or wrong key" | Wrong or old key | Ask Adam for the key again |
| Nothing loads, health fails | Old tunnel URL | Ask Adam for the current URL |
| Body scan / photo upload spins then times out | Huge photo on a slow link | Fixed in #36: photos are shrunk to 1600 px on the phone and uploads get 180 s. Pull `staging`. |

---

## 2. What's live on the shared server (`staging`, all merged)

| Area | Routes | Core method(s) in `app/lib/core/api.dart` |
| --- | --- | --- |
| **Home feed** (size-first, seeded) | `GET /feed?user_id&limit&seed&seed_shown` | `api.feed({limit, category, retailer, seed, seedShown})` → cards with `yourSize` (String?) and `inYourSize` (bool?, null = unknown, so no badge). `seedShown: true` (only with `seed`) = you already showed the seed card, so this reload leaves it out; sends `seed_shown=true` only when true. |
| **Discover** | `GET /search?q`, `GET /search/styles`, `POST /search/photo` | `api.search(q)` → `SearchResult{query, similar, goesWith}`; `api.searchStyles()` → `StyleChips{styles:[(tag,count)], trending}`; `api.searchPhoto(bytes)` → `PhotoSearchResult{photoUrl, tags, similar, goesWith}`; `api.vibe(q)` → `VibeQuery{styles, categories, colors, keywords}` |
| **Product / size** | `GET /products/{id}`, `POST /size` | `api.product(id)`, `api.sizeAdvice(id, …)` (sends `user_id`, so the server uses the saved body profile) |
| **Liked** | `/wishlist/...` | `api.wishlist()` → `List<Product>` (build Liked from this, not by filtering the feed), `api.wishlistIds()`, `api.save(id)`, `api.unsave(id)` |
| **Cart + checkout** | `/cart/...`, `/checkout`, `/orders`, `POST /orders/{id}/retry` | `api.cart()` (has `unavailable[]`), `api.addToCart`, `api.removeFromCart`, `api.changeCartSize(id, size:, newSize:)` (atomic pencil), `api.checkout()`, `api.orders()`, `api.retryOrder(orderId, retailer:)`. Every line (`CartItem` and `UnavailableItem`) has `imageUrl` (String?) from the flat `image_url`: the thumbnail even when `product` is null because it left the catalog. |
| **Try-on** | `POST /tryon` | `api.tryOn([productIds], closetItemIds:)` → `TryOnResponse{imageUrl, mode: ai|collage}`. Prompt v3 (#37): same person, garment names, the user's build and recommended size so it drapes on their body. 15–60 s fresh, instant when cached. |
| **Complete the look + Fit Score** | `POST /complete-look`, `POST /ai/fit-score` | `api.completeLook(id)`, `api.fitScore(...)` |
| **AI Fit Creator** (no screen yet) | `POST /fits/create`, `GET /fits/{id}`, `POST /fits/{id}/try-on`, `POST /fits/{id}/cart` | `api.createFits({count, occasion, mustInclude, budgetUsd, tryOn})` → `List<OutfitFit{id, name, occasion, reason, pieces:[FitPiece{slot, source: closet|catalog, closetItem?, product?, yourSize, inYourSize}], newTotalUsd, closetCount, tryOnUrl?}>`; `api.fit(id)`; `api.fitTryOn(id)` (lazy image); `api.addFitToCart(id)`. Every fit has ≥ 1 new in-size piece; occasion is free text ("class", "date", "rooftop party"). |
| **Closet** | `/closet/...`, `POST /closet/digitize` | `api.closet()`, `api.uploadClosetItem(bytes)` (one piece), `api.digitizeCloset(bytes)` (one photo with several pieces → one item each), `api.deleteClosetItem(id)` |
| **Body scan + measurements** | `POST /users/{id}/body-scan?commit=`, `POST /users/{id}/body-scan/confirm`, `PATCH /users/{id}/body-profile`, `DELETE /users/{id}/body-photo` | `api.bodyScan(bytes, heightCm:, weightKg:)` → `BodyScanResult{bodyPhotoUrl, profile: BodyProfile, committed}` (photo also becomes the try-on photo). **Draft → review → confirm:** `api.bodyScan(..., commit: false)` runs the scan but saves nothing on the user (`committed: false`); show `profile`, let the user edit, then `api.confirmBodyScan(draft, {heightCm, weightKg, chestIn, waistIn, hipIn, inseamIn, build, fit, shoeUs})` with only the fields the user changed (profile units: cm / kg / inches / US shoe) → saves photo + profile, edited fields become `manual` (typed, win over later scans), `committed: true`. Abandoning the review = call nothing. `api.updateBodyProfile({heightCm, weightKg, waistCm, chestCm, hipCm, inseamCm, shoeUs, fit, usualSizes})` (send metric; the server stores inches); `api.deleteBodyPhoto()`; `getUser().bodyProfile` reads it back. Ready-made widget: `features/profile/body_scan_screen.dart` `BodyScanScreen(api, heightCm?, weightKg?)` pops a `BodyProfile`. |
| **User / onboarding** | `POST /users`, `GET/PATCH /users/{id}`, `POST /onboarding` | `api.createUser({…, shopFor})`, `api.getUser`, `api.updateUser({displayName, styleText, priceRanges, preferredStores, onboarded, shopFor})` (`shopFor`: `men|women|both`, sent only when non-null; read back as `AppUser.shopFor`, `both` when the server never set it), `api.onboarding(text)` (plain-English style + "tops under $30" budgets) |
| **Style DNA** | `GET /users/{id}/style`, `POST …/style/apply` | `api.style()`, `api.applyStyle()` |
| **Inspo** | `/fitcheck/...` | `api.fitCheckFeed({limit, author})` (everyone's posts; `author` = one person), `api.createFitCheckUpload(bytes, caption:)` (AI tags each piece), `api.updateFitCheckTags`, `api.shopFitCheck(id)`, `api.likeFitCheck`, `api.commentFitCheck`, `api.deleteFitCheck`. Tags carry `FitTag.box = [xMin, yMin, xMax, yMax]` (0–1 of the photo, null on older posts) for pins on each piece. |
| **Shop a photo's outfit** | `POST /ai/tag-fit`, `POST /ai/shop-fit` | `api.tagFit(url)`, `api.shopFit(...)` |
| **Card text** | — | `Product.blurb()` → one line (≤ 110 chars) for cards; `Product.description` keeps the full retailer text for "More". |

Errors: every method throws `ApiError{status, message}`; AI-down routes return 502 with a plain sentence you can show as-is.

---

## 3. Coming from Adam's lane (PRs, not merged yet; no breaking changes)

| What | Branch | What it adds for the app |
| --- | --- | --- |
| Sizing from real measurements + cross-department (a man's measurements on women's charts and vice versa) | `adam/measure-sizing` | Nothing to change: `yourSize` / `sizeAdvice` just get more accurate; `/size` adds `size_system: "us"`. |
| Onboarding from photos | `adam/photo-onboarding` | `POST /onboarding/photos` → `api.onboardFromPhotos(photos, heightCm:, weightKg:, styleHint:)` → closet added, body scanned, style inferred, `shop_for` detected. A "fast setup" option if the council picks it (sprint-2 Q7). |
| Closet pieces as real product photos + brand | `adam/closet-real-pieces` | `ClosetItem.brand / productId / catalogImageUrl / matchConfidence / cropImageUrl`; `image_url` becomes the clean catalog photo when matched; `api.updateClosetItem(id, {label, brand, …})`, `api.rematchClosetItem(id)`. |
| Product summaries + men's/women's fallback | `adam/summary-dept` | `Product.summary` (1–2 sentences, also for H&M items that have no description); `blurb()` prefers it. |

`ADAM_TO_RYAN.md` gets a dated line with the PR number when each one merges.

---

## 4. Adam's asks for your screens (from Adam directly; the look is your call)

1. Height, weight and measurements as **scroll pickers** instead of typed fields.
2. **US units** in the UI (ft/in, lb, US sizes); convert to cm/kg in the app, the server stays metric.
3. First-run onboarding: let the user open **Connection** inline instead of the "connect to use body scan" dead end (sprint-2 A9).
4. A **"Fits for you"** screen for the AI Fit Creator (sprint-2 Q6 decides where it lives).
5. Closet: each piece should look like the real product (the closet PR above gives you the catalog photo + brand); a brand label on each piece, kept minimal.

The rest of your list is `docs/sprint-2.md` Part A (A1–A10) and "Ryan" under "Who does what".

---

## 5. Working agreement

- Branch from `staging`, PR into `staging`; Adam merges. Don't edit `app/lib/core/` (Adam's lane): ask in `RYAN_TO_ADAM.md` and the core method appears in a PR.
- Run `flutter analyze` (0 issues) and `flutter test` before pushing; Adam merge-checks every PR against the others.
- The shared server is Adam's Mac. If it's down, Adam restarts it and DMs any new URL.
