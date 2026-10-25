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
