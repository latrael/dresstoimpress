# Try-on budget (sprint 4 §10.2 decision)

Model: `gemini-3.1-flash-lite-image` (env `GEMINI_IMAGE_MODEL`). Image output is billed at $30 per 1M output tokens; a 1024px image is ~1,290 tokens, so **≈ $0.039 per try-on** (call it 4¢). Text prompt tokens add well under 0.1¢.

| Cap | Images | Cost |
| --- | --- | --- |
| `MAX_TRYONS=150` (old server-wide default) | 150 | ≈ $5.85 |
| **`MAX_TRYONS=400` (new default)** | 400 | ≈ $15.60 |
| `PREFETCH_PER_USER_DAY=20` × 4 users | 80 / day | ≈ $3.12 / day |

Decisions:
- `MAX_TRYONS` default raised 150 → **400** (`backend/app/ai/llm.py`). Override per server with the env var.
- `PREFETCH_PER_USER_DAY` stays **20** (`backend/app/ai/feed_tryon.py`): the first posts of each session plus wherever the user actually scrolls. Past it the card gets `tryon.status = "unavailable"` with the free collage.
- Only wearable closet picks go into the render; accessories stay in the 2×2 grid.
- `AI_BUDGET_USD` ($5) only meters Claude text calls; Gemini images are metered by `MAX_TRYONS` alone.

Measured on the shared server (Sun 1:10 AM): `POST /feed/u_adam/tryons` returns in 10 ms; two renders went `pending → ready` in ~15–20 s with the pool of 2.
