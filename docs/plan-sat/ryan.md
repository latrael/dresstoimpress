# Ryan: Saturday plan (9:00 AM – 7:00 PM)

**Ryan owns the app and all of its design: order, screens, flows and visuals.**
- This file only lines up **your own "Next work" list from `RYAN.md`** with the team checkpoints, and shows which backend routes and `core/` methods serve each item.
- The times are suggestions so the checkpoints land. Move anything you like.
- Please write "Plan confirmed" (or your changes) at the top of `RYAN_TO_ADAM.md` by 9:15.

Shared timeline: [README.md](README.md).

## 8:45: before standup
- [ ] `git pull origin staging` into `RyanFrontendking`. `core/` now has `searchProducts`, `createUser` / `getUser` / `updateUser`, `onboarding`, `applyStyle` and `imageProxyUrl`, plus `image_picker` in `pubspec` (your request, PR #11).
- [ ] `cd app && flutter pub get && flutter test`. Expect 14/14.
- [ ] URL + key in device settings. Adam reposts the URL if the tunnel changed overnight.

## 9:00–9:15: standup
**Decisions only you can make:**
1. Adam's iOS platform PR (adds `app/ios/` via `flutter create --platforms ios`; no `lib/` changes). OK to merge?
2. Nabil's `/fit` guest page: OK, OK with changes, or no?

## Your list, with what serves each item

| # | Item (from RYAN.md) | Routes / `core` methods | Done when (against the live backend) |
| --- | --- | --- | --- |
| 1 | **Size advice + product details** | `Api.sizeAdvice(productId, …)` → `POST /size` returns `{size, confidence, reason}`; `size` is always in stock, or null. It handles S–XL, XXS–3XL, `28/32`, `28inch`, US women's 0–24, and shoes (needs `shoe_us`). Height/weight: `Settings.heightCm` / `weightKg` (defaults 170 / 65) until onboarding sets them. | an H&M top and an H&M jean (sizes like `30/32`) both get a size from `/size` in the app |
| 2 | **Personal try-on** | `Api.tryOn([productId])` → `{imageUrl, cached, mode}`. ~5 s first time, instant after. `isOutfitBoard` = the collage fallback, not a photo of the user. `uploadBodyPhoto(bytes)` sets the user's photo. | try-on images load for 3 products on the phone |
| 3 | **Complete the look + Fit Score** | `Api.completeLook(productId)` → items `{source: closet\|catalog, id, category, label, reason}`, `newItemsTotalUsd`, `missing`. `Api.fitScore(productIds, closetItemIds)` → `{score 0–100, verdict, notes, breakdown}` (free, instant). | both work from a product |
| 4 | **Onboarding + full search** | `Api.onboarding(text)` → the user plus what was parsed (`styles`, `budgets`). `Api.searchProducts(q, category, retailer, sort, limit, offset)` → `ProductPage` (page on with `nextOffset`, null at the end). | free text like "Y2K, tops under $40" saves budgets; search covers all 418 products |
| 5 | **Fit Check:** create / likes / comments / shop | `createFitCheckUpload(bytes, caption)` (the AI pre-fills tags), `updateFitCheckTags`, `likeFitCheck`, `commentFitCheck`, `shopFitCheck(postId)`, `fitScore(items: post.tagged)`. Real posts arrive ~11 AM (Nabil). | posting a photo, liking, commenting and shopping a fit all work |
| 6 | **Closet** | `closet()`, `uploadClosetItem(bytes)` (returns `duplicateOf`: an item it's probably the same as, or null; saved either way), `deleteClosetItem(id)`. Adam's real closet photos land ~11 AM. | upload + delete work; a duplicate is detectable |
| 7 | **Profile / Style DNA** | `style()` → `{headline, styles, palette (with hex), patterns, formality, priceRanges, favoriteRetailers, avoid, confidence}`. `applyStyle()` saves the learned budgets (409 under 5 likes). | the profile loads for u_demo |
| 8 | **iPhone verification** | Adam builds and runs it on his iPhone (`flutter run --release`) | your screens work on the phone |

## Suggested blocks (your call)
| Time | Suggested |
| --- | --- |
| 9:15–10:30 | #1 size advice + product details |
| 10:30 | PR `RyanFrontendking` → `staging` (merge window 1) |
| 10:30–12:00 | #2 try-on |
| **12:00** | **Checkpoint A on Adam's iPhone:** feed → size → add to cart → checkout `paid` (the first live checkout; Nabil confirms in Nessie) |
| 13:30–15:30 | #3 complete the look + Fit Score, #4 onboarding + search |
| **15:30** | **Checkpoint B:** AI features reachable in the app |
| 15:30–17:00 | #5 Fit Check, #6 closet, #7 profile / Style DNA. PR by 16:30 (merge window 4). |
| **17:00** | **Freeze:** fixes only. Adam rebuilds the iPhone app. |
| 17:30 / 18:30 | Dry runs #1 and #2 (you drive the app) |

**If a checkpoint is at risk:** you decide whether to hand a whole item to Adam or Nabil, at 12:00 or 15:30.

**Need something from the backend?** Write it in `RYAN_TO_ADAM.md` (AI routes / `core`) or `RYAN_TO_NABIL.md` (commerce). Adam's session checks every 20 minutes.
