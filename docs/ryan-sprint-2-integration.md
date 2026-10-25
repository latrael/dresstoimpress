# Ryan: integrate Adam's merged Sprint 2 client

Built on staging through #47 (79c9c66) and the subsequent handoff. No direct changes
to app/lib/core. PRs target staging; Adam merges.

## Completed

- Shop for has its own skippable onboarding screen (Men / Women / Both), editable
  from User. Server shopFor is restored and saved through updateUser; the local
  per-user cache retains it. First setup now has eight screens.
- Pull to refresh works on Home. Seeded refresh sends seedShown=true after showing
  the selected seed. A new result tap omits it, even for the same product; clearing
  the chip resets the session. Late replies cannot replace a newer feed.
- Available and unavailable cart rows fall back to flat line imageUrl when their
  product disappeared. All eight known retailer names display correctly in cart,
  Fits and Home's brand fallback.
- Scan uploads request commit:false. Leaving/canceling or skipping the scan/review
  never confirms a draft. Discard removes untouched prefilled estimates while keeping
  manual edits. Rescanning replaces only untouched estimates.
- Save confirms the reviewed scan, sending only changed dimensions as manual edits
  (cm/kg converted to inches where required). Unchanged AI estimates are not copied
  through the manual-dimension endpoint. Editing other profile sections also avoids
  reclassifying unchanged server measurements as manual.
- The standalone body-scan route also uses draft/confirm, with errors/retry visible.
- All eight published store IDs are recognized in onboarding and profile caching;
  other-store interests stay separate and saved IDs are preserved.

## Shared-client requests still pending

GET /stores exists and returns eight stores, but Api.stores()/store metadata model
is absent. RYAN_TO_ADAM.md requests it. The UI uses a central eight-store fallback
until that arrives; dynamic counts/department filtering are not claimed.
Photo onboarding and closet brand/rematch remain awaiting merged Adam contracts.
Saved-dimension clearing also needs a way to send explicit null through the client:
its current transport omits null fields. The app reports an unsupported clear rather
than claiming it saved one. New optional blank inputs still work.

## Verification

112 Flutter tests pass; analysis clean; release web and signed iOS builds succeed.
Tests cover Shop-for persistence, eight-store preference restoration, seed refresh
and reset parameters, cart images without a product, cancel without confirming,
and scan edits without marking unchanged estimates manual.

After Adam's reconnect, read-only live checks succeeded: health 200, scan-confirm
path rejects GET with 405 (POST route exists), authenticated stores 200/eight rows.
No live personal-photo upload, profile write, social post, purchase or paid AI run
was performed. Credentials remain in private local build configuration outside Git.
The phone update may require reconnecting the physical device; installation status
is recorded in the staging handoff after publishing.
