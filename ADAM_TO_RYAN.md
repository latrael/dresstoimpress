# ADAM_TO_RYAN.md

Notes from Adam (AI lane) to Ryan (app). Newest at the top. Everything here is on `staging`.

**Last updated:** Fri Oct 23, 2026, ~8:25 PM PT

---

## Read first

- **Gallery + description are now in the shared contract** (your `ryan-nabil.md` request): `Product.images: [{url, kind: "product" | "retailer_model"}]` and `Product.description: string | null`. Both optional; `image_url` stays the primary photo. Nabil fills them in ingest. Your fixture's extra photos/descriptions can map straight onto these names.
- **Backend:** hosted on Adam's Mac behind a tunnel. The URL and the shared key are sent **privately** (group chat), never in Git — the repo is public.
- **Every request needs the header `X-DTI-Key: <key>`** (set it once on the FlutterFlow API group). Images under `/static/...` and `GET /health` need no header, so image widgets can load try-on and demo photos directly.
- **Demo user:** `u_demo` (has a closet: baggy jeans, black cargos, white sneakers, and an AI-generated full-body photo for try-on).

## Calls for your screens

| Screen | Call | Notes |
| --- | --- | --- |
| Feed | `GET /feed?user_id=u_demo&limit=20` | cards = Product + `reason` ("goes with your baggy jeans"), `score`, `pairs_with`. First load ~7 s (AI ranking), then cached |
| Save / cart / skip | `POST /swipe {user_id, product_id, action: like\|save\|discard, size?}` | any `/swipe` removes the item from the feed (per your notes, don't call it for photo swipes); idempotent wishlist routes are with Nabil |
| Size picker | `POST /size {product_id, height_cm, weight_kg, fit?}` | → `{size, confidence, reason}`; highlight `size`, grey out `in_stock: false` |
| Try it on | `POST /tryon {user_id, product_ids: [id]}` | ~5 s first time, instant after. `mode: "ai"` = real try-on; `"collage"` = outfit board (label it) |
| Complete the look | `POST /complete-look {user_id, product_id, budget_usd?}` | `{items: [{source: closet\|catalog, id, category, label, reason}], new_items_total_usd, missing}` |
| Cart / checkout | `GET /cart/{user_id}`, `POST /checkout/{user_id}` | grouped by retailer |
| Closet | `POST /closet/upload` (multipart `user_id`, `file`) | returns the item with `label` ("black leather moto jacket") |
| Onboarding photo | `POST /users/{user_id}/body-photo` (multipart `file`) | |
| Fit Check | `POST /ai/tag-fit {image_url}` → tags; `POST /ai/shop-fit {viewer_id, photo_url}` → buyable items | Nabil's `/fitcheck/...` routes coming |

## Known limits
- Catalog is H&M + Uniqlo, no shoes yet (complete-the-look fills shoes from the closet).
- Checkout returns `pending_nessie` until Nabil's Nessie key is wired.
