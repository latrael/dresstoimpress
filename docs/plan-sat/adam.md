# Adam: Saturday plan (9:00 AM – 7:00 PM)

**Lane:** AI backend, hosting (Mac + tunnel), `app/lib/core`, the iPhone build, and the AI parts of the demo. Shared timeline and checkpoints: [README.md](README.md).

## Overnight: Adam's session (already running; checks in every 20 min)
- [ ] Health check of the server + tunnel each round; restart uvicorn if it's down.
- [ ] Watch for new commits and PRs and re-test anything that lands.
- [x] **iOS platform PR for Ryan's approval:** **PR #13**, `flutter build ios` OK (Runner.app, 17.5 MB). add `app/ios/` with `flutter create --platforms ios`. No `lib/` changes. Verify `flutter build ios --no-codesign`. Ryan decides whether it merges.
- [ ] **AI quality pass on live data:**
  - Sample 30 feed reasons: they name a real closet item, use ≤12 words, and stay in budget.
  - Shop-the-fit on the 3 seed posts.
  - Size advice across the real size formats.
  - Fix anything found in the AI lane, with tests, and open a PR.
- [x] **`docs/ai-writeup.md`:** drafted. the AI section for Devpost (Claude Haiku tagging/pairing with a $5 cap, Gemini try-on, rules fallbacks, costs). Nabil pastes it into Devpost.
- [x] **`scripts/reset_demo.py`:** done, with a test. returns u_demo to a clean state for dry runs (empty cart, no swipes or wishlist, closet kept).

## 8:45: before standup
- [ ] **Mac awake:** run `caffeinate -dims` in a Terminal tab and leave it running all day.
- [ ] **Tunnel check:** `curl https://<tunnel>/health` should return `{"ok":true}`.
  - If it fails, restart: `cloudflared tunnel --no-autoupdate --url http://localhost:8000`.
  - Paste the new URL to your session (it updates `PUBLIC_BASE` and restarts the server).
  - Post the URL + key privately to Ryan and Nabil.
- [ ] **iOS SDK:** `xcodebuild -showsdks | grep iphoneos` should show iOS 26.0 (it's there as of 1 AM).

## 9:00–9:15: standup
Confirm the plan, the submission deadline, and **Ryan's OK on the iOS platform PR**.

## 9:15–10:15: iPhone build (Checkpoint A depends on it)
- [ ] Merge the iOS platform PR, once Ryan OKs it, then `git pull origin staging`.
- [ ] **On the iPhone:**
  - Settings → Privacy & Security → **Developer Mode** on (it restarts the phone).
  - Plug it into the Mac and trust the computer.
- [ ] **In Xcode:** `cd ~/dresstoimpress/app && open ios/Runner.xcworkspace`. Under Runner → Signing & Capabilities:
  - Team = your **Personal Team** (Apple ID).
  - Bundle Identifier = something unique, e.g. `com.acwarob.dresstoimpress`.
- [ ] **Run it:** `flutter devices` lists the phone, then `flutter run -d <phone id> --release`.
  - The first launch fails until you trust the developer: Settings → General → VPN & Device Management.
- [ ] Enter the URL + key in the app's connection settings.
- **Done when:** the feed loads on the phone with photos, and add-to-cart works.

## 10:15–11:15: real demo data (the AI demo depends on it)
- [ ] **Body photo for try-on:** one full-body photo of you, front-facing, plain wall, fitted clothes, head to feet in frame.
  - AirDrop it to `~/dti-photos/body.jpg` and tell your session.
  - It uploads to u_demo (`POST /users/u_demo/body-photo`) and runs 3 test try-ons.
- [ ] **Closet:** 6–8 of your real clothes, one item per photo, laid flat, in daylight. Include at least 2 bottoms, 2 tops, 1 shoes and 1 outerwear.
  - AirDrop them to `~/dti-photos/closet/`.
  - Your session runs `python -m scripts.eval_tagger ~/dti-photos/closet`, then uploads each via `/closet/upload` to u_demo and removes the 3 placeholder closet items.
- **Done when:** `GET /closet/u_demo` shows your real items with correct labels, and feed reasons mention them ("goes with your black cargos").

## 11:15–12:00: AI check on real data
- [ ] With your session: read 20 feed reasons, try on 5 demo picks, and run the size advice on your real height/weight.
- [ ] **Fit Check:** take 2 real fits at the venue (with Nabil, see nabil.md), then "shop this fit" should return sensible items.
- [ ] Anything that looks wrong: your session fixes it (prompts/rules) in a PR before the 12:30 merge window.

## 12:00: Checkpoint A (you hold the phone)
Feed → size → add to cart → checkout `paid`. Nabil confirms the purchase in Nessie.

## 12:30–13:30: merge window + lunch
- [ ] Merge the open PRs that passed their tests.
- [ ] **Credits:**
  - Anthropic: console.anthropic.com → Billing. Top up $10 if the balance is under $5. Nabil saw "credit balance too low" errors Friday.
  - Gemini: AI Studio → billing is active.
  - Spend so far is about $0.08 (+ ~$0.40 from Nabil's tag pass).

## 13:30–15:30: support + write-up
- [ ] **Ryan's core asks:** whatever call or field he needs (your session adds it to `app/lib/core` + tests, aiming to turn it around in 30 min).
- [x] **`docs/ai-writeup.md`:** drafted. read your session's draft, fix anything, and send it to Nabil for Devpost.
- [ ] **`/fit` guest page:** if Ryan said yes, set `FITCHECK_EVENT_CODE=<private code>` in `backend/.env` and restart. Then `https://<tunnel>/fit/qr?code=<code>` shows the URL for the QR.

## 15:30: Checkpoint B
The AI features are reachable in the app: try-on, complete the look + Fit Score, Fit Check shop, closet upload, Style DNA.

## 15:30–17:00: demo prep
- [ ] Rebuild the iPhone app from the latest `staging`: `git pull && cd app && flutter run -d <phone> --release`.
- [ ] Warm the try-on cache for the picks the demo will show: `cd backend && python -m scripts.precompute_tryons --limit 10` (≈10 Gemini images).
- [ ] Run `python -m scripts.reset_demo` before each dry run.

## 17:00–19:00: freeze, dry runs, wrap
- [ ] 17:00 freeze: fixes only. Final iPhone rebuild.
- [ ] **17:30 dry run #1.** You present the AI parts: your closet → feed reasons that mention it → try-on on your body photo → complete the look with its Fit Score → shop a friend's fit.
  - Record the iPhone screen (Control Center → Screen Recording) as the backup video.
- [ ] 18:30 fixes, then dry run #2.
- [ ] 19:00: merge `staging` → `main`. Leave the Mac + tunnel running, with `caffeinate`.
