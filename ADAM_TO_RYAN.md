# ADAM_TO_RYAN.md

Notes from Adam (AI lane) to Ryan (app). Newest at the top. **Ryan owns the app and its design.** Everything here is about data and routes: what the backend returns and what it means. How it looks is Ryan's call.

**Last updated:** Fri Oct 23, 2026, ~9:40 PM PT

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
