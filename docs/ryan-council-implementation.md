# Ryan council sprint implementation

Source: docs/council-final-sprint.md, plus Ryan's answers in the app chat.
Implementation stays on RyanFrontendking; PRs target staging and are not merged by
Ryan's agent. Staging was integrated through 54063b6, including Adam's canonical
council methods/models and Nabil's routes. The 17:00 cutoff is optional per Ryan.

## Confirmed product decisions

- Scan before reviewing measurements; keep its photo private for try-on.
- Login returns to the profile saved on this device. New account creates a server
  profile when connected; team test profile is an explicit separate option.
  Google sign-in remains deferred. No password login or arbitrary-ID login.
- H&M/Uniqlo chips plus optional other-store interests (no claim of extra catalogs).
- Matched Inspo tags show catalog name/store/price; unmatched tags search by label.
- Trending mixes community engagement with personal feed suggestions.
- Closet offers one-item upload and whole-outfit/wardrobe digitizing.

## Ryan P0 / P1

- Persistent Liked → Cart → Closet → User header on every route, accessible above
  Navigator semantics; floating Home / Discover / Inspo island tabs.
- Home starts after onboarding; one continuous lazy list with solid separators,
  horizontal-only galleries, automatic available sizes, in-size/alternate badges.
  No passive /swipe events. A missing real size is never silently substituted.
- Seeded Home uses api.feed(seed:). Every catalog entry point shares it; the chip
  clears the seed and ignores late responses. Unknown/out-of-stock seeds stay visible.
- Separate Welcome, Style, Stores, Scan, Measurements, Budget and Done screens.
  Optional steps can be skipped. User opens each section separately later.
- Server style/budgets/stores/onboarded, plus syncToServer for dimensions/fit/usual
  sizes. Device preferences are a cache/session, not authentication. cm/inch conversion
  follows the shared body-profile model. No default body dimensions are invented.
- Scan asks height, offers camera/gallery, shows AI/estimate wording and note, fills
  blank dimensions and requires a review/save action before leaving setup for Home.
  Typed values are not overwritten by pre-filling. Private photo preview/delete is
  available under User, preserving measurements when its photo is deleted.
- Discover camera/gallery upload uses searchPhoto, not social or body-photo routes.
  Text uses search with vibe fallback; style chips/counts and a trending/personal mix;
  separate Similar/Goes with it grids. Owned closet matches are labeled, not cartable.
- Inspo is the shared feed, with author filtering, photo-toggled tag overlay, catalog
  metadata where matched and label search otherwise. Own-post deletion is confirmed.
  Tag boxes/pins remain optional polish; old/no-box posts have the same usable overlay.
- Liked uses api.wishlist, including saves absent from the loaded feed.
- Cart size pencil uses the atomic PATCH. Generic missing-route 404/405 can use the
  older add/remove compatibility path; a missing cart line never creates a new line.
  Quantities are preserved. Unavailable lines are visible/removable and block checkout.
- Staging payment retry/receipt wiring retained, plus history retry and cart thumbnails.
  Paid totals are distinct from order totals; cart opens by refreshing the server copy.
- User groups setup answers, Style DNA, orders, private photo, connection, local logout
  and restart-setup. Shared-user auth/privacy infrastructure is still the team's MVP.

## Validation and acceptance

81 Flutter tests, including ten new council-flow checks, pass; Flutter analysis clean.
Release web build passes. Private health/feed/search-styles checks and browser Home,
Discover, images and catalog-to-seeded-Home navigation succeeded. The signed iPhone
release built and installed. The final launch was blocked because the iPhone is
locked; unlock it and open Niche. An earlier checkpoint launched through devicectl. A real
on-device walkthrough of camera/scan/cart is still needed. No credentials or private
photos are committed. Test image uploads use synthetic fixtures and mocked endpoints;
no live body-photo/social upload or live payment was performed by the agent.

The shared API matches Adam’s council methods; the only sizing extension is
`sizeAdvice(useSavedProfile: true)`, which omits unspecified height/weight rather
than sending the old Settings defaults. Staging’s latest backend additions (shop_for,
seed_shown and cart-line image_url) are additive; their optional UI/client extensions
remain follow-ups. No gender preference was inferred for Ryan’s users.

The existing body-scan API saves estimates/photo as part of scanning, before the
client review; the UI makes review explicit. A true draft/confirm endpoint is a
backend follow-up if estimates must remain uncommitted until user confirmation.
