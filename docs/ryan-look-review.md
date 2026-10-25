# Ryan: scoring, closet imagery and try-on review

## User decisions and scope

Ryan authorized merging existing PR #56; merged into staging at 343d6b5.
Comments now has one entry point; the add field is inside the sheet.
Ryan chose closet first, catalog for gaps. Sign-in remains on hold.
This follow-up is a separate PR into staging for review; no backend deployment.
Shared core is unchanged.

## Changes

- Fit Score uses an everyday-wear curve. Missing style/formality/fit metadata is
  neutral evidence. Matching silhouettes and no extra layers are valid choices.
  Clear clashes, missing bases and the all-criteria >=8 gate for 90+ remain.
  Photo-critic silhouette/layering anchors match, with a new critique cache version.
- The app shows primary style and all criterion scores/notes, falling back to the
  old four-part score on old servers. Inspo sends the actual post photo when the
  user requests a score. Complete the Look displays its returned score immediately.
- Complete the Look resolves selected closet IDs against the actual wardrobe and
  uses only owned clean/crop photos. Catalog gaps resolve the exact product ID
  and are labeled Catalog piece; missing photos never receive a random substitute.
  Photo-read errors leave recommendations accessible with a message.
- Product try-ons carry the server-selected source photo into the local gallery.
  Compare with original / Show try-on switches that bounded image in place;
  both use contain, preserving framing. It performs no second generation. Collage
  results stay labeled as outfit boards and offer no false person comparison.

## Evidence and limits

170 Flutter tests pass; analysis clean; release web and signed iOS builds succeed.
89 selected backend tests pass: scoring/calibration, Complete the Look, outfit rules,
Fit Creator, shop quality, try-on prompts and source selection. No live paid AI run.
Seed-7 calibration: 300 random median70, 30 curated median84, neither automatically
receives 90+. Sparse everyday fixture: 35 -> 72. Slim coherent fixture: 85 -> 89.
Browser review on the live team profile verified catalog images/labels, style and
criteria display, and one Comments button opening the composer sheet. No live
comment/like writes or personal photo uploads. Actual new try-on render quality
has not been visually accepted here; source/prompt/display behavior is verified,
and the comparison control supports reviewing the real edit. Backend scoring
changes require Adam to deploy before the live app reflects the new calibration.
The current iOS build is compiled, not newly installed in this turn.
