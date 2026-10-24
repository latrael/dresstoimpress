# Ryan: Flutter app status

Updated October 24, 2026 (Pacific). Branch: `RyanFrontendking`.

## Ownership and references

Ryan owns every app screen and all design. Adam maintains AI/backend hosting and
`app/lib/core`; Nabil maintains commerce. Plain Flutter supersedes FlutterFlow.
Reference: both pages of `WireframeSketch.pdf`, Ryan's accepted Quick Browse,
and `frontend/QUICK_BROWSE.md`. Preserve ivory/burgundy, the bounded photo
carousel/dots/price, details/sizes/cart, Home grid and persistent search, and the
Home / Discover / Social navigation. Never invent descriptions or model stats.

## Overnight implementation (PR #16 into staging; not merged)

Worked `docs/plan-sat/ryan.md` in order:
1. Size advice: positive measurement inputs, optional waist/US shoes, backend fit
   values slim/regular/oversized, confidence/reason, available-size selection.
   Product descriptions/colors stay outside the horizontal gallery. Cart is explicit.
2. Personal try-on: user-driven body photo if needed, generated slide only in that
   product's local gallery; collage labeled Outfit board, not a photo of the user.
3. Complete the look: owned/catalog distinction, missing slots/new-items total,
   catalog detail entry, Fit Score with separate product and closet IDs.
4. Onboarding: free text saved through core, parsed styles/budgets shown, feed
   refreshed. Full catalog search/paging replaces loaded-feed-only search when
   connected; stale results ignored, failed next pages retain earlier results.
5. Fit Check: selected photo/caption upload, likes, comments, existing-label editing,
   shop and score; failed comments retain their draft. No public guest-page changes.
6. Closet: selected image upload, real MIME, duplicate notice with both items retained,
   list refresh, explicit confirmed removal.
7. Profile: user and Style DNA, palette/styles/patterns/formality/retailers/budgets,
   apply with 409 handling, onboarding/Closet/photo access within existing navigation.

Previous Feed/wishlist/cart/checkout/receipt/order behavior is preserved. Browsing
never calls `/swipe`. The shared core remains the only API transport. The feature
image adapter now uses core's `imageProxyUrl` from PR #11. No backend/core edits.

## Verification and remaining acceptance

Flutter 3.47.6 / Dart 3.13.5: analyze clean, 31 tests pass, release web build succeeds.
Regression checks include gallery boundaries/reset, sizes/cart errors, account-read
failure, query races/paging, three independent generated galleries, cancel/upload
MIME, Fit Check actions/drafts/tags and Style DNA 409.

Isolated backend with mock AI and synthetic images: actual shared Dart client
verified health, all 418 catalog products (417 in stock), H&M top + waist/length
jeans size suggestions, three mock outfit-board image loads, onboarding budgets,
complete-look/score, Fit Check create/like/comment/shop, Closet upload/delete and
Style DNA. These are LOCAL checks, not shared-live or real AI quality acceptance.
Browser review at 390x844 verified Home/Quick Browse, scrollable details and tools,
available-size selection and the generated-slide label. No Xcode required.

Shared live acceptance is pending: the tunnel changed and its new address has not
been provided to this session. Connection details belong only in device settings,
never Git/docs/screenshots. Preview currently uses an isolated local test server.
No live checkout, paid AI generation or personal-photo upload was done overnight.

## Human decisions and morning checks

- Review PR #16; humans merge or hold. Agent does not merge.
- Ryan decides PR #13 iOS icon/permission wording and Nabil's `/fit` guest page.
- Privately update backend connection; repeat shared acceptance for all seven rows.
- Supply personal/real outfit/closet photos; verify actual AI quality and phone
  picker/keyboard/layout/checkout on Adam's iPhone. Xcode download can continue.
- UI remains subject to Ryan's review; existing labels may be corrected/removed,
  but arbitrary new tag fields and follow/unfollow are not implemented.

Read/write directional handoffs on staging. The morning report is at the top of
`RYAN_TO_ADAM.md`; it records the late posting time candidly. PRs target staging,
never main. No private connection information belongs in the repository.
