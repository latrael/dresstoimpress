# dresstoimpress — progress and direction

Last updated: Fri Oct 23, 7:20 PM PT. Branch: `adam/ai-pipeline` (Adam's AI lane). `main` has only the README so far.

## Where we are

The backend skeleton and the whole AI pipeline are built, tested (22 tests) and verified on real models.

| Area | Status | Notes |
| --- | --- | --- |
| FastAPI skeleton + shared data contract | Done | `backend/app/main.py`, `backend/app/models.py` |
| Closet tagging (`/closet/tag`, `/closet/upload`) | Done, live on Claude Haiku | e.g. "black leather moto jacket" → outerwear, grunge/streetwear, ~3 s |
| Pairing (`/pair`) | Done, live | Budget-first, sorted, reasons like "Perfect Y2K top for your baggy jeans" |
| Shop the fit (`/ai/shop-fit`) | Done | Matches Fit Check tags to products, ranks vs viewer's closet |
| Style memory (Moss) | Done, needs Moss keys | Falls back to swipe history until then |
| Try-on (`/tryon`) | Built, blocked | Google project billing still processing; images return 403 |
| Cost controls | Done | Haiku default, caching, $5 cap, `GET /ai/usage`; real cost so far < $0.01 |
| Gemini fallback | Done | If Claude fails (credits, network), tagging/pairing use Gemini automatically |
| Commerce: Apify feed, cart, Nessie checkout, Fit Check backend | Not started | Nabil |
| iPhone app (FlutterFlow) | Not started in repo | Ryan |

## Blockers

1. **Google billing for try-on images.** The new Gemini project ("DRESStoIMPRESS") is locked while Google processes the billing account. Adam is waiting; retry with `python /tmp/gem_img.py` or any `/tryon` call.
2. **Moss keys** from the Cal Hacks Moss Starter Pack (`MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`).
3. **Shared backend URL.** The server runs on Adam's Mac at `localhost:8000`; it needs a tunnel or deploy so the app can reach it.

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
