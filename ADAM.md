# ADAM.md: AI pipeline status

What Nabil and Ryan need from the AI layer. Newest changes at the top of the changelog. Field names: [`docs/schema.md`](docs/schema.md); notes to each of you: `ADAM_TO_NABIL.md`, `ADAM_TO_RYAN.md`.

**Last updated:** Fri Oct 23, 2026, ~8:45 PM PT. Branch: `adam/ai-pipeline` → PR into `staging`.

---

## TL;DR

- **Shared backend is live on Adam's Mac behind a Cloudflare tunnel.** The URL and `X-DTI-Key` are shared privately, never in Git. The full demo journey passes through the tunnel: `scripts/smoke_e2e.py --base <url> --key <key>` → **10/10**, including a real Nessie checkout (`paid`).
- **Catalog: Nabil's 418 real H&M + Uniqlo products, all AI-tagged** (label, pattern, formality, style tags), for ~$0.07. Committed in `seed/products.json`.
- **Fit Check shopping works end to end.** The old Apify actor died (404), so live search now uses Nabil's H&M actor: 3 items in ~8 s, cached after.
- **New:** Fit Score (`POST /ai/fit-score`), closet list/delete, duplicate detection on upload, real H&M size formats.
- **193 tests.** AI spend so far ≈ $0.08 of the $5 cap.

## Endpoints

| Method | Path | For | Returns |
| --- | --- | --- | --- |
| POST | `/closet/upload` · `/closet/tag` | Ryan (closet) | ClosetItem with `label` and **`duplicate_of`** (id of an item it probably already has, or null) |
| GET | `/closet/{user_id}` | Ryan (closet screen) | `[ClosetItem]` |
| DELETE | `/closet/{user_id}/{item_id}` | Ryan ("remove duplicate") | `{deleted}`; 404 if it isn't theirs |
| POST | `/products/tag` | Nabil (ingest) | product tags + legacy `tags` object; optional `hint` = product name |
| POST | `/pair` | Nabil (`/feed`) | `[{id, product_id, score, reason, pairs_with}]`, best first |
| POST | `/size` | Ryan (size picker) | `{size, confidence, reason}`; reads S/M/L, XXS–3XL, `28/32`, `28inch`, US women's 0–24, shoes |
| POST | `/tryon` | Ryan | `{image_url, cached, mode}` (`ai`, or `collage` fallback) |
| POST | `/complete-look` | Ryan (product sheet) | outfit from closet + catalog within budget |
| POST | `/ai/fit-score` | Ryan (Fit Check post, complete-the-look) | `{score 0-100, verdict, notes, breakdown}`; free, instant |
| POST | `/ai/tag-fit` | Ryan / Nabil (Fit Check) | items seen in an outfit photo |
| POST | `/ai/shop-fit` | Nabil (`/fitcheck/{id}/shop`) | buyable products + reasons |
| POST | `/users/{id}/body-photo` | Ryan (onboarding) | `{body_photo_url}` |
| GET | `/ai/usage` | anyone | AI spend so far |

## What I need from you

### Nabil
- Merge PR `adam/ai-pipeline` → `staging` (I can't merge my own PRs), then `staging` → `main` when you're happy.
- Optional: pass `hint=p["name"]` in `ingest.tag()` → `tag_product(p["image_url"], hint=...)`. That's how the snapshot was tagged; H&M model shots tag much better with it.

### Ryan
- Closet screen: `GET /closet/{user_id}`; on upload, if `duplicate_of` is set, show "Looks like you already have this" with **Keep both** / **Remove** (`DELETE /closet/{user}/{id}`).
- Fit Score badge on Fit Check posts and the complete-the-look sheet: `POST /ai/fit-score`.

## Blockers
- None for the demo. Moss keys would turn on semantic style memory; until then it uses swipe + wishlist history.
- The tunnel URL changes whenever Adam restarts `cloudflared`; he'll repost it.

## Changelog
- **Oct 23, 8:45 PM:** Synced `staging` and my branch with `main` (Nabil's PR #3: Nessie, Fit Check, 418 products). Tagged the whole catalog (`scripts/tag_catalog.py`, product-name hint). Fit Check live search rebuilt on Nabil's H&M actor, searches run in parallel. `colors.py` (normalized color matching, closet duplicates) and `outfit_score.py` (Fit Score), both drafted in Gemini and reviewed. Closet list/delete. Sizing reads real H&M sizes. Wishlist saves feed style memory. JSON store writes are atomic. Tests can no longer touch the real store or real APIs.
- **Oct 23, 8:05 PM:** Merged Nabil's commerce into `staging` (99 tests), end-to-end smoke 10/10 (`scripts/smoke_e2e.py`), try-on prompt fixed for model-photo references, demo person photo, first-merge checklist.
- **Oct 23, 7:55 PM:** Google billing cleared: real AI try-on verified (4.6 s). Outfit-board fallback, `/complete-look`.
- **Oct 23, 7:40 PM:** Unified schema on `staging`; `/size` and rules fallback (drafted in Gemini); Claude thinking disabled for JSON tasks (fixed cut-off pairing replies).
- **Oct 23, 7:30 PM:** Fit photo tagging, strict item matching, live store search, `/products/tag`, compat layer for NABIL.md's shape.
- **Oct 23, 7:05 PM:** Closet labels, natural reasons, cost controls (Haiku default, caches, $5 cap), Gemini fallback.
- **Oct 23, 6:10 PM:** FastAPI skeleton, tagging, try-on, pairing.
