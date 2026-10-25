# Onboarding and account entry

Council flow supersedes the older combined form. Entry offers returning-device
Login, New account, and an explicit team test profile. Google sign-in is deferred.
Connected account creation uses Api.createUser and remembers its returned ID;
sample-mode profiles are explicitly local. Invalid/missing saved server profiles
return to entry instead of impersonating another user.

First setup is seven screens: Welcome → Style → Stores → Scan → Measurements →
Budget → Done. Every optional step has Skip for now; Welcome can skip setup.
User exposes each section for editing later. Scan precedes manual review. Height
is the reference, weight optional; camera/gallery choices use the existing picker.
AI estimates and fallback estimates are labeled, notes/head-to-feet warnings shown,
and typed dimensions are retained when a scan pre-fills blanks. The photo stays
in the private scan/try-on profile and can be previewed/deleted under User.

Live style text uses onboarding; price limits, preferred stores (including other
interests), and onboarded use updateUser. BodyProfile syncing saves height/weight,
chest/waist/hips/inseam, shoe size, fit and usual top/bottom/shoe sizes on the server.
Measurements use US-unit scroll wheels (ft/in, lb, inches and US shoes). Values
convert to cm/kg for the API; shared profile inches convert to the metric cache.
Style begins with catalog/vibe chips plus optional own words. Connection can open
inline from scan setup without losing draft measurements.
Skipped/blank category budgets are omitted; editing the budget section can clear
old caps using an explicit map. Device completion/preferences are a cache/session,
not a password or secure sign-in service.

Home uses authoritative yourSize/inYourSize card fields when known. Missing size
advice can use explicit measurements or exact usual-size matches. The saved-profile
client option sends null for omitted height/weight instead of 170/65 defaults.
Only available sizes can reach the cart. Unknown sizes prompt setup; a known
unavailable fit offers an explicit alternative chooser and stays in the feed.
The cart pencil uses atomic size replacement, retaining quantity.

Backend caveat: bodyScan currently persists its estimates while returning them.
The app requires review/save before completing setup, but draft-only scan storage
would need a backend draft/confirm contract. No photo is published to Inspo by scan.

Sprint 2 status and pending Adam contracts: docs/ryan-sprint-2-implementation.md.
