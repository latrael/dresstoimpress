# Ryan: 1:00 AM – 10:00 AM

**Ryan owns the app and all of its design: order, screens, flows and visuals.**
- This file lines up **Ryan's own "Next work" list from `RYAN.md`** with the overnight window, and shows which backend routes and `core/` methods serve each item.
- **Ryan is asleep 1:00–9:00.** If his coding agent was started before bed (prompt in [README.md](README.md), "Before bed"), it works this list in Ryan's order, to Ryan's spec (`RYAN.md`, `frontend/QUICK_BROWSE.md`, the wireframe). Any design question it can't answer from that spec is skipped and listed in the morning report, never guessed.
- If no agent ran, the list simply starts at 9:15. The times are only suggestions; Ryan changes anything.
- Please write "Plan confirmed" (or changes) at the top of `RYAN_TO_ADAM.md`.

Team timeline: [README.md](README.md).

## Before starting
- [ ] `git pull origin staging` into `RyanFrontendking`. `core/` already has `searchProducts`, `createUser` / `getUser` / `updateUser`, `onboarding`, `applyStyle`, `imageProxyUrl`, plus `image_picker` (PR #11).
- [ ] `cd app && flutter pub get && flutter test`. Expect 14/14.

## Ryan's list, with what serves each item

| Suggested | # | Item (from RYAN.md) | Routes / `core` methods | Done when (against the live backend) |
| --- | --- | --- | --- | --- |
| 1:00–2:30 | 1 | **Size advice + product details** | `Api.sizeAdvice(productId, …)` → `POST /size` returns `{size, confidence, reason}`; `size` is always in stock, or null. It handles S–XL, XXS–3XL, `28/32`, `28inch`, US women's 0–24, and shoes (`shoeUs`). Height/weight default to `Settings.heightCm` / `weightKg` (170 / 65). | an H&M top and an H&M jean (`30/32` sizes) both get a size from `/size` |
| 2:30–4:00 | 2 | **Personal try-on** | `Api.tryOn([productId])` → `{imageUrl, cached, mode}`. ~5 s first time, instant after. `isOutfitBoard` = the collage fallback, not a photo of the user. `uploadBodyPhoto(bytes)`. | try-on images load for 3 products |
| 4:00–5:00 | 3 | **Complete the look + Fit Score** | `Api.completeLook(productId)` → items `{source: closet\|catalog, …}`, `newItemsTotalUsd`, `missing`. `Api.fitScore(productIds, closetItemIds)` → `{score, verdict, notes, breakdown}` | both work from a product |
| 5:00–6:00 | 4 | **Onboarding + full search** | `Api.onboarding(text)` → user + parsed `styles` / `budgets`. `Api.searchProducts(q, category, retailer, sort, limit, offset)` → `ProductPage` (`nextOffset` null at the end) | free text saves budgets; search covers all 418 products |
| 6:00–7:00 | 5 | **Fit Check:** create / likes / comments / shop | `createFitCheckUpload(bytes, caption)`, `updateFitCheckTags`, `likeFitCheck`, `commentFitCheck`, `shopFitCheck(postId)`, `fitScore(items: post.tagged)` | post, like, comment and shop all work |
| 7:00–8:00 | 6 | **Closet** | `closet()`, `uploadClosetItem(bytes)` (`duplicateOf`: an item it's probably the same as, or null; saved either way), `deleteClosetItem(id)` | upload + delete work |
| 8:00–8:30 | 7 | **Profile / Style DNA** | `style()` → `{headline, styles, palette (hex), patterns, formality, priceRanges, favoriteRetailers, avoid, confidence}`; `applyStyle()` (409 under 5 likes) | the profile loads for u_demo |
| 8:30 | | **PR `RyanFrontendking` → `staging`** + morning report at the top of `RYAN_TO_ADAM.md`: done, not done, questions | | `flutter analyze` clean, tests pass |

**Need a call or field that's missing?** Write it in `RYAN_TO_ADAM.md` (AI routes / `core`) or `RYAN_TO_NABIL.md` (commerce). Adam's session checks every 20 minutes all night.

## Ryan (human), 9:00–10:00
- [ ] 9:00 standup: read your agent's morning report.
- [ ] **Your decisions:**
  1. Adam's **PR #13** (adds `app/ios/` only; the permission-prompt wording and the icon are placeholders for you). Merge, or not?
  2. Nabil's **`/fit` guest page**: OK, OK with changes, or no?
- [ ] Review and merge (or hold) your agent's overnight PR.

## After 10:00
12:00 checkpoint A on Adam's iPhone (feed → size → add to cart → checkout `paid`) · 15:30 B (AI features reachable) · 17:00 freeze · 17:30 / 18:30 dry runs (you drive the app). If a checkpoint is at risk, you decide whether to hand a whole item to Adam or Nabil.
