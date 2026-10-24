# ADAM_TO_RYAN.md

Notes from Adam (AI lane) to Ryan (app). Newest at the top. **Ryan owns the app and its design.** Everything here is about data and routes: what the backend returns and what it means. How it looks is Ryan's call.

**Last updated:** Sat Oct 24, 2026, ~2:05 AM PT

---

## Overnight log (Adam's session, every 20 min; newest first)

- **3:45 PM: every council route has a core method. Merged: #25 (AI: tag `box` pins, `/ai/vibe`, body-photo delete), #26 (app: `BodyScanScreen`, server measurements, closet "Scan several pieces", cart Retry/refresh, delete own post, profile measurements), #28 (Nabil: size-first + seeded `/feed`, `/search*`, atomic cart, one Inspo feed). PR #30 (core only, matches #28; Adam merges):**
  - `api.feed(seed: productId)` → seeded Home (D9); cards carry `yourSize` (String?) and `inYourSize` (bool?: null = unknown, so no badge).
  - `api.search(q)` → `SearchResult{query, similar: List<Product>, goesWith: List<GoesWithItem{product?, closetItem?, fromCloset, reason}>}` (D10 two sections).
  - `api.searchStyles()` → `StyleChips{styles: [(tag, count)], trending: [TrendingProduct{product, trendCount}]}` (D11).
  - `api.searchPhoto(bytes, mimeType:)` → `PhotoSearchResult{photoUrl, tags: List<FitTag>, similar: List<RankedProduct>, goesWith}` (camera button).
  - `api.changeCartSize(productId, size:, newSize:)`; `StoreController.changeSize` already uses it, so the pencil is atomic now.
  - `Cart.unavailable: List<UnavailableItem>` (lines whose product/size went away; show them so the user can remove them; `count` includes them).
  - `api.updateUser(displayName:, styleText:, preferredStores:, onboarded:)` + `AppUser.preferredStores/onboarded` (onboarding steps 3 and 7).
  - `api.fitCheckFeed(author:)` for "tap a name → their posts".
  - Tag pins: `FitTag.box` is `[xMin, yMin, xMax, yMax]` 0–1 (null on posts made before 15:30).
  - `u_demo` has no body profile yet, so `inYourSize` is null everywhere until Adam runs the body scan for the demo user.
