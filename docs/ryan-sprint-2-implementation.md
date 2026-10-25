# Ryan Sprint 2 implementation

Based on docs/sprint-2.md and docs/handoff-ryan-ios.md. Work stays on
RyanFrontendking, PRs target staging, and Adam merges. This report supersedes
Sprint 1's thick-separator and metric-input descriptions.

## Ryan's confirmed choices

Thin solid line with spacing; keep photo dots and remove the number counter.
Catalog styles plus vibe chips. Fits for you lives in Discover. Product summaries
have no extra label. Wait for Adam's shared-client additions; do not edit core.

## Implemented

- A1: 1 px solid separator with 24 px space above/below.
- A2/A3: search style labels without counts; keyboard dismisses on search, drag
  and tap outside.
- A4/A5/A6: double-tap heart scales/fades over the photo; normal save behavior
  updates the card heart. Dots remain; numeric position removed. Current/next
  carousel images and next product's first photo are preloaded with handled errors.
- A7 UI: short card blurb, More/Less for original retailer text. Uses the existing
  Product.blurb method so Adam's summary preference can land independently.
- A8: catalog styles and clean girl/old money/gorpcore chips plus optional own words;
  chips and text persist together through the existing onboarding contract.
- A9: Fresh connected installs require an explicit New account or team-test choice;
  server onboarding status alone never opens the demo profile. Connection available from entry and inline during scan setup; connect/retry
  retains the draft measurements. Local-only profiles can become their own server
  profile on connection; arbitrary missing remote IDs are not silently recreated.
- A10: repeated top-icon taps do not stack routes; switching top pages returns to
  the shell before opening the requested page.
- Fits for you: Discover entry, occasion chips, explicit generation of three fits,
  owned/catalog labels and catalog-to-seeded-Home taps, new-piece total, per-fit
  try-on with honest collage wording, add-fit-to-cart and refresh; failures retry.
- US-unit wheel pickers: height ft/in, weight lb, circumferences/inseam in, shoes US.
  API values remain cm/kg. Optional blank/clear and review are preserved. Scan and
  profile measurement displays use US units too.

## Waiting for Adam (Ryan explicitly chose to wait)

No changes to app/lib/core. Requests posted on staging in RYAN_TO_ADAM.md:
shopFor profile get/update, seedShown feed option, cart/unavailable flat imageUrl,
photo onboarding method/model. The Shop-for
screen, seed_shown reload behavior, flat removed-item photos and photo fast setup
are not shipped with a guessed or duplicate HTTP adapter. Adam's summary-dept
PR #40 is now merged and integrated through staging 46b7628; Product.blurb prefers
his server summary without a label. Closet brand/rematch
UI likewise needs his announced closet-real-pieces fields.

## Verification

102 Flutter tests pass; analysis reports no issues. Tests cover wheel conversion and
optional clear, combined chip/text persistence, inline connection retry without
losing height, non-stacking routes, More/Less, outfit creation/cart routing/error
recovery, heart animation and existing browsing/cart/scan flows. Browser US-unit
wheel layout reviewed using the actual connected demo profile without saving edits.
Release web and privately connected signed iOS builds both succeed.

Private URL/key are supplied from a local temporary defines file for iOS; they are
not in source or this report. Ryan deleted the old app, installed the fresh staging
build, trusted the developer profile and confirmed it opens. No live personal-photo
upload, social post, checkout or paid Fit Creator/try-on run was made by this agent.
