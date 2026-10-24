# dresstoimpress — progress and direction

Last updated: Fri Oct 23, 8:00 PM PT. Branch: `adam/ai-pipeline` (Adam's AI lane). `main` has only the README so far.

## Where we are

The backend skeleton and the whole AI pipeline are built, tested (22 tests) and verified on real models.

| Area | Status | Notes |
| --- | --- | --- |
| FastAPI skeleton + shared data contract | Done | `backend/app/main.py`, `backend/app/models.py` |
| Closet tagging (`/closet/tag`, `/closet/upload`) | Done, live on Claude Haiku | e.g. "black leather moto jacket" → outerwear, grunge/streetwear, ~3 s |
| Pairing (`/pair`) | Done, live | Budget-first, sorted, reasons like "Perfect Y2K top for your baggy jeans" |
| Shop the fit (`/ai/shop-fit`) | Done | Strict matching (same type + category); live store search via Apify when nothing matches (needs `APIFY_TOKEN`) |
| Fit photo auto-tagging (`/ai/tag-fit`) | Done, live | Lists every item in an outfit photo, e.g. "red graphic t-shirt", "oversized black jacket" |
| Style memory (Moss) | Done, needs Moss keys | Falls back to swipe history until then |
| Try-on (`/tryon`) | Done, live | Gemini Flash Lite image, ~5 s, keeps body and pose; outfit-board fallback if images fail |
| Cost controls | Done | Haiku default, caching, $5 cap, `GET /ai/usage`; real cost so far < $0.01 |
| Gemini fallback | Done | If Claude fails (credits, network), tagging/pairing use Gemini automatically |
| Commerce: ingest, `/feed`, `/swipe`, `/cart`, `/wishlist`, `/checkout` | Done (merged to `staging`) | Nabil. 370 real H&M + Uniqlo products on his machine; Nessie pending key |
| Fit Check posts + `/fitcheck/{id}/shop` | Next | Nabil |
| Demo person photo | Done | AI-generated fictional person, `backend/assets/demo_body.jpg`, set by `seed_demo` |
| iPhone app (FlutterFlow) | Not started in repo | Ryan |

## Handoffs (Fri 8 PM): what to do next, on `staging`

Everything below is already merged on `staging` and passes `cd backend && pytest -q` (99 tests). Branch off `staging`, PR back into `staging`.

### Adam → Nabil
1. **Fit Check backend:** store posts (`POST /fitcheck`, `GET /fitcheck/feed`) and make `GET /fitcheck/{post_id}/shop?user_id=` return `ai.service.shop_fit(user_id, post["tagged"])`. To pre-fill a post's tags from its photo: `ai.service.tag_fit(photo_url)`.
2. **Run the shared demo backend** on your machine (you have the 370 products): `python -m scripts.seed_demo` (adds the demo user and their photo), then a public URL (ngrok or cloudflared), set `PUBLIC_BASE` to it in `.env`, restart, and send the URL to Ryan.
3. **Tag the catalog once:** re-run ingest without `--no-tag` so products get `style_tags`/`label`/`pattern` (better pairing; about $0.07 for 370 on Haiku).
4. **Add shoes** to ingest (e.g. H&M `"sneakers, boots"`); there are none yet, so complete-the-look can only fill shoes from the closet.
5. **Keys in the shared `.env`:** `APIFY_TOKEN` (also powers Fit Check live search), `NESSIE_API_KEY` when you have it. Adam can send the Anthropic and Gemini keys.

### Adam → Ryan
1. **Point FlutterFlow's API group at the shared URL** from Nabil (until then: run the backend locally with `MOCK_AI=1`, or use `seed_demo` data). Demo user: `u_demo`.
2. **Onboarding:** body photo → `POST /users/{id}/body-photo` (multipart); closet photos → `POST /closet/upload` (returns the item with a `label` like "black cargo pants" — show it).
3. **Swipe feed:** `GET /feed?user_id=` (cards include `reason`, e.g. "goes with your baggy jeans" — show it under the price); swipes → `POST /swipe {user_id, product_id, action: like|save|discard, size?}`.
4. **Product sheet:** `POST /size` → highlight the suggested size in the picker, grey out `in_stock: false`; "Try it on" → `POST /tryon` (≈5 s, show a spinner; if `mode` is `collage` it's an outfit board, not AI); "Complete the look" → `POST /complete-look {user_id, product_id, budget_usd?}`.
5. **Cart + checkout:** `GET /cart/{user_id}` (grouped by retailer), `POST /checkout/{user_id}`.
6. **Fit Check:** after taking the photo, `POST /ai/tag-fit {image_url}` to pre-fill tags; "Shop this fit" → Nabil's `/fitcheck/{post_id}/shop` (or `POST /ai/shop-fit {viewer_id, photo_url}` until it exists).
7. Push a `RYAN.md` (screens done, what you need) like `NABIL.md` / `ADAM.md`, and your Figma/Notability links, on `RyanFrontendking` → PR into `staging`.
8. **Your gallery + description request (`ryan-nabil.md`):** the fields are on `staging` now (`images[{url, kind}]`, `description`); Nabil fills them in ingest and adds the wishlist PUT/DELETE routes.

## Who owns what (no overlap)

| Area | Owner | Not touched by |
| --- | --- | --- |
| `backend/app/ai/*`, `scripts/eval_tagger.py`, `scripts/precompute_tryons.py`, `docs/` | Adam | Nabil, Ryan |
| Main product ingest from Apify (category pages → `products`), `/feed`, `/swipe`, `/cart`, `/checkout`, Fit Check posts storage, Devpost | Nabil | Adam, Ryan |
| FlutterFlow app, Figma, Notability, demo video, slides | Ryan | Adam, Nabil |
| `backend/app/models.py` (shared contract) | Shared: announce in group chat before changing | |

Boundaries:
- Adam's live search (`app/ai/finder.py`) only looks up **items from Fit Check posts** that the catalog doesn't have. It writes them to `products` with `source: "live_search"` and the same Product fields. Nabil's ingest stays the main source of the feed.
- `/feed` (Nabil) calls `ai.service.pair()`; `/swipe` (Nabil) calls `ai.memory.record_swipe()`; `GET /fitcheck/{post_id}/shop` (Nabil) returns `ai.service.shop_fit(viewer_id, post["tagged"])`. Adam doesn't edit those routes.
- Gemini-drafted modules (size advisor, outfit rules) land in `backend/app/ai/` via Adam.

## Schema: unified on `staging` (see docs/schema.md)

Proposal for the team: one Product shape (Nabil's ids and sizes-with-stock, singular categories and `price_usd`/`product_url` names). Everyone merges into `staging` first.

### Earlier drafts

Nabil's proposal (branch `nabil`, `NABIL.md`) differs from `backend/app/models.py`: `price`/`currency` vs `price_usd`, `url` vs `product_url`, plural categories (`tops`) vs singular (`top`), single `color` vs `colors[]`, sizes as `[{name, inStock}]` vs `["S"]`, and `tags {style[], formality: "casual"}` vs `style_tags[]` + `formality` 1–5.

**The AI code reads both** (`backend/app/ai/compat.py`), so either choice works for Adam's side. What Nabil asked for is ready:
- `POST /products/tag {image_url}` returns tags for a product image, including his exact `tags` object (`category: "tops"`, `style[]`, `formality: "casual"`). Cached per image, so tagging the catalog once is cheap (Haiku, ~$0.0002 per product).
- `POST /pair` results now include `id` (same as `product_id`) plus `reason`.
- Pick one shape for Ryan's app so the UI reads one set of names; Adam suggests keeping Nabil's richer `sizes` with `inStock`.

## Blockers

2. **Apify token** for live item search (same token Nabil uses for ingest; `APIFY_TOKEN` in `.env`).
3. **Moss keys** from the Cal Hacks Moss Starter Pack (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`).
4. **Shared backend URL.** The server runs on Adam's Mac at `localhost:8000`; it needs a tunnel or deploy so the app can reach it.

## Next (timeline, Pacific)

| When | Owner | Task |
| --- | --- | --- |
| Fri night | Nabil | Apify ingest into `products` (same Product fields as `models.py`), `/feed`, `/swipe` |
| Fri night | Ryan | FlutterFlow screens on mock data (`MOCK_AI=1` works without keys) |
| Fri night | Adam | Run `scripts/eval_tagger.py` on 10 of our own photos; tune prompts; integrate Gemini-built size advisor + outfit rules |
| Fri 11 PM | Nabil + Adam | Merge commerce router; `/feed` calls `ai.service.pair()`, `/swipe` calls `ai.memory.record_swipe()` |
| Sat 8 AM–12 PM | All | Public backend URL; app wired to real API; **end-to-end run at noon** |
| Sat afternoon | Adam | Real try-on on all three of us (once Google clears); Moss keys in |
| Sat 10 PM | Adam | `scripts/precompute_tryons.py --user u_demo` with real demo photos |
| Sat 11 PM | Nabil | Devpost draft (Adam writes the "how we use Claude / where it can go wrong" section) |
| Sun 9 AM | All | Final submit |

## Direction

- **Demo story:** swipe real products → each card names the closet item it goes with → try it on → one checkout across stores → Fit Check post a judge can shop in one tap.
- **Tracks the AI lane carries:** Anthropic (Claude does tagging and pairing; we can explain failure modes: wrong tags are user-editable, budget filtered server-side, no body reshaping), Moss (style memory), and the AI half of Meta (shop-the-fit for friends' posts).
- **Keep it cheap and robust:** Haiku everywhere, caches on, caps on, and every AI call has a non-AI fallback so the demo never hard-fails.
- **Nice to have if time:** size advisor ("we pick your size"), outfit rules scorer for smarter offline ranking (both being drafted in Gemini by Adam), voice via Cartesia only if ahead.

## How to plug in (Nabil, Ryan)

- Run it: see `backend/README.md` (venv, `.env`, `python -m scripts.seed_demo`, `uvicorn app.main:app`).
- Endpoints and request/response shapes: `backend/README.md` table, or `http://localhost:8000/docs`.
- New optional field: `ClosetItem.label` (e.g. "black cargo pants") — show it on the closet screen.
- Giving an AI assistant context: paste `docs/ai-context.md` first.
