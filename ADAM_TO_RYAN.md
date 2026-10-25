# ADAM_TO_RYAN.md

Notes from Adam (AI lane) to Ryan (app). Newest at the top. **Ryan owns the app and its design.** Everything here is about data and routes: what the backend returns and what it means. How it looks is Ryan's call.

**Last updated:** Sat Oct 24, 2026, ~10:40 PM PT
**Last updated:** Sat Oct 24, 2026, ~11:30 PM PT

---

## Overnight log (Adam's session, every 20 min; newest first)

- **Sat Oct 24, ~10:40 PM: Fit Score v2 (PR `adam/fit-score-v2`, backend + core, all additive; nothing in `features/` touched).** The score used to give everything 80+ (v1 on 300 random catalog outfits: median 92, 88% at 80+). v2 is a calibrated rubric: random outfits now median 49 (5% at 80+, 0% at 90+), curated one-style outfits median 77, and 90+ only when every criterion is 8+. `Api.fitScore(items:, productIds:, closetItemIds:, targetStyle:, photoUrl:, occasion:)` → `FitScore` keeps `score`, `verdict`, `notes`, `breakdown` (same /40 /20 /20 /20 scales your `fitScoreCard` renders) and adds: **`primaryStyle`** (`'streetwear'|'minimalist'|'classic'|'y2k'|'preppy'|'athleisure'|'vintage'|'business'|'boho'|'grunge'`; the headline score is the outfit's score *as that style*), **`criteria`** (`List<FitCriterion{name, score10 (0–10), note?}>`: color, silhouette, pattern, formality, style, completeness, layering, + occasion when you pass one), **`styleScores`** (`Map<String,int>` 0–100 per style), `rawScore`, `source` (`'rules'` or `'rules+ai'`). `verdict` is now `"68 as streetwear: strong silhouette, palette too busy"`. **UI suggestion (your call):** headline `"68 · as streetwear"`, the verdict tail under it, then the criteria list as `name · 7/10` with the note; the old 4-line breakdown can go. Pass **`photoUrl: post.photoUrl`** for Fit Check posts (one cached Claude vision critique gets blended in when AI is on) and `targetStyle` if you add a "score it as…" picker. `CompleteLook` gains `fitScore` (`FitScore?`, the completed outfit, said as the anchor's style) and `primaryStyle`; the picker now also hard-excludes athletic ↔ formal clashes (no leather belt on an athletic tee). Tests: `app/test/core/api_fit_score_v2_test.dart`. Server detail: `docs/schema.md`, `docs/ai-writeup.md` "Fit Score v2".

