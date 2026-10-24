# Saturday Oct 24: 10-hour plan (9:00 AM – 7:00 PM PT)

Written Sat ~1 AM by Adam's session after checking every branch. **Starting point:**
- Everything is merged. `staging` = `main` @ 4f5df54 (PRs #7–#12).
- **Backend:** live on Adam's Mac through the tunnel; smoke test 10/10 (feed, size, AI try-on, complete the look, cart, Nessie checkout `paid`, Fit Check shop).
- **App:** Ryan's Flutter app runs on the live backend: Home → Quick Browse feed, wishlist, cart, checkout UI, orders. Tests: app 14/14, backend 248.

Per-person plans: **[adam.md](adam.md) · [nabil.md](nabil.md) · [ryan.md](ryan.md)**

**Goal by 7 PM:**
- The app runs on an iPhone (and in Chrome), with every commerce + AI feature reachable.
- Real photos: our fits, Adam's closet, Adam's body photo for try-on.
- Two demo dry runs done, with a backup video recorded.
- Devpost draft written.
- `staging` → `main`.

## Ground rules (unchanged)
- **Ryan owns the app and all its design.** Nobody else designs screens or tells him how they should look.
- **Lanes:** Adam = AI backend, hosting, `app/lib/core`, iPhone build. Nabil = commerce backend, Devpost, demo script, backup server.
- **PRs go into `staging` only.** Agents can open PRs but can't merge them, so a human merges at the merge windows.
- Handoffs go in the directional `.md` files on `staging`. No secrets in Git (URL and key stay private).

## Shared timeline

| Time | What | Who |
| --- | --- | --- |
| 8:45 | Mac + tunnel up, URL reposted if it changed; everyone pulls `staging` | Adam, all |
| **9:00–9:15** | **Standup.** Confirm this plan, or change it here. Reply "confirmed" in your `*_TO_ADAM.md`. | all |
| 10:30 | Merge window 1 | whoever is free merges |
| **12:00** | **Checkpoint A: on Adam's iPhone, feed → size → add to cart → checkout `paid`** (first real checkout) | Ryan drives, Nabil confirms in Nessie, Adam holds the phone |
| 12:30 | Merge window 2 | |
| 13:00–13:30 | Lunch | |
| 14:30 | Merge window 3 | |
| **15:30** | **Checkpoint B: AI features reachable in the app:** try-on, complete the look + Fit Score, Fit Check post + shop the fit, closet upload, Style DNA | all |
| 16:30 | Merge window 4 (last one for features) | |
| **17:00** | **Feature freeze.** Bug fixes only. Adam rebuilds the iPhone app from `staging`. | all |
| 17:30 | **Dry run #1** (timed), plus a screen recording as the backup video | all |
| 18:30 | Fixes from the dry run, then **dry run #2** | all |
| **19:00** | Wrap: Devpost draft complete, `staging` → `main`. Mac + tunnel stay up overnight. | all |

**Submission deadline:** confirm it on Devpost / the hacker guide at standup. This plan assumes Sunday morning, which leaves Saturday night for polish.

## If something breaks

| Problem | Fallback |
| --- | --- |
| Adam's Mac or the tunnel dies | **Nabil's backup server** (built by 10 AM, see nabil.md). Swap the URL in the app's settings. |
| Anthropic credits run out | Text features fall back to Gemini automatically; tagging and pairing keep working. Adam tops up. |
| AI try-on image fails | Try-on returns `mode: "collage"` (an outfit board) instead. Pre-computed try-ons are cached anyway. |
| Nessie fails at checkout | The order is kept with status `nessie_failed`, and the app shows that state. Retry. |
| The iPhone build fails | Demo the web build in Chrome (same app, same backend). |

## Confirmation (by 9:15)
Each person writes **"Plan confirmed"**, or what they want changed, at the top of their handoff file on `staging`:
- Ryan → `RYAN_TO_ADAM.md`
- Nabil → `NABIL_TO_ADAM.md`
- Adam → in the group chat

Changes to Ryan's part are Ryan's decision.