- **3:15 PM: all 7 PRs merged; council v2 read; what's built for your P0s.** The shared server runs merged `staging` (343 tests, smoke 10/10). Two PRs from Adam are coming before the freeze, both avoiding `main.dart` so your shell rewrite (island tabs + top-right icons) merges clean.
  - **Body scan (your onboarding screen 4) is ready to drop in.** `features/profile/body_scan_screen.dart` → `BodyScanScreen(api, heightCm?, weightKg?)`. It asks height (+ optional weight), picks a photo, calls `api.bodyScan`, shows the estimates and pops with a `BodyProfile`. The onboarding screen already uses it ("Scan from a photo" pre-fills the measurement fields). The photo also becomes the try-on photo. Measurements are saved on the server by `ShopperProfile.syncToServer(api)` and restored by `withBody(..., gapsOnly: true)`, so **D5 is done for measurements**; `preferred_stores` and `onboarded` are Nabil's.
  - **Liked screen (D8):** build it from `api.wishlist()` (returns `List<Product>`), not from filtering the feed. Today's heart icon in `main.dart` is a sticky saved-only filter over `store.feed`, which is the "you have to unclick the likes" bug Adam saw. Filtering the feed also hides liked items that fell out of the feed.
  - **Closet (D8):** `ClosetScreen` now has "Scan several pieces" → `api.digitizeCloset(bytes)` → one tagged item per garment, each cropped. Answers council Q1: both one-per-photo and whole-outfit work.
  - **Inspo tag pins (your "tap photo → tags on each piece"):** coming in the AI PR as `FitTag.box = [xMin, yMin, xMax, yMax]` (0–1 fractions of the photo; `null` on old posts, so fall back to your list). Position each tag at the box center.
  - **Delete own post:** trash icon on your own `FitPostCard` → `api.deleteFitCheck(id)`; the feed refreshes.
  - **Cart:** refreshes from the server when opened and after any error; receipt shows "Paid $X of $Y" with **Retry payment** per failed store (`api.retryOrder(orderId, retailer:)`, PR #20's route).
  - **Discover vibe search (D10 text search):** `api.vibe(q)` → `{styles, categories, colors, keywords}`, for when Nabil's `/search?q=` isn't there yet. Coming in the AI PR.
  - **User screen:** "Your measurements" section + a Body scan button are added to `ProfileScreen`; regroup as you like.
- **3:00 PM: answers to your 2:40 requests, plus an app audit Adam asked for.**
  - **Your asks:**
    - **(1) Server-side measurements: done in PR #22.**
      - `Api.updateBodyProfile(heightCm, weightKg, waistCm, chestCm, hipCm, inseamCm, shoeUs, fit, usualSizes)` → `BodyProfile`. Lengths in cm; only the fields passed change.
      - Read it back on any device via `getUser().bodyProfile`.
      - `Api.sizeAdvice` now sends `user_id`, so `/size` uses the saved fit (unless you pass one), shoe size and waist. It falls back to the usual size for that category, but only if that size is in stock, including when no height/weight is known.
    - **(2) Body scan → measurements: done in PR #22.**
      - `Api.bodyScan(bytes, heightCm:, weightKg:)` → `BodyScanResult`. The model estimates chest / waist / hip / inseam / build from a full-body photo, with height as the scale.
      - `source` is `ai` or `estimate`. `fullBody == false` comes with a `note` asking for a head-to-feet photo.
      - The same photo becomes the try-on photo. Values the user typed win over the scan.
    - **(3) Atomic cart size change** and **(4) category price maximums** are Nabil's lane, forwarded to him.
  - **Also new in core:**
    - `Api.digitizeCloset(bytes)` → `List<ClosetItem>` (PR #22): one photo of several clothes → one tagged, cropped closet item per garment; `duplicateOf` is set as with uploads.
    - `Api.deleteFitCheck(postId)` (PR #17).
  - **Image fix in core (PR #17):** `imageUrl` / `imageProxyUrl` now load our own photos (`/static/uploads|tryon`) saved under an old server address from the connected server. A photo shown with `Image.network(url)` directly doesn't get the fix; through `api.imageProxyUrl` it does.
  - **Audit findings. Reporting only, your call how to fix:**
    - The AppBar heart is the saved-only filter (main.dart ~294-302) and it stays on across tabs. Adam took it for "likes you have to unclick".
    - The saved view is built from the loaded feed, not `Api.wishlist()`, so items saved from search, Shop this fit or Complete the look never show up there.
    - Saves and likes only flip after the server replies. One busy flag per post blocks Like while Shop this fit runs (social_feed ~203/281).
    - No thumbnails in cart rows, Complete the look or order history; no body-photo preview in Profile.
    - The cart screen doesn't reload from the server when opened or after an error (cart_screen ~78-82).
    - The receipt shows "Total" even when a store failed.
    - Order retry needs Nabil's PR #20. I'll add `Api.retryOrder` to core when it merges.
    - `Api.swipe` is never called, so seen items stay in the feed. Saves still teach the feed (wishlist counts as likes in style memory).
    - **No UI path yet for:** digitize wardrobe, body scan, the saved list, order retry, deleting your own post. Adam wants everything in the original docs reachable before the 17:00 freeze.
- **13:45: the shared backend is back at a NEW URL** (Adam DMs it; the 10:25 one is dead); update your device settings. Smoke 10/10. Your PR #18 merges cleanly with #17 + #19: analyze clean, 39/39. PR #19 makes `/feed` return immediately after swipes (same response shape). Reasons are also more varied now.
- **10:55 AM: #13 and #16 merged** (with your OK), plus #15 and #14. The shared server runs `staging` 096a4cb: smoke 10/10, `flutter analyze` clean, 31/31. The URL and key came by DM. Next on Adam's side: the iPhone build from `staging`.
- **10:35 AM: read your morning report and PR #16.** Checked on top of #15 + #14 + #13: no conflicts, `flutter analyze` clean, **31/31** (your e83259b), backend 275, and the unsigned iOS release build of the combined app succeeds. The new backend URL comes from Adam by DM, not Git. Merges are the humans' call: #15 → #14 → #13 → #16.
- **10:25 AM: the shared backend is back** at a new URL, which Adam DMs you; update it in your device settings. Smoke test 10/10. Stored image URLs were rewritten to the new address. PR #13 still needs your OK.
- **8:10 AM:** the shared backend URL is still down. It changes at 8:45, and Adam DMs the new one. PR #13 (`app/ios`) needs your OK at 9:15; the Info.plist wording, icon and display name are yours. The morning report is at the top of `docs/progress.md`.
- **2:05 AM:**
  - **Data facts:**
    - When the AI is unavailable, `502` errors from `/closet/upload`, `/closet/tag`, `/ai/tag-fit` and `/tryon` now carry a plain `detail` ("photo tagging is unavailable right now, try again in a minute"), with no provider details.
    - With every AI provider down, `/feed` still has reasons (rules), and `/tryon` returns `mode: collage`.
  - **u_demo's cart, wishlist and swipes on the shared store were cleared at 2:00** (my mistake). If your agent restored test state there, it's gone now.
  - Thanks for confirming the plan.
- **2:15 AM: the shared tunnel died at ~1:25.** The backend URL changes at 8:45, and Adam will DM the new one; update it in your device settings. Stored image URLs (try-ons, body photo, closet) get rewritten to the new address automatically (PR #15), so the old ones won't break.
- **1:50 AM: PR #15** (AI quality pass). Data behavior only, no shapes changed:
  - `/feed` reasons never name a closet item the user doesn't have.
  - The feed ranking is budget-first.
  - "Shop this fit" returns each post item's exact product first and collapses color variants into one card.
  - Women's numeric jean sizes are estimated correctly.
- **1:20 AM: PR #13** (adds `app/ios/` for the iPhone build; nothing in `lib/`). **Needs your OK at standup.** The camera / photo-library permission text in `Info.plist` and the app icon are placeholders for you; iOS requires those permission strings, or `image_picker` crashes.
- No asks from you seen yet. I check `RYAN_TO_ADAM.md` every 20 minutes.

---

## Sat ~1:15 AM: overnight plan (1–10 AM) is up; please confirm by 9:15

**[`docs/plan-sat/ryan.md`](docs/plan-sat/ryan.md)** lines up your own RYAN.md "Next work" list with the overnight window (agent-only, everyone is asleep 1–9) and the 9:00 handoff. Your agent runs it only if you started it before bed (prompt in `docs/plan-sat/README.md`); otherwise it starts at 9:15. For each item it shows the exact `core/` method and route.
- **Order and design are yours;** the times are only suggestions. Team view: [`docs/plan-sat/README.md`](docs/plan-sat/README.md).
- **Two decisions for you at standup:**
  1. My iOS platform PR (adds `app/ios/` only, no `lib/` changes). Merge, or not?
  2. Nabil's `/fit` guest page: OK, OK with changes, or no?
- **Please write "Plan confirmed"** (or your changes) at the top of `RYAN_TO_ADAM.md` by 9:15.

---

## Fri ~11:15 PM: your 3 core requests are in PR #11

From your RYAN_TO_ADAM "concrete core requests". All of it is in `app/lib/core` plus `pubspec`; none of your files changed.
1. **`Api.imageProxyUrl(url)`:**
   - Retailer images (H&M, Uniqlo, …) → `GET /img?url=`.
   - `/static/...` → base URL.
   - Anything else is returned unchanged.
   - `imageUrl()` is **unchanged**, so your `store_controller.dart` wrapper keeps working. Switch whenever you want; the README claim was wrong before, sorry.
2. **Nabil's newer routes:**
   - `searchProducts({q, category, retailer, inStock, sort, limit, offset})` → `ProductPage {items, total, limit, offset, nextOffset}`. `nextOffset` is null on the last page.
   - `createUser`, `getUser([id])`, `updateUser(...)` → `AppUser {id, displayName, styleText, priceRanges, bodyPhotoUrl, friends}`.
   - `onboarding(text, {displayName, userId})` → `OnboardingResult {user, styles, budgets, unmatched}`.
   - `applyStyle()` → `StyleApplyResult {user, profile}`. It throws `ApiError` 409 with fewer than 5 liked items.
3. **`image_picker`** is in `pubspec.yaml`.

**Checked:**
- `flutter analyze` clean, and `flutter test` **14/14**: your 8 unchanged, plus 6 new core tests in `test/core/`.
- **Live, read-only:** `searchProducts('baggy jeans')` returns 3 of 29 with `nextOffset` 3; `getUser`, `style()` and the 404 parse; `imageProxyUrl` on an H&M photo returns 200 image/jpeg.

**Server:** it now runs merged `staging` (your #10 included), and the smoke test passes 10/10 through the tunnel. The `/fit` guest page stays off until you decide.

---

## Fri ~9:40 PM: shared shell + core are published; your Feed drops in as-is

You asked (RYAN_TO_ADAM.md) for the starter so the Feed can be connected. It's on branch **`flutter-starter`**, folder `app/`:
- `pubspec.yaml` (package `dress_to_impress`, Flutter 3.47.x, packages: `http`, `shared_preferences`, `image_picker`)
- `lib/main.dart`: a bare entry with a URL + key settings screen and "Test connection". Placeholder only; replace or restyle it as you like.
- `lib/core/api.dart`: one async method per backend route, the `X-DTI-Key` header, readable errors (including the checkout 409 object), and multipart upload. It also has the `/img?url=` image helper you need on web.
- `lib/core/models.dart`: parsers for every response shape. They were checked against the live backend: 13/13 routes decode.
- `lib/core/config.dart`, `lib/core/settings.dart`: URL + key saved on the device, never in code.

**Your Feed was checked inside it, unchanged:** analyze clean, your 4 tests pass (details below).

**Merging:** your branch is 62 commits behind `staging`, so merge `staging` in before your PR. Your files don't overlap with anyone's.

**Plan:** you own all of the app's screens and design. Nabil and Adam stay on the backend and answer API questions. An earlier version of my plan split the screens between the three of us; that's withdrawn. iPhone build afterward on Adam's Mac (needs the iOS 26 platform installed in Xcode first).

**URL + key:** Adam is sending them to you privately so you can run against the live backend.

**Status, deviations and next steps for everyone:** [`docs/progress.md`](docs/progress.md).

## Integration check (done)

I copied `app/lib/features/feed/` and `app/test/features/feed/` from `RyanFrontendking` (c45ad88) into `flutter-starter`, unchanged, then ran `flutter pub get`, `flutter analyze` and `flutter test` (Flutter 3.47.8):
- `flutter analyze`: **no issues**.
- `flutter test`: **4/4 pass** (photo gesture boundaries/dots, size/cart validation, vertical browse/single-image dots, double-tap save/cart error).
- **No file overlaps.** The starter has no `features/` or `test/` files, so yours merge cleanly.
- **Fix on my side:** the starter's `pubspec.yaml` was missing the `flutter_test` dev dependency, so your tests couldn't run. Added in `flutter-starter` 1b4aff2.

**PR #9** (`flutter-starter` → `staging`) is open. Once it's merged, merging `staging` into your branch gives you the shell + core. To get it sooner, merge `origin/flutter-starter` directly.

## Backend facts for your screens

All routes need the header `X-DTI-Key: <key>` (private, from the group chat) except `GET /health`, `/static/...` and `/img`. Demo user: `u_demo`. Catalog: 418 H&M + Uniqlo products (48 shoes), all AI-tagged (`label`, `style_tags`, `pattern`, `formality` 1–5).

| Route | Returns / means |
| --- | --- |
| `GET /img?url=<image_url>` | the same image, re-served by our backend. Needed on web: retailer image servers refuse direct loads. Only retailer image hosts are allowed. |
| `GET /feed?user_id=&limit=` (Nabil) | Products + `reason` (AI, may be empty), `score`, `pairs_with` (closet item ids) |
| `POST /size {product_id, height_cm, weight_kg, fit?, waist_in?, shoe_us?}` | `{size, confidence: high\|medium\|low, reason}`. `size` is always an in-stock size, or null. Handles S–XL, XXS–3XL, `28/32`, `28inch`, US women's 0–24 and shoes (needs `shoe_us`). |
| `POST /tryon {user_id, product_ids, closet_item_ids?}` | `{image_url, cached, mode}`. `mode: "ai"` = the user wearing it (~5 s first time, instant after). `mode: "collage"` = an outfit board, **not** a photo of the user. It's only used if image generation fails. |
| `POST /complete-look {user_id, product_id, budget_usd?}` | `{items: [{source: "closet"\|"catalog", id, category, label, reason}], new_items_total_usd, missing}`. `source: closet` = something the user already owns. |
| `POST /ai/fit-score {items?, product_ids?, closet_item_ids?}` | `{score 0–100, verdict (≤6 words), notes (2–4 lines), breakdown {color/40, pattern/20, formality/20, completeness/20}}`. Rules only, free, instant. `items` can be a Fit Check post's `tagged`. |
| `GET /closet/{user_id}` | `[ClosetItem]`: `id, label, category, color, pattern, style_tags, formality, image_url, duplicate_of` |
| `POST /closet/upload` (multipart `user_id`, `file`) | the new ClosetItem. `duplicate_of` = the id of an item it's probably the same garment as, or null. The item is saved either way. |
| `DELETE /closet/{user_id}/{item_id}` | `{deleted}`. 404 if it isn't that user's. |
| `GET /users/{user_id}/style` | Style DNA: `{headline, styles[{tag, share}], palette[{name, family, hex, share}], patterns, formality{avg, label}, price_ranges, favorite_retailers, avoid, sample_size, confidence}` |
| `POST /users/{user_id}/style/apply` | saves the learned `price_ranges` on the user (the feed ranks in-budget items first). 409 with fewer than 5 liked items. |
| `POST /users/{user_id}/body-photo` (multipart `file`) | `{body_photo_url}`, used by try-on. |
| `POST /ai/tag-fit {image_url}` | items seen in an outfit photo (Fit Check auto-tags) |

Commerce routes (cart, checkout, wishlist, Fit Check posts, onboarding, users, search) are in Nabil's `NABIL_TO_RYAN.md`.

**Known data limits:**
- H&M has no descriptions (always `null`); Uniqlo has 1 photo per product.
- The feed's first load takes ~6 s while Claude ranks, then it's cached for 10 minutes.
- Fit Check live search covers H&M only.
