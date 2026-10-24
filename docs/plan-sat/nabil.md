# Nabil: Saturday plan (9:00 AM – 7:00 PM)

**Lane:** commerce backend (feed, cart, checkout/Nessie, Fit Check storage, users, search), the backup server, Devpost, the demo script and the sponsor write-ups. Shared timeline: [README.md](README.md). Please write "Plan confirmed" (or your changes) at the top of `NABIL_TO_ADAM.md` by 9:15.

## 8:45: before standup
- [ ] `git pull origin staging` on `nabil`.

## 9:00–9:15: standup

## 9:15–10:15: backup server on your laptop
If Adam's Mac or tunnel dies during the demo, we swap URLs.

1. **Install:** `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
2. **`backend/.env`** (never commit it):
   - Your `APIFY_TOKEN` and `NESSIE_API_KEY`.
   - The Anthropic key Adam sent.
   - `GEMINI_API_KEY`: ask Adam. Optional; without it, try-on falls back to an outfit board.
   - The **same** `API_SHARED_KEY` as Adam's, so the app works unchanged.
   - `PUBLIC_BASE=<your tunnel URL>`, set after step 4.
3. **Seed the data:** `.venv/bin/python -m scripts.seed_demo && .venv/bin/python -m scripts.load_products --replace && .venv/bin/python -m scripts.seed_fitcheck`.
   - `load_products` drops seed_demo's 5 placeholder products, which is why it runs after it.
4. **Run it:**
   - `.venv/bin/uvicorn app.main:app --port 8000`.
   - In another tab: `cloudflared tunnel --no-autoupdate --url http://localhost:8000`, then put that URL in `PUBLIC_BASE` and restart uvicorn.
5. **Check it:** `.venv/bin/python -m scripts.smoke_e2e --base <your tunnel> --key <key>`.
- **Done when:** 10/10 on your laptop. Post "backup ready" and the URL privately. Stop it after (a laptop tunnel that's been idle can be restarted in 2 minutes).

## 10:15–11:15: real Fit Check posts
- [ ] **Photos:** take 3 real outfit photos at the venue (Adam, Ryan, you, with their OK), full body, good light.
- [ ] **Post them** to the shared server as u_adam / u_nabil / u_ryan: `POST /fitcheck` multipart (`user_id`, `file`, `caption`). The AI pre-fills the tags.
  - Fix wrong tags with `PATCH /fitcheck/{id}/tags`.
  - Then remove the 3 picsum seed posts (`fc_seed_1..3`) with `store.delete("fitcheck_posts", id)`, or a small script in your lane.
- **Done when:** u_demo's `GET /fitcheck/feed` shows 3 real fits, and `GET /fitcheck/{id}/shop?user_id=u_demo` returns sensible items for each.

## 11:15–12:00: checkout reliability (Capital One evidence)
- [ ] On the shared server, run 3 checkouts as a throwaway test user (not u_demo): one H&M only, one Uniqlo only, one mixed.
- [ ] **Each returns `paid`.** Check them in Nessie (`GET /accounts/{id}/purchases`) and take screenshots for the Capital One judges.
- [ ] Empty that user's cart after.

## 12:00: Checkpoint A
Ryan does feed → size → cart → checkout on Adam's iPhone. You confirm the purchase shows up in Nessie.

## 12:30–13:30: merge window + lunch
Review and merge PRs that passed their tests (yours, Adam's, Ryan's).

## 13:30–15:30: Devpost draft
- [ ] **Sections:**
  - Inspiration
  - What it does: swipe-to-shop feed that pairs with your closet, try-on, complete the look, Fit Check social + shop the fit, Style DNA, a real checkout
  - How we built it: Flutter app; FastAPI backend; Apify ingest (H&M + Uniqlo, 418 products); Capital One Nessie checkout; Claude Haiku + Gemini (paste `docs/ai-writeup.md` from Adam)
  - Challenges, accomplishments, what's next
- [ ] **Sponsor tracks:** list the ones we enter. Confirm against the hacker guide; **Visa is off-limits for us.** Each gets 2–3 sentences on exactly where it's used (your README section already covers Apify + Nessie).
- [ ] Screenshots: placeholders until Ryan's screens are final.

## 15:30: Checkpoint B

## 15:30–17:00: demo script
- [ ] **A 3-minute script:**
  - The hook (one line).
  - The flow, step by step: who talks, what's on screen, and the route behind it.
  - A fallback for each step (see the README's "If something breaks").
  - The closing line.
- [ ] Share it in the group chat by 17:00 so the dry runs use it.
- [ ] **If Ryan OK'd the `/fit` guest page:** tell Adam the event code privately so he can enable it.
- **Optional, only if everything above is done:** Zara or Mango ingest.

## 17:00–19:00: freeze, dry runs, wrap
- [ ] 17:00 freeze: fixes only.
- [ ] **17:30 dry run #1:** you run the clock and the script. 18:30 fixes, then dry run #2.
- [ ] 19:00: Devpost draft complete, with the backup video link from Adam. Merge `staging` → `main` (or confirm Adam did).
