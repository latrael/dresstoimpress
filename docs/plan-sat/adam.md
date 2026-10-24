# Adam: 1:00 AM – 10:00 AM

**Lane:** AI backend, hosting (Mac + tunnel), `app/lib/core`, iPhone build. Team timeline: [README.md](README.md).

## Overnight: Adam's session (check-ins every 20 min; ticks these off in order)
- [x] **1:00:** iOS platform PR for Ryan's approval: **PR #13**. `flutter build ios --no-codesign` OK (Runner.app, 17.5 MB, iOS 26 SDK).
- [x] **1:00:** `scripts/reset_demo.py` (+ test). Empties u_demo's cart, swipes and wishlist; keeps the closet, profile and try-on cache.
- [x] **1:00:** `docs/ai-writeup.md`, the AI section for Devpost, for Nabil.
- [x] **1:40–3:00: AI quality pass on live data,** done 1:50 → **PR #14** (`scripts/ai_quality_check.py`, before: 10 warnings, after: 0 fail, 8 harmless). Fixed: budget-first ranking, made-up closet items in reasons, shop-the-fit order + colour duplicates, women's numeric size estimate. with fixes plus tests in one PR into `staging`.
  - 30 feed reasons: each names a real closet item, is ≤12 words, and stays in budget.
  - Shop-the-fit on the 3 seed posts + 5 made-up tags.
  - `/size` on 20 products × 3 body types.
  - Spot-check tags on 20 products.
- [ ] **3:00–4:00: one-command demo data for the morning,** with tests.
  - `scripts/load_closet.py <folder> [--user u_demo] [--replace-seed]`: tags and uploads each photo, then removes the 3 placeholder items.
  - `scripts/set_body_photo.py <file> [--user u_demo]`.
- [ ] **4:00–5:00: warm the try-on cache** for u_demo's top 10 picks (`python -m scripts.precompute_tryons --limit 10`, ≈10 Gemini images). This uses the current demo body photo; it re-runs after Adam's real photo.
- [ ] **5:00–6:00: fallback drill.** On a second server on port 8001 (never the shared one), force Claude off → Gemini, then both off → rules, and AI images off → collage. Confirm the app-facing shapes don't change. Write the results in `docs/progress.md`.
- [ ] **6:00–8:30: keep current.** Answer Ryan's and Nabil's agents' core/AI asks (PRs into `staging`). Fast-forward the server to new `staging` merges, then tests, restart, smoke.
- [ ] **8:30: morning report** in `docs/progress.md`: what got done, open PRs to merge, and Adam's 9:15 checklist.

## Before bed (now)
- [ ] **Mac plugged in** (it was on battery at 1 AM, ~9 h left), **lid open**, tunnel Terminal window open. `caffeinate` was started by your session.

## Adam (human), from 8:45
- [ ] **8:45:**
  - `caffeinate -dims` in a Terminal tab.
  - `curl https://<tunnel>/health`. If it fails, restart `cloudflared tunnel --no-autoupdate --url http://localhost:8000`, give your session the new URL (it updates `PUBLIC_BASE` and restarts), and DM it to Ryan and Nabil.
- [ ] **9:00:** standup. Read the morning report and the plan confirmations, and confirm the submission deadline.
- [ ] **9:15: merge** the PRs the report lists: **#13 only if Ryan OKs it**, plus the AI quality PR. Then `git pull`.
- [ ] **9:20: iPhone build.**
  - On the phone: Settings → Privacy & Security → **Developer Mode** on, plug into the Mac, trust it.
  - `cd ~/dresstoimpress/app && open ios/Runner.xcworkspace` → Runner → Signing & Capabilities → Team = **Personal Team**, Bundle Identifier = something unique (e.g. `com.acwarob.dresstoimpress`).
  - Run `flutter devices`, then `flutter run -d <phone> --release`.
  - Trust the developer: Settings → General → VPN & Device Management.
  - Enter the URL + key in the app's settings.
  - **Done when:** the feed loads on the phone with photos.
- [ ] **9:40: photos.**
  - **Body:** 1 full-body photo, front-facing, plain wall, fitted clothes, head to feet. Then `python -m scripts.set_body_photo ~/dti-photos/body.jpg`.
  - **Closet:** 6–8 real clothes, one per photo, flat, in daylight (≥2 bottoms, 2 tops, 1 shoes, 1 outerwear) → `~/dti-photos/closet/`. Then `python -m scripts.load_closet ~/dti-photos/closet --replace-seed`. Your session can run both.
  - Then `python -m scripts.precompute_tryons --limit 10`.
  - **Done when:** `GET /closet/u_demo` shows your items with correct labels, and feed reasons mention them.
- [ ] **Credits:** check Anthropic (console → Billing; top up $10 if under $5) and Gemini billing.

## After 10:00
12:00 checkpoint A on your iPhone · 15:30 B · 17:00 freeze + rebuild · 17:30 dry run (you present the AI parts: closet → reasons → try-on → complete the look + Fit Score → shop a friend's fit; record the phone screen as the backup video) · 19:00 `staging` → `main`. Run `python -m scripts.reset_demo` before each dry run.
