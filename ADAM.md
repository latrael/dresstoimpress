# ADAM.md: AI pipeline status

What Nabil and Ryan need from the AI layer. Newest changes at the top of the changelog. Full detail: [`docs/progress.md`](docs/progress.md); field names: [`docs/schema.md`](docs/schema.md).

**Last updated:** Fri Oct 23, 2026, 8:05 PM PT. Branch: `adam/ai-pipeline`, merged into `staging`.

---

## TL;DR

- **All AI endpoints are built and tested (67 tests)** and verified on real models: tagging, pairing, Fit Check tagging and shopping, size advice.
- **Claude Haiku is live**; spend so far is under $0.01, with a hard $5 cap and caching everywhere.
- **AI try-on works** (Gemini Flash Lite image, ~5 s, body and pose unchanged); if images ever fail it falls back to an outfit board.
- **The AI code reads both product shapes**, so nothing breaks while ingest moves to the unified schema.

## First merge: `staging` → `main` (Nabil, please confirm in NABIL.md)

Adam's check at 8:05 PM, on `staging` @ latest:

- [x] `cd backend && pytest -q` → 99 passed (Adam's AI + Nabil's commerce/ingest)
- [x] `python -m scripts.smoke_e2e` against a running server → **10/10**: health, feed with pairing reasons, size advice, AI try-on, complete the look, swipe like → cart, cart grouped by store, checkout, Fit Check tag + shop, AI usage
- [x] `nabil` has no commits that aren't on `staging`; schema locked to `models.py` on both sides
- [ ] **Nabil confirms** nothing local is unpushed and he's OK merging (reply under "What I need from you → Adam" in NABIL.md, or in the group chat)

Known gaps (not merge blockers; `main` only has the README today): Nessie key (checkout returns `pending_nessie`), public backend URL, Fit Check posts storage, no shoes in the catalog, Ryan's app not in the repo yet. Feed's first load takes ~7 s while Claude ranks; later loads are cached.

Proposed: merge `staging` → `main` with a PR once Nabil confirms; after that `main` = last known-good demo, and we keep working through `staging`.

## Endpoints

| Method | Path | For | Returns |
| --- | --- | --- | --- |
| POST | `/closet/tag` · `/closet/upload` | Ryan (closet screen) | ClosetItem with `label`, e.g. "black leather moto jacket" |
| POST | `/products/tag` | Nabil (ingest) | product tags + legacy `tags` object |
| POST | `/pair` | Nabil (`/feed`) | `[{id, product_id, score, reason, pairs_with}]`, best first |
| POST | `/size` | Ryan (size picker) | `{size, confidence, reason}` |
| POST | `/tryon` | Ryan | `{image_url, cached, mode}` (`ai` or `collage` fallback) |
| POST | `/ai/tag-fit` | Ryan / Nabil (Fit Check) | items seen in an outfit photo |
| POST | `/ai/shop-fit` | Nabil (`/fitcheck/{id}/shop`) | buyable products + reasons |
| POST | `/users/{id}/body-photo` | Ryan (onboarding) | `{body_photo_url}` |
| GET | `/ai/usage` | anyone | AI spend so far |

## What I need from you

### Nabil
- Call `ai.memory.record_swipe(user_id, product, action)` from `/swipe` (style memory).
- `/feed`: send candidates to `ai.service.pair()`; `/fitcheck/{post_id}/shop`: return `ai.service.shop_fit(viewer_id, post["tagged"])`.
- Your `APIFY_TOKEN` in `.env` for Fit Check live search.

### Ryan
- Show `ClosetItem.label` on the closet screen; show `reason` on feed cards.
- Body photo upload in onboarding (`/users/{id}/body-photo`).

## Blockers
- Moss keys (Starter Pack) for style memory; falls back to swipe history meanwhile.
- A shared backend URL (tunnel or deploy) so the app can reach the API.

## Changelog
- **Oct 23, 8:05 PM:** Merged Nabil's commerce into `staging` (99 tests), end-to-end smoke 10/10 (`scripts/smoke_e2e.py`), try-on prompt fixed for model-photo references, demo person photo, first-merge checklist.
- **Oct 23, 7:55 PM:** Google billing cleared: real AI try-on verified (4.6 s). Outfit-board fallback, `/complete-look`.
- **Oct 23, 7:40 PM:** Unified schema on `staging`; `/size` and rules fallback (drafted in Gemini); Claude thinking disabled for JSON tasks (fixed cut-off pairing replies).
- **Oct 23, 7:30 PM:** Fit photo tagging, strict item matching, live store search, `/products/tag`, compat layer for NABIL.md's shape.
- **Oct 23, 7:05 PM:** Closet labels, natural reasons, cost controls (Haiku default, caches, $5 cap), Gemini fallback.
- **Oct 23, 6:10 PM:** FastAPI skeleton, tagging, try-on, pairing.
