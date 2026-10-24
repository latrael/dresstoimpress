# 10-hour plan: Sat Oct 24, 1:00 AM – 10:00 AM PT

So nobody starts from scratch at 9 AM. Written ~1 AM by Adam's session after checking every branch.

**Starting point:**
- `staging` = `main` @ 4f5df54; all PRs #7–#12 are merged.
- **Backend:** live on Adam's Mac through the tunnel (smoke test 10/10, including a Nessie `paid` checkout).
- **App:** Ryan's Flutter app runs on the live backend (feed, wishlist, cart, checkout, orders).
- **Tests:** app 14/14, backend 248.

Per-person plans: **[adam.md](adam.md) · [nabil.md](nabil.md) · [ryan.md](ryan.md)**

**Everyone is asleep 1:00–9:00.** So:
- **Overnight work is agent-only.** No overnight task needs a person: no photos, no phones, no merges.
- **Adam's session is the only agent guaranteed to run all night.** It's already running, with check-ins every 20 minutes, on Adam's Mac (plugged in, lid open, `caffeinate` on).
- **Nabil's and Ryan's overnight items only happen if their agent is running.** Nobody is awake to start one. Anything an agent didn't do moves to **9:15** for that person, in the same order.
- **9:00–10:00 is the human handoff:** review what the agents did, merge, and do the few things only people can do.
- **Adam's session checks in every 20 minutes all night:** health check, new commits, answering asks.

## Timeline

| Time | Adam's session (running) | Nabil's agent (only if running) | Ryan's agent (only if running) |
| --- | --- | --- | --- |
| 1:00–3:00 | ✅ iOS platform PR #13, reset script, AI write-up. Then the AI quality pass on live data, fixes in a PR. | Backup server on Nabil's laptop; 3 test checkouts verified in Nessie | Ryan's own list, his order: size advice + product details |
| 3:00–5:00 | One-command demo-data scripts (closet photos folder, body photo); warm the try-on cache | Devpost draft (`docs/devpost.md`), using `docs/ai-writeup.md` | Try-on, complete the look + Fit Score |
| 5:00–7:00 | Fallback drill (Claude → Gemini → rules) on a separate port; answer core asks | Demo script draft (`docs/demo-script.md`); real-fits upload script ready for the morning photos | Onboarding + search, Fit Check |
| 7:00–8:30 | Keep the server on the latest `staging` (tests + smoke); answer asks | Answer asks; final checks | Closet, Profile / Style DNA; PR into `staging` by 8:30 |
| 8:30–9:00 | **Morning report** in `docs/progress.md`: what's done, what each person must do at 9 | Same, in `NABIL_TO_ADAM.md` | Same, in `RYAN_TO_ADAM.md` |
| **9:00–9:15** | **Standup (humans):** read the morning reports, confirm or change the rest of the day, confirm the submission deadline | | |
| 9:15–10:00 | **Adam:** merge PRs, iPhone build, photos (body + closet) | **Nabil:** real Fit Check photos, backup URL check, merges | **Ryan:** review his agent's work, decide on PR #13 + `/fit` |

## Before bed (2 minutes, optional)
- **Adam:** Mac plugged in, lid open, tunnel window open. `caffeinate` is already on.
- **Nabil / Ryan:** if you want your agent working overnight, keep your laptop plugged in, open, and awake (`caffeinate -dims` on a Mac). Start your agent with:
  > Work through my overnight list in `docs/plan-sat/<you>.md` on `staging`, top to bottom, with no human available until 9 AM. Never wait for me: if something needs a decision or a person, skip it, note it in my morning report, and move on. PRs into `staging` only; never merge. Write the morning report at the top of `<YOU>_TO_ADAM.md` by 8:30.
- If you skip this, nothing is lost: your list starts at 9:15.

## After 10:00 (daytime checkpoints)

| Time | Checkpoint |
| --- | --- |
| **12:00** | **A:** on Adam's iPhone, feed → size → add to cart → checkout `paid` |
| **15:30** | **B:** all AI features reachable in the app (try-on, complete the look + Fit Score, Fit Check shop, closet, Style DNA) |
| **17:00** | Feature freeze (fixes only); Adam rebuilds the iPhone app |
| 17:30 / 18:30 | Dry runs #1 and #2, plus the backup screen recording |
| **19:00** | Devpost draft complete; `staging` → `main` |

## Ground rules
- **Ryan owns the app and all its design.** His agent works his list his way; nobody else designs screens.
- **Lanes:** Adam = AI backend, hosting, `app/lib/core`, iPhone build. Nabil = commerce backend, backup server, Devpost, demo script.
- **PRs into `staging` only.** Agents open PRs; humans merge, at 9:15 or later.
- Handoffs go in the directional `.md` files on `staging`. No secrets in Git.

## If something breaks

| Problem | Fallback |
| --- | --- |
| Adam's Mac or the tunnel dies | Nabil's backup server (overnight task); swap the URL in app settings |
| Anthropic credits run out | Text falls back to Gemini automatically; Adam tops up in the morning |
| AI try-on fails | Returns an outfit board (`mode: "collage"`); warmed try-ons are cached |
| Nessie fails | The order is kept as `nessie_failed`; retry |
| The iPhone build fails | Demo the web build in Chrome |

## Confirmation
Each person (or their agent, for its own overnight part) writes **"Plan confirmed"**, or their changes, at the top of `RYAN_TO_ADAM.md` / `NABIL_TO_ADAM.md`. Adam confirms in the group chat. Changes to Ryan's part are Ryan's decision.
