# Ryan Sprint 3: first UI increment

Source: docs/sprint-3.md including council decisions. Ryan explicitly put sign-in
on hold in chat; existing team accounts stay. No database rebuild or account reset
is performed by this agent. Code stays on RyanFrontendking, PRs into staging only.

## Implemented

- Home no longer appends “edit in cart” to the size label.
- Closet Add to closet offers A piece / An outfit, camera or multi-photo gallery
  (up to eight photos, resized with existing image limits). Both choices call
  Api.uploadClosetPhotos(kind: outfit), deliberately routing every photo through
  multi-garment detection. The previous one-item upload is gone from this screen.
  Added / merged / skipped results are distinguished; matched existing pieces gain
  photos instead of being described as new duplicates.
- Closet has Pieces and Outfits views. Outfits currently groups actual wornIn photos
  with their linked pieces; it does not invent persistent outfit IDs. An authoritative
  outfit collection/group API is still pending from Adam.
- Owned grid/detail photos accept the user's static crop/clean shot and reject
  catalog URLs and retailer image hosts. If no owned photo exists, a placeholder is
  shown. Brand is displayed when supplied. Detail shows worn-in photos and supports
  editing label/brand/category/color, removing a catalog match, and explicit reshoot.
- Inspo photos use resolved natural dimensions: wide photos show whole, portraits
  taller than 9:16 are center-cropped to that cap. Images use cover at the resolved
  aspect, with no added bars/stretch. Photo metadata from the future core model can
  eliminate the initial square loading placeholder.
- Post actions have separate space before comments/the next post. Like requests
  have their own busy state, so shopping a fit does not disable liking.
- Comments open a keyboard-safe bottom sheet. Existing comments sort chronologically
  (newest at bottom), the compact input stays pinned above the keyboard, drafts remain
  on send error, and successful sends update the parent even if the sheet closes.
- Empty Inspo stays empty; no seeded posts or live test uploads are created.

## Waiting for team contracts

App/lib/core remains unchanged, as requested by Ryan and the iOS handoff.
- GET /stores method/model: current eight-store names are already supported by the
  shared UI fallback; live counts/department filtering still await the client.
- Authoritative closet outfits/outfit_id API/model; current grouped worn-in photos
  are useful but are not a substitute for server upload-group identity.
- Idempotent explicit PUT-like method before optimistic heart/count updates. Current
  POST toggle is sent once, serialized per post, with no automatic retry. Confirmed
  like behavior remains until the idempotent client arrives.
- Paged comment client/model with author names/cursor and post photo_w/photo_h.
  The sheet currently uses real comments in the existing feed response, not invented
  pagination or a duplicate HTTP transport.
- Sign-in is on hold per Ryan, not awaiting a guessed authentication implementation.

Requests are posted to RYAN_TO_ADAM.md and RYAN_TO_NABIL.md on staging.

## Validation

130 Flutter tests pass; Flutter analysis clean. Release web and signed iOS builds
succeed. Seven new checks cover natural ratios/cap, owned-photo rejection, both
upload choices using multi-garment detection with multiple photos, canceled picking,
linked outfit navigation, and ordered comments with keyboard-safe input. Existing
upload, tag edit, like/comment and browsing regressions are retained.

No live personal-photo upload, social post, paid reshoot/try-on, checkout, or database
write/reset was performed by the agent. Private connection values stay outside Git.
Phone installation and live visual acceptance are recorded in the staging handoff.
