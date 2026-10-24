# Ryan council sprint ready for review — Oct 24, 4 PM PT

Published `43e9352` on `RyanFrontendking`. [PR #33](https://github.com/latrael/dresstoimpress/pull/33) targets staging, is open/mergeable, and was NOT merged. Local and remote Ryan trees match with a clean working tree. Integrated staging through 54063b6; checked Adam's 15:45 and Nabil's 17:15 contract notes. This section supersedes the earlier in-progress/request sections below.

## Delivered

- Persistent Liked → Cart → Closet → User header on all routes, floating Home/Discover/Inspo island; Home is the continuous solid-separated product list.
- Login for this device's returning profile, New account through createUser, explicit team test profile. Google later, per Ryan.
- Seven separate skippable setup screens: Welcome, Style, Stores, Scan, editable Measurements, Budget, Done. H&M/Uniqlo + optional other-store interests; server style/stores/budgets/onboarded and body-profile sizes/fit; private photo preview/delete; all editable under User.
- Shared seeded Home from catalog tags/results/Liked, clear seed chip, size badges with explicit alternatives when real size is unavailable; no default body values or passive swipe writes.
- Discover dedicated search/searchPhoto/searchStyles, camera/gallery, style counts, engagement/personal mix, Similar/Goes with it. Closet matches are labeled and never cartable or seeded.
- Inspo shared feed, author filtering, photo-toggle catalog metadata/label tags, seed/search tap, confirmed own-post delete. Both closet upload choices.
- Full wishlist screen; atomic cart pencil, visible/removable unavailable lines blocking checkout, thumbnails; retained your receipt/per-store retry and added order-history retry.

## Integration / evidence

Uses your canonical council methods/models. The only core extension is `sizeAdvice(useSavedProfile: true)`: unspecified dimensions are omitted rather than sending Settings' old 170/65 defaults. Typed dimensions win over scan prefill. Atomic cart fallback is restricted to missing-route 405 or generic 404 “Not Found”; missing-cart-line 404 never creates a line.

**81 Flutter tests pass**, analysis clean, release web build succeeds. New tests cover council navigation, full wishlist, text/photo search/owned items, seed/reset, scan review, absent measurements, atomic failure and unavailable lines, plus reconnect recovery. Live read-only health/feed/styles and actual browser Home/Discover/images/catalog→Home verified. Final signed iPhone release built and installed successfully. iOS blocked its launch because the device is locked; Ryan must unlock and open Niche. Earlier checkpoint launched successfully through devicectl. Private key/URL remain outside Git. No live personal-photo upload/post or payment performed by agent.

## Explicit follow-ups

1. The current body-scan route persists estimates/photo before client review. UI exposes review/edit/save; a true uncommitted draft→confirm route needs backend work. Please do not describe it as deferred server persistence.
2. Positional tag pins remain stretch; permitted photo-toggle list overlay is implemented. Google auth remains deferred.
3. Nabil's additive shop_for, seed_shown and cart-line image_url are documented next client extensions; Ryan has not chosen a gender-preference UI. Current seeded Home fetches once per selection (retry starts a new fetch).
4. Human acceptance: physical scrolling/keyboard, real scan quality/camera and checkout demo. Implementation checklist: docs/ryan-council-implementation.md.

---

# Ryan council sprint started — Oct 24

Read docs/council-final-sprint.md and latest Adam/Nabil handoffs. RyanFrontendking fast-forwarded to staging 4516746, including PR #22's body scan/profile methods. Implementing Ryan's full P0/P1 app list; 5 PM is optional per Ryan. No PR merges by this agent.

## Ryan's confirmed decisions

- Scan BEFORE measurement review. Keep the scan photo private for try-on.
- Entry choices: Login (returning saved profile on this device), New account, and explicit team test profile. Google auth later; no fake password login or arbitrary-ID impersonation.
- Stores: H&M + Uniqlo chips plus optional other-store interests, clearly not extra catalogs.
- Inspo tags: matched catalog name/store/price when actual match exists; unmatched garment label opens similarity search.
- Trending mixes global engagement and personal recommendations.
- Closet offers BOTH single-garment upload and multi-garment digitizing (existing API).

## Needed shared contracts

Please coordinate with Nabil and publish core methods/models for the council's GET /search (similar/goes_with), POST /search/photo, /search/styles + mixed trending, /feed seed + your_size/in_your_size, public Inspo author filtering, and atomic cart size PATCH. Current core on staging lacks these. Need preferred_stores / onboarded / usual_sizes profile fields when they land, including clear PATCH semantics and blank/skipped budget clearing. Existing updateBodyProfile will be used now. Do not infer photo measurement confidence from nonexistent fields; current BodyScanResult has source/fullBody/note.

## In progress

Floating island Home/Discover/Inspo shell, persistent Liked/Cart/Closet/User header, dedicated Liked using Api.wishlist (all saved products), continuous Home, shared seeded landing, split onboarding and private scan review, both closet inputs, tag overlay, grouped User sections. The fallback Discover adapter currently composes existing keyword search + complete-look while dedicated endpoints are pending; no private photo upload through social/body routes for search. A new sprint PR will target staging after validation; original PR #18 is already included in the updated staging ancestry.

---

# Ryan → Adam: latest app onboarding + automatic sizing — Oct 24

Published `12a8a9d` on `RyanFrontendking`; [PR #18](https://github.com/latrael/dresstoimpress/pull/18) updated into staging, remains unmerged. Ryan now wants a SOLID separator (48px muted burgundy plus spacing) in the continuous lazy product list. Earlier arrow/boundary/faded requests below are superseded.

## Current app behavior

- New local user IDs first land on Welcome to Niche. Start with optional plain-English looks/clothing/stores, preferred slim/regular/oversized fit, actual measurements, or a usual alphabetic size. Price maximums for tops/bottoms/jackets/shoes are optional, individually blank/skippable; entire onboarding can be skipped. Completion and measurements persist locally per configured user ID; this is not auth or cross-device sync.
- Manual dimensions: height, waist, chest, hips, inseam in cm; weight kg; US shoe size. No default body measurements are silently accepted. Photo-based body measurement is NOT implemented or claimed.
- Existing Api.onboarding handles live style/price text; local measurement-only onboarding needs no style request. Demo saves locally. Profile preferences and the missing-size path allow editing later.
- Quick Browse automatically calls Api.sizeAdvice on nearby items once per product/profile revision using explicit height+weight, preferred fit, waist converted cm/2.54 and shoe US. Only returned in-stock sizes can be selected. An explicit usual letter size may match an available size exactly; demo uses this fallback, not a made-up dimension estimator. Missing/unsupported size results never choose an arbitrary first size. Single Add to Cart + quiet chosen-size text replaces the size chips and manual size-advice sheet in the app flow.
- Cart pencil offers real sizes, unavailable disabled, preserving quantities and merging an existing matching line. Demo is local. Live replacement uses existing add-new then remove-old routes. Failure refreshes the cart and clearly asks review; it cannot claim an atomic replacement.

## Backend/core requests to coordinate

1. Please provide server-side measurement/profile persistence + get/update contracts for cross-device onboarding. Chest/hips/inseam currently stay local because /size accepts only height/weight/fit/waist/shoe. Also clarify whether per-category usual-size fallbacks can be stored.
2. Please define a real body-scan → measurement capability if implementing it. Current body-photo upload/try-on is not a sizing scan; no dimensions are inferred from it.
3. Coordinate with Nabil on an atomic cart size-change endpoint preserving quantity and merging target lines safely. Existing two-step route composition can leave both lines after a partial failure, which the UI explicitly reports and refreshes.
4. Optional category price maximums are sent as plain text via current onboarding parser. Confirm canonical category recognition; no new payload fields or unsupported dimensions were invented.

## Verification

Flutter analysis clean; all 45 tests pass (first visit/skip/return, actual dimensions without prices, per-user persistence, cache+waist conversion, no default-body guessing, unavailable advice, cart pencil/quantity and failed live replacement, continuous scrolling and carousel boundaries). Signed release updated and launched on Ryan's iPhone. Browser first-visit layout visually checked. Native keyboard/photo/gesture feel and real-user size quality still require acceptance. Private tunnel/key and Apple signing configuration remain outside Git. Shared core/backend files unchanged. Details: frontend/ONBOARDING.md.

---

# Ryan update: continuous scroll replaces boundary gestures — Oct 24

Ryan reported the swipe-up gate required a reversal and requested continuous scrolling. Published `b161553` on `RyanFrontendking`; [PR #18](https://github.com/latrael/dresstoimpress/pull/18) updated into staging, unmerged. All prior boundary/arrow instructions below are superseded. One lazy vertical list contains full product details, separated by a 48px faded burgundy band plus 12px spacing above/below. Prepare roughly one screen ahead/behind; distant widgets/images build on approach. No nested vertical scroll, page snapping, thresholds, timers or gesture confirmation. Each nearby item keeps independent size/photo state. Horizontal gallery behavior, backend/core and passive-browsing API behavior unchanged.

Checked latest Adam/Nabil handoffs on staging. Flutter analysis clean; 36 tests pass (five continuous-scroll regressions replace seven obsolete paging checks). Actual browser sample-mode preview verified natural scrolling and visible separators. Updated signed release installed and launched on Ryan's iPhone; physical scroll feel is for his acceptance. No private credentials or personal signing configuration committed. Phone connection settings remain device-local.

---

# Ryan update: bottom-gated browsing, arrow removed — Oct 24

Ryan scrapped the up-arrow idea. Published `faaec28` on `RyanFrontendking`; [PR #18](https://github.com/latrael/dresstoimpress/pull/18) is updated, targets staging, and remains unmerged. Read the latest staging Adam/Nabil handoffs before changing the UI. A product must reach the bottom before a fresh upward gesture advances; no arrow/progress overlay. Keep the existing small-motion and momentum protections, one product per gesture, and horizontal photos confined to the carousel. Previous-product navigation remains gated at the top.

Flutter analysis clean, all 38 tests pass, including the replacement no-overlay regression. Updated release build installed and launched on Ryan's connected iPhone. Native scrolling feel still needs Ryan's review. Xcode signing is configured locally with his Personal Team. Cloud-folder Finder metadata broke signing in the repo folder; an identical temporary local app copy was used for the build. No signing identity or private connection data committed. Latest private backend health/feed verified separately (200, five items); phone build keeps device-local connection settings.

---

# Ryan update: deliberate product scrolling + up-arrow cue

Published on `RyanFrontendking` at `b45ebac`, [PR #18](https://github.com/latrael/dresstoimpress/pull/18) into staging; unmerged. Ryan requested a cue after scrolling to the bottom of the current product. Details now reach the edge first; a fresh overscroll reveals the up-arrow/progress indicator before advancing. Touch confirms on release; wheel/trackpad after the gesture settles. Small movements cancel and momentum cannot skip several products. Horizontal photo gestures remain scoped to photos. The previous item uses the top edge.

Flutter analyze clean; 38 tests pass (seven new scroll/cue regressions). Actual web demo verified bottom → small scroll/cue without paging → armed cue → next product. Native iPhone feel still needs verification. Xcode download is complete per Ryan; no signing/setup changes were performed for this web fix. Branch was brought up to merged staging first; backend/core unchanged.

---

# Ryan morning report — Sat Oct 24, 10:27 AM PT

Plan confirmed. Implementation is published on `RyanFrontendking` at `e83259b`; PR [#16](https://github.com/latrael/dresstoimpress/pull/16) targets `staging` and is **not merged**. This report is posted after the requested 8:30 deadline; it is not backdated. Final edge-case checks and documentation are complete; shared live and phone acceptance remain pending.

## Done, in Ryan’s checklist order

1. **Size advice + product details:** measurement/fit form, optional waist and shoe size, confidence/reason, available-size selection only. Retailer descriptions/colors preserved; no invented model stats. Separate Add to Cart.
2. **Try-on:** generated personal slide stays within the photo carousel; returned collage is explicitly labeled Outfit board, not a photo of the user. User-driven body-photo selection/upload; cancel skips upload.
3. **Complete the look + Fit Score:** separates owned closet pieces from catalog suggestions, exposes missing categories and new-items total; score submits catalog and closet IDs separately.
4. **Onboarding + search:** free text saves parsed style/budgets and refreshes suggestions. Search uses `searchProducts` with paging, keeps earlier results on a failed next page, ignores late responses from older queries.
5. **Fit Check:** photo/caption upload, like, comment, edit existing labels, shop and score. Errors do not optimistically claim success. No guest-page activation.
6. **Closet:** user-selected upload with real MIME, possible-duplicate notice (both saved), list refresh and confirmed removal.
7. **Profile / Style DNA:** user/profile, style shares, palette, patterns, formality, retailers, learned budgets/apply with explicit 409 handling. Onboarding and Closet reachable without changing the three-tab navigation.

## Evidence and limits

- Final checkpoint `e83259b` is published and local/remote Ryan branches match with a clean working tree. Latest staging handoffs are included.
- Baseline 14 tests passed; current expanded suite **31/31**. Flutter analysis clean; release web build succeeds. No edits to `app/lib/core` or backend implementation.
- Isolated local backend, mock AI and synthetic fixture only: actual shared Dart client verified all 418 catalog products (417 currently in stock), H&M top and waist/length-jean size recommendations, three mock outfit-board image loads, onboarding budgets, complete-look/score, Fit Check create/like/comment/shop, Closet upload/delete, Style DNA.
- Actual browser: phone-size Home and Quick Browse retain the wireframe layout; size recommendation selects an available chip; generated gallery slide is bounded and honestly labeled. Phone-size (390x844) Home, Quick Browse and scrollable product tools were visually reviewed.
- **Shared live acceptance is not signed off.** Earlier tunnel outage prevented it; latest staging now says the backend is back at a new URL shared privately. That new URL has not been supplied to this session. Device preview currently uses an isolated local test server. No live checkout, paid AI generation, or real personal-photo upload performed.
- iPhone/Xcode, real photo quality, and final visual approval remain human checks. Xcode download is independent of this work.

## Morning decisions / follow-up

- Ryan: review PR #16; humans merge or hold it. Agent will not merge.
- Ryan: decide on PR #13’s iOS permission wording/icon and Nabil’s `/fit` guest page. Neither was approved or activated.
- Adam: privately provide the refreshed backend connection; repeat shared live acceptance and phone run after review. Backend/core ownership stays with Adam/Nabil.
- Follow/unfollow and arbitrary new tag fields are not implemented; the current core exposes no follow action. Existing outfit labels can be corrected/removed.
- Posting/removing real personal photos was skipped. Upload UI is implemented, while overnight checks used only synthetic local fixtures.

---

# Plan confirmed — Ryan overnight work

Ryan’s agent is running the staging docs/plan-sat/ryan.md list in order. Implementation stays on RyanFrontendking; PRs target staging and will not be merged by the agent. Human decisions, personal photos and iPhone work are deferred to the morning report, which will be prepended here by 8:30 AM PT. The documented tunnel outage blocks shared live checks; local checks continue. No private connection information will be committed.

# Ryan → Adam: shared Flutter integration and live verification

Updated October 23, 2026 (Pacific). Implementation stays on `RyanFrontendking`; handoffs stay on staging.

## Current plan acknowledged

Ryan owns every app screen and all design. Adam maintains AI/hosting and core; Nabil commerce. Read all distinct Markdown versions across staging (5c320be), Adam (e27baa9), Nabil (now e2ea844), flutter-starter (1b4aff2) and Ryan. Rechecked both PDF pages and retained the Quick Browse mock-up Ryan approved.

## Implemented and verified

Merged staging + flutter-starter into RyanFrontendking. Only conflict was the old added NABIL_TO_RYAN.md; kept staging's newer version. No backend/core edits.

Actual `app/` now runs: Home suggested grid -> selected Quick Browse, persistent loaded-suggestion search, typed-model Feed adapter, wishlist PUT/DELETE, cart add/remove, retailer groups/totals, explicit Nessie-sandbox checkout UI, receipt status distinctions and order history. Initial Social feed + shop entry also wired. Demo mode remains separate/local and never claims a payment.

Ryan provided the private connection details directly; they are in device-local settings only, not this document, source or Git. Live health 200/ok; feed limit=5 returned 5 products; image proxy 200 JPEG. Actual browser loaded live catalog and photos. Verified photo swipe/dot updates, description drag staying outside the carousel, vertical paging to a single-photo product with real description and unavailable sizes, save/unsave, size-M add -> correct H&M cart -> removal. Test cart and wishlist membership restored. **No live checkout executed.**

`flutter analyze` clean; 8 tests pass. Original 4 plus shared-API Home/Feed/save/cart route check (no /swipe), checkout 409 retaining cart, partial account read failure blocking writes, proxy query encoding. Return-to-previous-product test now also verifies photo/size reset. Desktop mouse dragging explicitly enabled after browser check found Flutter's default ignored it.

## Concrete core requests

At published starter 1b4aff2, `Api.imageUrl` only resolves relative static paths; it does not proxy retailer images despite README claims. StoreController currently wraps the already documented `/img?url=` route without changing core. Please add a core proxy helper when convenient.

The published core lacks Nabil's newer product search/paging, onboarding/users methods and Style DNA apply. pubspec also lacks image_picker (currently only http/shared_preferences). Please bring core up to those contracts; the app currently filters loaded suggestions and does not pretend that is full-catalog/natural-language search.

## Remaining

Sizing assistance, personal try-on slide (collage = Outfit board), complete-look/Fit Score, full product detail, onboarding, complete Social, Closet/Profile and phone verification. iPhone still on your Mac. Public /fit guest page remains off pending Ryan's explicit review; no approval inferred.

Frontend status and accepted design spec updated in RYAN.md / frontend/QUICK_BROWSE.md. Implementation PR targets staging only.
