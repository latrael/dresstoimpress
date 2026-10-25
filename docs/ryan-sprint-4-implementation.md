# Ryan Sprint 4 implementation — October 25

Based on docs/sprint-4.md, font-banks.html, logo-board.png and current-home.png.
Ryan chose double-tap-only Home likes, cream glass navigation, and full-width
Discover results. Deep merlot glass remains an alternative for a later review.
Sign-in remains on hold. PR targets staging; agent does not merge this increment.

## Delivered

- Bundled Young Serif regular400 + four static Manrope weights, with OFLs. Shared
  role-based type scale, palette, round surfaces, pills, glass and touch feedback.
  Display type never uses synthetic bold/italic; no raw font sizes/weights remain
  outside the type system. Phosphor 2.1.0 font assets are pinned with MIT license
  and checksums; plain const IconData avoids the old wrapper's incompatibility
  with Flutter 3.47.6's final IconData class. animations is pinned at 3.0.0.
- Edge-to-edge cream, readable system icons, lowercase wordmark, three outline
  icons + initial avatar, rolling bag badge/bounce. Physical bottom inset is
  preserved outside Scaffold so the full cart button clears the nav on iPhone.
- Glass navigation with live PageController indicator and horizontal tab paging.
  Photo carousel drags clamp inside their frame, including at the last slide;
  caption drags switch tabs. System edge gestures remain platform-owned.
- Home is vertical snapping reels. Three slides: hero product / on-you status /
  2x2 owned closet picks. Stories bars, double-tap save, expandable details and
  available-size sheet; Add to cart is the only main action and morphs to Added.
  Seed reset and pull-to-refresh are preserved. Next two hero images are warmed.
- Adam's merged core is wired through ReelsBindings: real heroImageUrl,
  closetPicks, tryOn, prefetchTryOns and tryOnStatus. First3/next3 prefetch; immediate
  visible cache read and 3-second pending polling. Work pauses when Home is hidden
  or app is backgrounded. Backend owns its20/user/day and400 server caps.
  Body-photo/closet returns refresh the feed; owned tiles open their actual piece.
  Missing photos and unavailable/collage modes are honest; no random substitutes.
- Onboarding has a drawn arch/dropping dot, real catalog-photo mosaic, one Let's go
  CTA, step transitions, animated progress/chips and fixed Next/Skip/Back controls.
  Scan-first review/save behavior and existing measurement/budget persistence stay.
- Discover/Liked use full-width natural-ratio photos and shared Home landing.
  Inspo, comments, cart, closet, profile, connection and other screens inherit
  shared typography/icons/surfaces/routes. Inspo gets like pop/haptic and glass
  tags; cart gets rounded photos and tabular prices. Reduced motion uses fades.

## Verification

185 Flutter tests pass; analysis clean; release web and debug iOS simulator builds
succeed. 12 focused Sprint4 checks include font asset registration, carousel/tab
isolation, snap scrolling, sizes/cart, owned-photo provenance, production client
bindings, polling/visibility and actual system insets through the full app shell.
Native iPhone16/iOS27 simulator review confirmed real fonts/icons, no black band,
and the full Add to cart button visibly above navigation. The native review found
and fixed the inset-consumption bug that simple viewport tests missed.

Before: docs/sprint-4/current-home.png (Nabil's physical iPhone16).
After: docs/sprint-4/after-home-iphone16-simulator.png (unedited Device Hub capture;
SIMULATOR, not physical-device acceptance). Live u_demo feed and account checked;
the test user has no body photo, so this review performed no paid try-on render,
no personal upload, no social write and no checkout. Private connection/signing
configuration remains outside Git. Shared core/backend changes are Adam/Nabil's
merged staging commits; this app increment does not edit their source.

## Team follow-up, not claimed complete

- Pixel9Pro hardware screenshots/gesture-back/haptics, and physical iPhone16
  acceptance. No Android SDK/emulator is installed here; Ryan's phone unavailable.
  393x852 and412x915 widget viewport checks are not hardware screenshots.
- A photo-owning user's real ready/pending/AI/collage slide review and the measured
  preloaded experience on post2+; backend reports15-20s. UI/client states are tested
  with deterministic fixtures. Shared-server deployment remains Adam's lane.
- Welcome motion/haptics/large-text device acceptance remains part of review.
