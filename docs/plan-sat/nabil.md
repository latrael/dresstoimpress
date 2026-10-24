# Nabil: 1:00 AM – 10:00 AM

**Lane:** commerce backend, backup server, Devpost, demo script, sponsor write-ups. Team timeline: [README.md](README.md).

**Nabil is asleep 1:00–9:00.** The overnight items are for **Nabil's coding agent, only if he started it before bed** (prompt in [README.md](README.md), "Before bed"). None needs a human. **Whatever isn't done by 9:00 moves to 9:15, same order.** The backup server needs his laptop awake; if it isn't, that's the first thing at 9:15. Please write "Plan confirmed" (or changes) at the top of `NABIL_TO_ADAM.md`.

## Overnight (Nabil's agent, if running; skip anything that needs a person, and note it in the morning report)
- [ ] **1:00–2:00: backup server on Nabil's laptop.** If Adam's Mac dies, we swap URLs.
  1. **Install:** `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
  2. **`.env`** (never committed):
     - `APIFY_TOKEN`, `NESSIE_API_KEY`, the Anthropic key from Adam.
     - `GEMINI_API_KEY` (optional; ask Adam).
     - The **same** `API_SHARED_KEY` as Adam's.
  3. **Seed:** `.venv/bin/python -m scripts.seed_demo && .venv/bin/python -m scripts.load_products --replace && .venv/bin/python -m scripts.seed_fitcheck`. That order matters: `load_products` drops seed_demo's 5 placeholder products.
  4. **Run:** `.venv/bin/uvicorn app.main:app --port 8000` + `cloudflared tunnel --no-autoupdate --url http://localhost:8000`, then set `PUBLIC_BASE` to that URL and restart.
  5. **Check:** `.venv/bin/python -m scripts.smoke_e2e --base <backup tunnel> --key <key>` → 10/10. Put the result (not the URL) in `NABIL_TO_ADAM.md`. Leave it stopped or running, your call.
- [ ] **2:00–3:00: checkout evidence for Capital One.** On the **shared** server, as a throwaway user (`u_test_checkout`, not u_demo):
  - 3 checkouts: H&M only, Uniqlo only, mixed. Each returns `paid`, and each shows in Nessie (`GET /accounts/{id}/purchases`).
  - Save the purchase ids for the judges, then empty that user's cart.
- [ ] **3:00–5:00: `docs/devpost.md` draft.**
  - **Sections:** inspiration · what it does · how we built it (Flutter app; FastAPI; Apify ingest H&M + Uniqlo, 418 products; Capital One Nessie checkout; AI: paste `docs/ai-writeup.md`) · challenges · accomplishments · what's next.
  - **Sponsor tracks:** list the ones we're entering, with 2–3 sentences each on exactly where they're used. Confirm the list against the hacker guide; **Visa is off-limits for us**.
- [ ] **5:00–6:30: `docs/demo-script.md`,** a 3-minute script.
  - The hook (one line), then the flow step by step: who talks, what's on screen, and the route behind it.
  - A fallback per step (README "If something breaks"), and the closing line.
- [ ] **6:30–7:30: `scripts/post_real_fits.py <folder>`** (your lane), ready for the morning photos.
  - Posts each photo as u_adam / u_nabil / u_ryan via the Fit Check create path (AI tags pre-fill), then removes the picsum seed posts `fc_seed_1..3`.
  - Test it with fixtures; don't post real photos yet.
- [ ] **7:30–8:30:** answer Ryan's agent's commerce asks; final checks.
- [ ] **8:30: morning report** at the top of `NABIL_TO_ADAM.md`: done, not done, and what Nabil does at 9:15.

## Nabil (human), 9:00–10:00
- [ ] 9:00 standup.
- [ ] 9:15: merge PRs that passed their tests (yours, Adam's; Ryan's with Ryan).
- [ ] **9:30:** take 3 real outfit photos at the venue (with everyone's OK) → `python -m scripts.post_real_fits <folder>`. Fix wrong tags with `PATCH /fitcheck/{id}/tags`. **Done when:** u_demo's Fit Check feed shows 3 real fits and "shop this fit" returns sensible items.
- [ ] Check the backup server still answers (or restart it), and DM its URL to Adam.

## After 10:00
12:00 checkpoint A (confirm the purchase in Nessie) · 13:30 Devpost final pass · 15:30 B · 17:00 freeze · 17:30 dry run (you run the clock + script) · 19:00 Devpost draft complete + `staging` → `main`.
