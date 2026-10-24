# ADAM_TO_NABIL.md

Replies from Adam (AI lane) to Nabil (commerce lane). Newest at the top. Nabil's notes: `NABIL_TO_ADAM.md`.

**Last updated:** Fri Oct 23, 2026, ~8:25 PM PT · everything below is on `staging`

---

## Decided: shared backend runs on Adam's Mac

- Adam's Mac hosts it (Anthropic + Gemini keys, working Google billing, real try-on). Tunnel URL + shared key go to you and Ryan **privately**; never commit them (public repo).
- New on `staging`: `/static` now serves only `uploads/` and `tryon/` (it used to expose the JSON store), and with `API_SHARED_KEY` set every route except `/health` and `/static/...` needs header `X-DTI-Key`. Your routes are covered automatically; nothing to change. Tests: `scripts/smoke_e2e.py --key ...`.
- **Tagging without sharing the Anthropic key:** when your snapshot + `scripts/load_products` PR lands on `staging`, Adam runs the tag pass on his Mac (where the server lives anyway) and pushes the tagged snapshot. If you'd rather tag before snapshotting, say so and Adam sends the key privately.

## Ready for the first merge `staging` → `main`?

Adam's side says yes: `pytest -q` → 101 passed (your commerce + ingest + AI), and `python -m scripts.smoke_e2e` against a running server → 10/10 (feed with reasons, size, AI try-on, complete the look, swipe → cart, cart by store, checkout, Fit Check). Checklist in `ADAM.md`.
**Please confirm** in `NABIL_TO_ADAM.md`: nothing local unpushed, and OK to merge. Then Adam opens the PR `staging` → `main`.

## Answers to your questions

1. **Fit Check posts:** your shape `{id, user_id, photo_url, caption, tagged: [FitTag], created_at, likes: [], comments: []}` works. Store `tagged` exactly as `/ai/tag-fit` returns it: `FitTag` now also carries `category`, `color`, `pattern`, `style_tags`, `brand` (they were being dropped before, which weakened strict matching). Then `GET /fitcheck/{post_id}/shop` = `ai.service.shop_fit(viewer_id, post["tagged"])`, no extra fields needed.
2. **`APIFY_TOKEN`:** private is right; the repo is public. `.env` is gitignored on all branches.
3. **Shared backend host:** proposal is Adam's Mac (the Anthropic + Gemini keys and the Google billing are there; real try-on works). Adam is confirming the tunnel. When your snapshot PR lands, Adam runs `python -m scripts.load_products` there.
4. **`POST /complete-look`:** Ryan calls it directly from the product sheet ("Complete the look" button), optionally from the cart. `/feed` shouldn't.

## Your points that touch my code

- **`/feed` → `pair(..., k=min(50, limit*3))`:** measured ~7 s on the first load (Claude writes one reason per ranked item). Suggest: keep a wide pool via `candidate_product_ids` (up to 50) but pass `k=min(24, limit*2)`, so Claude sees 50 and writes ~24 reasons; top up with your unranked cards as you do now. Repeat loads hit the 10-minute cache.
- **Swipes collection:** great, thanks. `pair()` and the memory fallback read it as written (`action` = cart/wishlist/discard).
- **Colour-variant collapse in the feed:** good; `pair()` doesn't care.
- **Tags at ingest:** easiest is to tag on your machine before you snapshot, so the committed snapshot already has `label`/`pattern`/`formality`/`style_tags`. Adam sends you the Anthropic key privately; it's Haiku and the backend hard-stops at `AI_BUDGET_USD` ($5). ~370 × $0.0002 ≈ $0.07.
- **`to_canonical` turning unknown categories into `top`:** fixed. It now raises `ValueError("unknown category ...")`. `Product(**p)` in ingest is fine too.
- **Try-on images:** noted. The try-on prompt now names the garment slot and ignores models/logos/size text in reference photos, so H&M model shots work (verified on a Uniqlo model shot). Garment-only Uniqlo images are still the safest for the demo.

## New on `staging` for Ryan's request (`ryan-nabil.md`)

Added to `Product` (both optional, existing data still validates):
- `images: [{url, kind: "product" | "retailer_model"}]`, same product + colour only, `image_url` stays the primary. `to_canonical` fills a single-photo gallery when only `image_url` exists.
- `description: string | null`, real retailer text as plain text, else null (never a pairing reason).

Over to you for the ingest side: H&M `images[]` + `model_image` (as `retailer_model`), Uniqlo per-colour images, descriptions from raw when present, and the idempotent wishlist routes Ryan asked for (`PUT`/`DELETE /wishlist/{user_id}/items/{product_id}`). Ryan's branch is `RyanFrontendking`.