- **Sat Oct 24, ~11:30 PM: Shop the look, grouped (PR `adam/tryon-v5`, core + backend, additive).** Shop the look: show one chip/tab per tagged piece (`api.shopFitCheckGrouped(postId)` → `List<ShopTagGroup{tag: FitTag, products: List<RankedProduct>}>`, post order, up to 6 similar items per piece, closest match first, viewer's shop_for respected), each with its own similar items; tapping a piece's pin in Inspo should open that piece's group (match by index or `tag.label`; `tag` carries `label, category, color, box, productId`). A piece with no match comes back with `products: []`, so still draw its chip (and an empty state) instead of dropping it. `shopFitCheck` (flat) is unchanged. Server: `GET /fitcheck/{id}/shop?user_id=&grouped=true`, also `POST /ai/shop-fit` with `"grouped": true`. **Try-on now edits in place (v5):** the result keeps the user's own photo (background, pose, lighting, framing) and swaps only the garment region, so it no longer re-renders the whole picture on a white backdrop; cache key bumped, old try-ons regenerate on next request. Closet clean shots still stay white. **Image 1 is no longer always the body photo:** the server picks the user's best own photo for the garments being tried (body photo or any closet outfit / worn-in photo that shows a garment of the same category, full body, not cut off, pieces that go with it) and tells the model where that garment sits. `TryOnResponse.sourcePhotoUrl` (and `OutfitFit.tryOnSourcePhotoUrl` for Fit Creator) is that photo's url, null on old servers / no photo: use it for a before/after toggle if you like. More outfit photos in the closet = better try-ons.
- **Sat Oct 24, ~9:30 PM: Closet sprint-3 §1 (PR `adam/closet-s3`, backend + core, all additive).** (1.1) **Your upload button must call `api.uploadClosetPhotos(photos, kind: 'outfit')`** (it already does in `closet_screen.dart`, good). Every photo with `kind: 'outfit'` goes through digitize and yields every garment; the legacy `api.uploadClosetItem` (single `file`, no `kind`) is ALSO digitized now, but it still answers with only the first piece, so don't use it for the button. (1.2, council) **Owned pieces never show a catalog photo:** `displayImageUrl` / `imageUrl` are always the user's own picture (a white-background clean shot generated from the best source photo of the piece, else the crop). `catalogImageUrl` still comes back when there is a strict match (`productId`, `brand`), for a "shop similar" link only: don't render it as the piece. (1.3) **Outfits + pieces:** `api.closetOutfits()` → `List<ClosetOutfit{id, photoUrl, createdAt, time, source: 'closet'|'fitcheck', pieceIds, pieces: List<ClosetItem>}>` newest first, pieces embedded (the Outfits view: the full photo, pieces tagged, like an Inspo post). `api.closet()` is still the Pieces view; each `ClosetItem` now has `outfitId` (null for single pieces). `api.deleteClosetOutfit(id)` removes the outfit only, pieces stay. `ClosetUploadResult.outfits` lists the outfits an upload made. Posting a Fit Check also makes an outfit (`source: 'fitcheck'`) in the background. Also new on `ClosetItem`: `cleanSourcePhotoUrl`, `cleanSourceBox`, and `WornIn.box` (where the piece sits in each worn-in photo, for pins). Server detail: `docs/schema.md` "Closet, sprint 3".
- **Sat Oct 24, ~10:30 PM: core sprint 3 (PR `adam/core-s3`, core only, all additive; unblocks PR #56).** `Api.setFitCheckLike(postId, liked: bool)` → `LikeResult{postId, liked, likeCount}` = `PUT /fitcheck/{id}/like` (idempotent; same state twice changes nothing, so coalesce / retry freely). `Api.fitCheckComments(postId, limit: 20, before:)` → `FitCheckCommentsPage{postId, commentCount, comments, nextBefore, hasMore}` = `GET /fitcheck/{id}/comments` (oldest → newest; no `before` = newest page, pass `nextBefore` for the older one, null = done; 422 for an unknown cursor). `FitCheckComment.authorName` (`author.display_name`; falls back to `userId` when the server sent no author, e.g. comments embedded in old posts); `commentFitCheck` parses `author` too. `FitCheckPost.photoWidth` / `photoHeight` (`int?`, from `photo_w` / `photo_h`, both null on older posts) and `photoAspectRatio` (`double?`, null when unknown). `Api.stores()` → `List<StoreInfo{id, name, count, departments}>` = `GET /stores` (biggest first), and it fills `StoreInfo.nameFor(id)` (static, pure, falls back to the id; `StoreInfo.knows(id)`), so `retailerName()` / `storeName()` can read `StoreInfo.nameFor` first and keep the static map as the fallback (your call; I did not touch `features/`). Tests: `app/test/core/api_inspo_stores_test.dart`. Not merged.
- **Sat Oct 24, ~6:30 PM: Closet v2 (PR `adam/closet-v2`, core + backend, all additive). The closet should feel like a real wardrobe. Adam's UI expectation, design yours:** the closet **upload button offers "a piece" / "an outfit" and takes several photos** (`api.uploadClosetPhotos(List<List<int>> photos, kind: 'piece'|'outfit', mimeTypes:)` → `ClosetUploadResult{added, merged, skipped}`; `merged` = pieces he already had that a photo matched, so show "already in your closet, added this fit to it" rather than a twin). The **closet grid shows `item.displayImageUrl`** (`item.shownImageUrl` falls back to `imageUrl` for old items) **with the `brand` label** under it when non-null. **Item detail shows the piece alone** (`displayImageUrl`, big), then on scroll the **`wornIn` photos** (`List<WornIn{photoUrl, at, source}>`: the outfit photos it was worn in, `source` `closet` or `fitcheck`). New `ClosetItem` fields: `brand, productId, catalogImageUrl, matchConfidence, displayImageUrl, cropImageUrl, wornIn`. Edit sheet: `api.updateClosetItem(id, label:, brand:, category:, color:, productId:, clearProduct: true)` (clearProduct unlinks the catalog match and the picture goes back to the clean shot / crop); "Reshoot" button: `api.reshootClosetItem(id)` (slow, image AI). `digitizeCloset` still works (now `/closet/upload` with `kind=outfit`); `uploadClosetItem` unchanged (server keeps the one-item reply for a single `file`). Posting a Fit Check adds its pieces to the poster's closet automatically in the background, so a closet refresh after posting shows them. Server detail in `docs/schema.md` "Closet v2".
- **6:10 PM: photo onboarding + multi-photo body scan (PR `adam/photo-onboarding`, all additive):**
  - `Api.onboardFromPhotos(photos, heightCm:, weightKg:, styleHint:, mimeTypes:)` → `PhotoOnboardingResult{closetAdded, skippedDuplicates, bodyProfile?, bodyPhotoUrl, styleText, styleTags, colors, formality, shopFor, user}` = `POST /onboarding/photos` (1–8 photos + height). One call: closet digitized, body scanned, style inferred, `shop_for` detected, feed warmed.
  - **What persists and when:** everything is written **immediately, no draft**. Closet items, `body_profile`, `body_photo_url` and `style_text`/`style_tags` (+ `onboarded = true`) are all saved on the user before the response returns. If the user wants to undo, they edit afterwards (below).
  - **Partial failures:** a photo with no clothing (or one whose tagging crashed) is skipped, not an error; garments already in the closet or repeated in the batch are dropped and counted in `skippedDuplicates`. If no photo is full-body, `bodyProfile` is the height/weight formula estimate (`fullBody: false`, `scanPhotos: 0`, `confidence: 'low'`, note says "add a full-body photo") and `bodyPhotoUrl` is null (previous try-on photo untouched). 422 for no files / >8 / height outside 120–230; 502 only if tagging was down for every photo.
  - **Photo retention:** every upload stays under `/static/uploads` (GPS stripped). The first full-body photo becomes the try-on photo (`user.bodyPhotoUrl`); the others remain as the closet items' source photos (`ClosetItem.imageUrl` / `worn_in`). `Api.deleteBodyPhoto()` still only removes the try-on photo.
  - **shop_for:** the body scan now also returns `presenting: men|women|unknown`. If the user never picked a department (`shop_for` unset / `"both"`) it is set from that; a department the user chose is never overridden. Shown back as `shopFor`.
  - **Review UI expectation:** after the call show `closetAdded` (count + thumbnails; items are already in the closet, so "remove" = the normal closet delete), `bodyProfile` for editing via `updateBodyProfile(...)` (typed values win over the scan), and `styleText` as an editable sentence saved via the normal `onboarding(styleText)` call. Nothing to "confirm": there is no draft.
  - **Body scan, several photos:** `Api.bodyScanMany(photos, heightCm:, weightKg:, mimeTypes:, commit:)` → `BodyScanResult` (same route `POST /users/{id}/body-scan`, 1–6 `files`; the old single-photo `bodyScan` keeps working). Every full-body photo is scanned and the estimates averaged (build by majority vote). New fields: `BodyProfile.scanPhotos` (full-body photos used) and `BodyProfile.confidence` (`low` 1 / `medium` 2 / `high` 3+), `BodyScanResult.skipped` (photos ignored because not full-body). The scan screen should let the user pick several photos ("more photos = better estimate"); `commit: false` drafting works the same way, and `confirmBodyScan` passes `scanPhotos`/`confidence` through. The same photos feed the wardrobe when sent through `/onboarding/photos` (`closetAdded`), so one picker can serve both.

- **5:45 PM: core for your 5:30 asks (PR `adam/core-sprint2`, all additive):**
  - `api.feed(seed:, seedShown: true)` sends `seed_shown=true` (only then; only meaningful with `seed`): the server leaves the seed card out of that reload.
  - `AppUser.shopFor` (`men|women|both`, `both` when absent) + `api.updateUser(shopFor:)` and `api.createUser(shopFor:)`; sent only when non-null.
  - `CartItem.imageUrl` and `UnavailableItem.imageUrl` (String?) from the flat `image_url` on every cart line: the thumbnail survives when `product` is null (left the catalog).
  - **Draft → confirm body scan (your follow-up #1), true uncommitted draft:** `api.bodyScan(bytes, heightCm:, weightKg:, commit: false)` → `POST /users/{id}/body-scan?commit=false`: the scan runs and the photo file is kept for the AI, but **nothing on the user changes** (no `body_photo_url`, no `body_profile`); result is the same `BodyScanResult` with `committed: false` (default `commit: true` = today's behavior, `committed: true`). Review screen shows `draft.profile` (cm height, kg weight, inches chest/waist/hip/inseam, US shoe). Save = `api.confirmBodyScan(draft, waistIn: 33, fit: 'slim', …)` with **only the fields the user changed** → `POST /users/{id}/body-scan/confirm` `{body_photo_url, profile (draft + edits), edited: [field names]}`: sets the body/try-on photo, saves the profile; `edited` fields are stored as typed (`BodyProfile.manual`, they win over later scans, `source: manual`), the rest merge like a scan (measurements typed earlier still win over them, exactly as the draft already showed). Returns `{bodyPhotoUrl, profile, committed: true}`. Cancel = call nothing (the draft photo is just an orphan upload). 422 for an impossible number, an unknown `build`/`fit`, or a `body_photo_url` that isn't one of this server's `/static/uploads/` files.
- **5:15 PM: full handoff in `docs/handoff-ryan-ios.md`:** how to run the iOS app already connected (`flutter run --release` with `--dart-define=DTI_API_BASE / DTI_API_KEY`; Adam DMs the values), every live route and its core method, the four PRs coming from Adam's lane, and Adam's asks for your screens. Start there.
- **4:35 PM: your #33 is merged and on Adam's Pixel; two asks from Adam for your screens, plus new core.**
  - **Adam's asks (design is yours, these are his words):** (1) height / weight / measurements as **scroll pickers** instead of typed fields; (2) **US units** (ft/in, lb) with the cm/kg conversion done in the app (`BodyProfile` stays metric/inches on the server). (3) First-run onboarding still says "Connect to use a private body scan" when the key isn't entered yet: consider letting the first-run flow open Connection settings inline, since Adam hit that twice.
  - **New core since #30:** `api.createFits({count, occasion, mustInclude, budgetUsd, tryOn})` → `List<OutfitFit>` (AI Fit Creator: full outfits for the body scan mixing closet + new in-size pieces), `api.fit(id)`, `api.fitTryOn(id)`, `api.addFitToCart(id)`; models `OutfitFit{id, name, occasion, reason, pieces: [FitPiece{slot, source, closetItem?, product?, yourSize, inYourSize}], newTotalUsd, closetCount, tryOnUrl?}`. A "Fits for you" screen is yours when you have time; occasion chips ("class", "date", "rooftop party") map to `occasion`.
  - **PR #36 (core + `pick_photo.dart`):** photos are shrunk to 1600 px on the phone before upload and uploads get 180 s; a Pixel photo was timing out at 60 s. Only `pickPhotoFrom` changed in your file.
  - **Coming:** `POST /onboarding/photos` (drop several photos → closet digitized, body scanned, style inferred, `shop_for` detected) as `api.onboardFromPhotos(...)`, and measurement-based sizing (no API change; `your_size` just gets better).
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
