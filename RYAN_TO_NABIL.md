# Sprint 4 published: PR #71 ready for review — October 25

[PR #71](https://github.com/latrael/dresstoimpress/pull/71) is OPEN into staging, ready for review; RyanFrontendking 98aa5f2. Your #68 reels fields/routes and Adam’s #66/#69 core are wired. No commerce/core/backend edits in this app increment. First3/next3 prefetch, visible pending status polling and background pause; hero image, real closet IDs/photos, no-photo and honest outfit-board modes. Existing search/seed/cart/like/comment routes stay shared-client based.

Delivered the new type system, glass shell/swipe tabs, one-product-per-screen Home and bounded 3-slide carousel, arch/mosaic onboarding, full-width natural-ratio Discover and shared visual restyle. Ryan chose double-tap-only Home likes, cream glass nav, full-width Discover. Deep-merlot glass is a documented alternate; sign-in held. 185 tests, clean analysis, web/native simulator builds pass. Actual iPhone16/iOS27 simulator review confirmed no black band and that Add to cart clears the nav; capture and full checklist are in docs/sprint-4/after-home-iphone16-simulator.png and docs/ryan-sprint-4-implementation.md.

Please handle the Pixel9Pro hardware screenshot/edge-back/haptic pass and physical-device acceptance; the included after capture is explicitly SIMULATOR. Also review real photo-owning-account ready/AI/collage and preloaded post2+ behavior; no paid render or personal upload was performed by this agent. PR is published for the team now, not held for those checks. No merge performed.

---

# READY: paged comments shipped in merged PR #56 — October 24

PR #56 is merged into staging at 343d6b5, activated on Adam’s #58 core. The app now fetches newest and older comments with the real GET helper, before cursor and total count, with authorName. **You may now trim feed/detail to the two newest comments + comment_count.** This is the explicit ready signal, superseding older NOT ready notes below. Idempotent PUT likes and photo dimensions are active too. 167 tests passed at merge; live browser opened the paged sheet successfully. Single Comments entry, composer only inside it; no live comments or likes written by the agent.

Follow-up [PR #63](https://github.com/latrael/dresstoimpress/pull/63) is open into staging for gentler Fit Score, closet-first actual images with labeled catalog gaps, and try-on source comparison. No commerce/core changes. 170 Flutter tests + 89 selected backend tests pass, analysis/web/iOS builds succeed. Adam has the backend calibration/deployment note. Sign-in remains held.

---

# Inspo paging activated — ready for two-comment previews

PR #56 now uses Adam’s merged shared-client helpers in production: explicit PUT likes, GET comments pages (20 with before cursor), author display names and authoritative photo sizes. Route-level mock transport plus UI/concurrency checks pass. Once #56 is merged, the app is ready for feed/detail to return only the two newest comments plus comment_count. This supersedes the older NOT ready notes below. One Comments entry opens the sheet; Add a comment appears only inside it. No live social writes.

---

# Nabil Inspo handoff: UI ready to integrate, NOT ready for payload trim — Oct 24

Draft [PR #56](https://github.com/latrael/dresstoimpress/pull/56), `fceeea4`, contains tested instant-like queue/rollback, paged comment UI with names/dedup/retry/scroll anchoring, accurate totals and metadata sizing. 139 tests/analysis/web release pass. But Adam's current Api/model still lacks PUT-like, GET-page, author and photo-dimension accessors, so production callbacks remain unwired and the old safe runtime path remains.

**Keep full comments in feed/detail for now.** This is not the ready-to-trim signal. I requested the exact client additions from Adam in RYAN_TO_ADAM.md; once wired and route-tested, I will post the explicit ready signal here. No live writes or duplicate HTTP adapter; shared-client ownership respected. Dynamic stores client also remains pending.

---

# Ryan acting on your 7:50 Inspo handoff — Oct 24

Read and synced PR #55. Preparing optimistic explicit-state likes, paged comment sheet and authoritative photo dimensions. Adam's core currently lacks all three client additions, requested in RYAN_TO_ADAM.md; preserving shared-client ownership. **Do not trim feed/detail comments to two yet.** I'll write an explicit ready note here when the app actually loads GET comments pages and has been validated. Existing comment sheet remains usable from the current full payload meanwhile. No automatic retries on toggle POST.

---

# Ryan Sprint 3 UI ready — Oct 24

[PR #54](https://github.com/latrael/dresstoimpress/pull/54), `46b8fb7`, into staging, unmerged. Closet garment-detection uploads, own-photo-only Pieces and derived worn-photo Outfits views, natural-ratio Inspo with 9:16 portrait cap, roomier actions and keyboard-safe comments sheet are implemented. Sign-in on hold per Ryan. 130 tests/analysis/release builds pass; updated iPhone build installed/launched.

Still need your routes coordinated into Adam's core: explicit idempotent PUT-like, paged comments with names/cursor and post photo_w/photo_h. Confirmed-only toggle is kept until explicit-set client exists; no automatic POST retries. Sheet uses current feed comments until paging exists. GET /stores client is also still absent; eight-store fallback remains. No seed posts or database rebuild from this agent. Full checklist: docs/ryan-sprint-3-implementation.md.

---

# Ryan Sprint 3 UI underway — Oct 24

Implementing Home text cleanup, proper photo ratios capped at 9:16, spacious actions and a keyboard-safe comment sheet, plus garment-detecting closet uploads and honest owned photos. Please coordinate Adam core for GET /stores, PUT like (explicit liked state), paged comments with names/cursor and post photo_w/photo_h. Until the client lands, no duplicate HTTP adapter and no automatic retries on toggle POST. Closet outfit grouping needs Adam's endpoint/model. Council says Inspo starts empty; no seed posts will be made by this agent. Login last; method asked of Ryan. No database rebuild actions from this agent.

---

# Ryan: eight-store app integration — Oct 24

[PR #50](https://github.com/latrael/dresstoimpress/pull/50), `08b1625`, is open into staging and unmerged. The app now recognizes all eight published store IDs, preserves their preferences as retailer IDs (not custom-interest text), and uses readable names in cart/Fits/Home fallback labels. Cart rows use flat imageUrl when the product disappeared. Shop-for has its own optional screen, and seeded reload sends seedShown=true with reset/new-tap handling. No direct backend/core edits.

Live stores endpoint returned eight after Adam reconnected; health 200. Api.stores() is still absent, requested from Adam, so current chips/names use a shared eight-store fallback. Dynamic counts/department filtering are not claimed. 112 Flutter tests and analysis pass; release builds pass. Details in docs/ryan-sprint-2-integration.md and latest RYAN_TO_ADAM.md.

---

# Ryan council app integration — Oct 24, 4 PM PT

[PR #33](https://github.com/latrael/dresstoimpress/pull/33), `43e9352`, is open into staging and not merged. Ryan branch includes staging through 54063b6. Uses Adam's canonical council client: seeded feed + soft-size fields, search/photo/styles, public Inspo author feed, preferredStores/onboarded, atomic size PATCH and unavailable cart lines. 81 Flutter tests pass, analysis/release web build pass; live read-only feed/styles and browser catalog→seeded Home verified.

Your budget-clearing contract is applied: omitted categories removed by sending an explicit price_ranges map; {} clears all. Cart fallback only for a missing route (405 / generic Not Found), never a missing line. Unavailable lines stay visible/removable, block checkout, and don't enter payable totals. Trending is explicitly interleaved with personal suggestions per Ryan's answer; owned Goes with it pieces open Closet, never cart or seed.

Read your round-two contract: shop_for, seed_shown, cart-line image_url are additive client follow-ups, not silently guessed UI. Current seeded Home fetches once per product selection; retry refetches the seed. No gender preference inferred. Photo-search requests create no Inspo/body-photo record. Shared credentials remain private. See docs/ryan-council-implementation.md and RYAN_TO_ADAM.md for full scope and body-scan persistence caveat.

---

# RYAN_TO_NABIL.md

Updated October 23, 2026 (Pacific). Handoffs on staging; implementation on `RyanFrontendking`.

## Ownership and latest review

Ryan owns all app screens and all design. Adam is AI/backend hosting + core; Nabil is commerce backend. The old split-screen assignment is withdrawn. Read all distinct Markdown versions across staging, Adam, Nabil, flutter-starter and Ryan. Latest Nabil reread at e2ea844 includes the data-only reference and /fit approval request.

## App progress

Merged staging and shared Flutter starter into Ryan's branch, retaining his accepted Quick Browse layout and using both original PDF pages as references. Home grid, persistent search over loaded suggestions, live Feed + wishlist adapter, cart add/remove/grouped totals, explicit sandbox checkout UI, receipts/status handling and order history implemented. Initial Social feed/shop entry wired, with full Social still pending. No backend/core files edited.

Eight Flutter tests pass and analyze is clean. Tests cover original gestures plus shared API integration/no browsing /swipe, checkout 409/cart retention, partial account read failure and image proxy URL preservation. Desktop mouse dragging also verified in the actual browser. Switching products resets photo/size, including returning to a prior product.

## Live checks passed

Ryan supplied the private connection details directly; entered in device-local settings only. No values in source, Git or this handoff.

- Health 200/ok, authenticated feed limit=5 returned five cards with gallery/size arrays, image proxy returned JPEG.
- Actual app loads live photos, descriptions/fallbacks, product sizes and pairing reasons.
- Saved a real feed product, selected size M, added it, saw the correct H&M group and total in cart, removed it, then unsaved it. Original cart/wishlist membership restored. Saving and browsing did not dismiss the product.
- **No live checkout submitted.** The checkout UI is implemented and the stock-change 409 path is tested with controlled API responses. Phone checkout remains a team checkpoint.

The original five gallery/description/wishlist requests remain acknowledged as complete. No schema change requested.

## Outstanding commerce/core coordination

Your newer product search/paging and users/onboarding routes are not yet methods in the published shared Dart core. Asked Adam to add them; current search filters loaded suggestions and does not claim full-catalog or natural-language matching.

Api.imageUrl in starter 1b4aff2 resolves /static but does not proxy retailer images. Current app wraps the documented /img route; asked Adam for the intended core helper. No new transport was introduced.

Checkout receipts distinguish paid / nessie_failed / pending_nessie. There is no documented per-purchase retry endpoint, so the app doesn't silently repeat a successful store payment when another failed. Please document a safe retry contract if that is needed.

## /fit decision status

Your public guest page proposal was read. **Ryan has not explicitly approved enabling it.** Keep it off until his visual review/decision; this handoff does not give that approval. Continue backend work independently.

## Remaining Ryan work

Size assistance, personal try-on slide (collage labeled Outfit board), complete-look/Fit Score, full product details, onboarding, full Fit Check/Closet/Profile, and iPhone/live-checkout verification. User explicitly allows Xcode to come later on his machine.

Implementation PRs go to staging only. Private connection details and service credentials must never enter public docs or Git.
