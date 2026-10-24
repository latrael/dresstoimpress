# Team progress: overseer check

**Fri Oct 23, 2026, ~9:45 PM PT; update at ~11:15 PM below.** Adam's session checked every branch and PR, the shared backend and the handoffs. Newer checks replace this file.

**Ownership:**
- **Ryan:** the app and all of its design.
- **Adam:** AI backend, hosting, and `app/lib/core` kept in sync with the backend.
- **Nabil:** commerce backend.

## Overnight log (Adam's session, every 20 min)

- **1:55:**
  - **Open PRs to merge at 9:15:** **#13** (`app/ios`, Ryan's OK needed), **#14** (Nabil: Devpost draft + demo script, in progress), **#15** (Adam: AI quality fixes + `reset_demo` + AI write-up). No conflicts between them.
  - **Server:** up on `staging` @ 4f5df54. Tunnel 200, `caffeinate` on.
- **1:50:** AI quality check on live data: 10 warnings → 0 fail, 8 harmless after the fixes (PR #15).
- **1:20:** the unsigned iOS release build succeeds (iOS 26 SDK installed).

## Update: Fri ~11:15 PM

- **Merged into `staging`:** #8 (Adam), #7 (Nabil), #9 (shell + core), #10 (Ryan's app). Every deviation in the table below is closed except #5, the `/fit` OK, which is waiting on Ryan.
- **Server:** pulled to `staging` and restarted. Tests: backend **248 pass**; app `flutter analyze` clean, **14/14** tests.
- **Checks:**
  - `seed_fitcheck` re-run with the richer tags.
  - **Smoke test 10/10 through the tunnel.** The feed has a reason on 8 of 8 cards, and Nessie checkout is `paid`.
  - New routes are live: search, users, Fit Score on the seed posts (85).
  - Auth: `/fit` 404 (off), `/fitcheck` 401 without the key.
- **Open:** **PR #11** (core: Ryan's 3 asks + `/img` exact match). Ryan's remaining screens are his call. Then the iPhone build: iOS 26 platform download (Adam).

## Snapshot

| Branch | Head | vs `staging` | PR | State |
| --- | --- | --- | --- | --- |
| `main` | f90c36e | 15 behind, 0 ahead | — | last known-good (PR #2 + #3) |
| `staging` | 669043d | — | — | Ryan's latest handoffs on top of #5/#6 |
| `adam/ai-pipeline` | this commit | ahead | **#8** open | Style DNA, feed-reason top-up, `/img` proxy, app plan, these docs. 210 tests |
| `nabil` | 74b7499 | 13 ahead | **#7** open | onboarding/users, search, ranked-first feed, Fit Check seed tags, public `/fit` guest page, judges' README. **247 tests pass**; includes #8's commits |
| `flutter-starter` | 1b4aff2 | 3 ahead | **#9** open | shared Flutter shell + core (API client, models). Analyze clean, 13/13 live routes decode |
| `RyanFrontendking` | c45ad88 | **62 behind**, 4 ahead | — | Ryan's Quick Browse Feed + 4 widget tests, wireframe, specs |

- **Backend:** live on Adam's Mac through the tunnel. `smoke_e2e` 10/10: feed, size, AI try-on, complete the look, cart, real Nessie checkout `paid`, Fit Check shop, usage.
- **Data:** 418 products, all tagged. 3 Fit Check demo posts seeded.
- **AI spend:** ≈ $0.07 on Adam's runs, plus ≈ $0.40 from Nabil's tag pass, under the $5 cap.
- **App:** Ryan's Feed was checked inside `flutter-starter`, unchanged: `flutter analyze` clean, **4/4 tests pass**. It hasn't run against the live backend yet (Ryan has no URL/key yet).
- **Secrets:** scanned all 6 branches and the full history for API keys, the shared key and the tunnel URL. **Clean.**

## Deviations found

| # | What | Status |
| --- | --- | --- |
| 1 | PR #3 went `nabil` → **`main`**, skipping `staging` | Fixed: `staging` fast-forwarded to `main`, and every PR since targets `staging`. Rule stands: only `staging` → `main`. |
| 2 | **Adam changed the app plan 3 times in an hour** (SwiftUI → Flutter → "starter is reference only"). Ryan built against the middle version and waited for a starter that was then downgraded. | Fixed: `flutter-starter` is the shared shell + core again (PR #9) and is verified with Ryan's Feed. `docs/app-plan.md` now matches what Ryan approved. No more plan changes without Ryan. |
| 3 | Adam's docs gave Ryan **design instructions** (what to hide or grey out, labels, badge placement, look and feel, branch naming) | Removed from ADAM_TO_RYAN, app-plan, ADAM.md, schema.md and the starter README. They now state data facts only. Nabil's notes to Ryan also contain display guidance (see Nabil's next steps). |
| 4 | Ryan's handoff still lists the old split (Ryan = Feed, Nabil = Cart/Fit Check, Adam = Closet/Profile) | Current: Ryan owns all screens; Adam and Nabil stay on the backend. Communicated in ADAM_TO_RYAN. |
| 5 | Nabil's **public `/fit` guest page** is a user-facing web page outside the app, so its design is in Ryan's area | Needs Ryan's OK. Security reviewed and fine: off unless `FITCHECK_EVENT_CODE` is set, rate-limited, guest cap, AI tagging under the budget cap, escaped output. |
| 6 | `RyanFrontendking` is 62 commits behind `staging` | Ryan merges `staging` (and #9) in before his PR. His files don't overlap with anyone's. |
| 7 | PR #7 contains PR #8's commits (Nabil merged `adam/ai-pipeline` in), and after Adam published newer handoffs on `staging` it **conflicts on 3 of Adam's doc files** | Nabil merges `staging` and takes `staging`'s copies of those 3 files; exact commands in ADAM_TO_NABIL. Checked: 0 conflicts, 247 tests pass. |
| 8 | Feed: 5 of 8 cards come back with a reason | Backend half done (#8: `pair()` always returns reasons). Nabil's ranked-first `/feed` is in #7. |
| 9 | Two tag passes collided (#5 vs #6) | Resolved: kept the name-hinted snapshot (0 vs 37 wrong labels). |
| 10 | Anthropic "credit balance too low" during Nabil's tag pass | Adam checks / tops up. |

## Next steps

### Adam (things only you can do)
1. **Merge into `staging`, in order: #8 → #7 → #9** (or ask Nabil to). After each one, Adam's session restarts the server and re-runs the smoke test.
2. **Send Ryan the tunnel URL + key privately.** He hasn't been able to test live yet.
3. **Anthropic credits:** check the balance and top up.
4. **For the iPhone build later:**
   - Xcode → Settings → Components → install the **iOS 26** platform.
   - Then run `sudo xcode-select -s /Applications/Xcode.app`.
5. **Keep the Mac awake** (`caffeinate -dims` in a Terminal tab) with the tunnel window open. Repost the URL if it changes.
6. **Guest page:** if Ryan OKs it, set `FITCHECK_EVENT_CODE` in `backend/.env` after #7 merges.
7. **Optional cleanup:** `brew cleanup` (2.3 GB), `git worktree remove ~/dti-ios`, `git branch -D ios-starter`.

### Nabil
1. Merge `staging` into `nabil` (3 doc conflicts, commands in ADAM_TO_NABIL). Review #8 and #9; merge #7 once #8 is in.
2. Ask Ryan about the `/fit` guest page. It's a user-facing surface, so it's his call.
3. Keep NABIL_TO_RYAN to data facts (shapes, errors, meanings). How things display is Ryan's decision.
4. Devpost write-up, the README for sponsor judges (Apify, Capital One / Nessie) and the demo script.

### Ryan
1. Merge `staging` into `RyanFrontendking`, plus `flutter-starter` (PR #9). Your Feed already builds and passes its tests there.
2. Run against the live backend once Adam sends the URL + key.
3. Your pending list, in your order and your design. Ask Adam for any missing call or field; he keeps `core/` matching the backend.

## Checkpoints

| When | Checkpoint |
| --- | --- |
| Fri night | #8, #7, #9 merged. Ryan's Feed runs in Chrome against the live backend. |
| **Sat noon** | End-to-end on a phone: feed → save / add to cart → checkout `paid`. Then `staging` → `main`. |
| Sat evening | AI features reachable in the app. Real fits photographed at the venue. iPhone build. |
| Sun morning | Feature freeze, backup demo video, submit. |
