# dresstoimpress backend

One FastAPI service. Every outside call (Claude, Gemini, Apify, Nessie) goes through it; keys live only here.

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add keys, or set MOCK_AI=1 to build without them
python -m scripts.seed_demo # demo user u_demo + 3 closet items + 5 products
uvicorn app.main:app --reload --port 8000
```

Docs at http://localhost:8000/docs. Tests: `pytest -q` (runs in mock mode, no keys).

For phones at the venue, expose it: `ngrok http 8000`, then set `PUBLIC_BASE` to the ngrok URL.

## AI endpoints (Adam)

| Endpoint | Request | Response |
| --- | --- | --- |
| `POST /closet/tag` | `{user_id, image_url}` | ClosetItem (422 `not_clothing` if it isn't) |
| `POST /tryon` | `{user_id, product_ids[], closet_item_ids[]}` | `{image_url, cached}` |
| `POST /pair` | `{user_id, candidate_product_ids[]}` (empty = all unswiped products) | `[{product_id, score, reason, pairs_with[]}]` |
| `POST /closet/upload` | multipart `user_id`, `file` (jpeg/png/webp/heic, ≤10 MB) | ClosetItem (saves, then tags) |
| `POST /users/{user_id}/body-photo` | multipart `file` | `{body_photo_url}` |
| `POST /ai/shop-fit` | `{viewer_id, tagged[{label, retailer?, product_id?}]}` or `{viewer_id, photo_url}` | Products + `reason`, `pairs_with`, `score`, `matched_tag` |
| `POST /ai/tag-fit` | `{image_url}` (an outfit photo) | `[{label, category, color, pattern, style_tags, brand, retailer}]` — use as a post's `tagged` |

- **Tagging:** Claude vision → JSON, validated and clamped to the contract, retried once on bad JSON.
- **Try-on:** Gemini Flash image with the user's body photo + garment images; prompt forbids reshaping the body. Results cached by user + sorted ids and served from `/static/tryon/`.
- **Pairing:** budget matches first, top 50 sent to Claude with closet + style memory; hallucinated ids are dropped; falls back to budget/price ranking if Claude fails or the closet is empty.
- **Style memory:** with `MOSS_PROJECT_ID`/`MOSS_PROJECT_KEY` set, swipes are indexed in Moss (one index per user) and pairing retrieves the most relevant likes/discards; otherwise it reads recent swipes. **Nabil: call `ai.memory.record_swipe(user_id, product, action)` from `/swipe`.**
- **Shop the fit:** matches each tagged item to products strictly (same type word and category, plus a descriptor, color or retailer). If the catalog has nothing, it searches the stores live through Apify (`APIFY_TOKEN`), then ranks matches against the viewer's closet. **Nabil: `GET /fitcheck/{post_id}/shop` can return `ai.service.shop_fit(viewer_id, post["tagged"])`.**
- **Images:** fetched server-side and sent to Claude as base64 (retailer CDNs block outside fetchers; localhost isn't reachable). Only http(s) URLs accepted from the API.

## Cost

The Claude API is billed per token, separate from any Claude subscription. Defaults keep it near zero:

- **Haiku 5.5 for everything** ($0.10 / $0.50 per million input/output tokens). A closet tag is roughly 2k tokens, so a fraction of a cent. Set `CLAUDE_PAIR_MODEL=claude-sonnet-5-5` only if pairing quality needs it.
- **Caching:** tags cached per image URL, pairings for 10 min per user + candidate set, try-ons forever.
- **Hard caps:** `AI_BUDGET_USD` (default $5) and `MAX_TRYONS` (default 150). Past either, endpoints use their non-AI fallbacks instead of failing.
- **Watch it:** `GET /ai/usage` shows calls, tokens and estimated spend.
- **Building UI?** `MOCK_AI=1` spends nothing.

## Scripts

```bash
python -m scripts.seed_demo                       # demo data
python -m scripts.eval_tagger ~/Desktop/closet    # real tagger on a folder of photos (needs ANTHROPIC_API_KEY)
python -m scripts.precompute_tryons --user u_demo # warm try-on cache before judging (needs GEMINI_API_KEY)
```

## Where things live

```
app/models.py     shared data contract (don't rename fields without telling the team)
app/store.py      JSON-file store (default) or Firestore (USE_FIRESTORE=1)
app/ai/           Adam's pipeline: prompts, llm wrappers, service, router, memory, finder (item matching + live search)
scripts/          seed_demo.py
```

Nabil: add a `commerce` router for `/feed /swipe /cart /checkout /fitcheck` and include it in `app/main.py`. `/feed` should call `ai.service.pair()` to order cards and attach `reason` + `pairs_with`.
