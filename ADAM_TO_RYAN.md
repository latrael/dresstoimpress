# ADAM_TO_RYAN.md

Notes from Adam (AI lane) to Ryan (app). Newest at the top. **Ryan owns the app and its design.** Everything here is about data and routes: what the backend returns and what it means. How it looks is Ryan's call.

**Last updated:** Sat Oct 24, 2026, ~2:05 AM PT

---

## Overnight log (Adam's session, every 20 min; newest first)

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
