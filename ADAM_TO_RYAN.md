# ADAM_TO_RYAN.md

Notes from Adam (AI lane) to Ryan (app). Newest at the top. Everything here is on `adam/ai-pipeline` (PR into `staging`) and already running on the shared backend.

**Last updated:** Fri Oct 23, 2026, ~9:15 PM PT

---

## Switching to plain Flutter (Fri ~9:10 PM)

FlutterFlow needs a paid plan for API calls, so we're rebuilding in **plain Flutter**: free, the same widgets you designed with, and it runs in Chrome on your laptop with no Xcode. **Read [`docs/app-plan.md`](docs/app-plan.md)**: setup, who builds which tab, and the timeline.
- A starter is coming in the `flutter-starter` PR (folder `app/`). It has the API client and models for every route, a Settings screen for URL + key, and a first Quick Browse feed following your spec: vertical pages, photo paging inside the picture only, size chips, Add to Cart, heart = wishlist, no `/swipe`.
- **You own the Feed tab:** Quick Browse polish, product page, try-on, complete-the-look sheet, onboarding, look and feel.
- Nabil does Cart/Checkout + Fit Check; I do Closet, Profile (Style DNA) and the Fit Score badge. My Mac builds the iPhone version for the demo.
- Your FlutterFlow layout spec and fixtures are the design reference. Rebuild the screens from them.
- **Web images:** load product photos via `GET /img?url=<image_url>` on our backend (no key). Retailer image servers don't always allow web apps to load them directly.

New AI route for the Profile tab: `GET /users/{user_id}/style` → Style DNA: `{headline, styles[{tag, share}], palette[{name, family, hex, share}], patterns, formality{avg, label}, price_ranges, favorite_retailers, avoid, sample_size, confidence}`. `POST /users/{user_id}/style/apply` saves the learned price ranges on the user (409 under 5 likes).

---

## Read first

- **The shared backend is up:** Adam's Mac behind a Cloudflare tunnel. Adam sends you the URL and the key **privately**, never in Git (the repo is public). The URL changes if Adam restarts the tunnel.
- **Every request needs the header `X-DTI-Key: <key>`**. Set it once on the FlutterFlow API group. Images under `/static/...` and `GET /health` need no header, so image widgets can load try-on photos directly.
- **Real catalog:** 418 H&M + Uniqlo products, including 48 shoes, all AI-tagged. Product photos: `image_url`, plus `images[]` for the gallery and `description` (Uniqlo).
- **Demo user:** `u_demo`. Closet: black cargos, baggy jeans, white sneakers. Has an AI-generated full-body photo for try-on.

## New tonight

- **Closet screen:** `GET /closet/{user_id}` → `[ClosetItem]` (`label`, `category`, `color`, `image_url`, ...).
- **Duplicate check on upload:** `POST /closet/upload` returns `duplicate_of` (an item id, or null). When it's set, show "Looks like you already have this" with **Keep both** (do nothing) / **Remove** (`DELETE /closet/{user_id}/{item_id}` with the new item's id).
- **Fit Score badge** (Fit Check posts, complete-the-look sheet): `POST /ai/fit-score`, free and instant. Send one of these:
  - a post's tags: `{"items": post.tagged}`
  - a product plus closet pieces: `{"product_ids": [...], "closet_item_ids": [...]}`
  - It returns `{score: 0-100, verdict: "Clean neutrals, one pop", notes: [2-4 short lines], breakdown}`. Show `score` + `verdict` on the badge and `notes` in the details sheet.
- **Size picker** now works for real H&M jeans (`28/32`, `28inch`, women's `0–22`) and XXS–3XL.
- **Fit Check "shop this fit"** is faster: items not in the catalog are searched live at H&M in parallel, ~8 s the first time and instant after.

## Calls for your screens

| Screen | Call | Notes |
| --- | --- | --- |
| Feed | `GET /feed?user_id=u_demo&limit=20` | cards = Product + `reason` ("goes with your baggy jeans"), `score`, `pairs_with`. First load ~7 s (AI ranking), then cached |
| Save / cart / skip | Nabil's routes (`NABIL_TO_RYAN.md`) | `/swipe`, `PUT /wishlist/{user}/items/{product}` |
| Size picker | `POST /size {product_id, height_cm, weight_kg, fit?, waist_in?, shoe_us?}` | → `{size, confidence, reason}`; highlight `size`, grey out `in_stock: false` |
| Try it on | `POST /tryon {user_id, product_ids: [id]}` | ~5 s first time, instant after. `mode: "ai"` = real try-on; `"collage"` = outfit board (label it) |
| Complete the look | `POST /complete-look {user_id, product_id, budget_usd?}` | `{items: [{source: closet\|catalog, id, category, label, reason}], new_items_total_usd, missing}` |
| Fit Score | `POST /ai/fit-score` | see above |
| Cart / checkout | `GET /cart/{user_id}`, `POST /checkout/{user_id}` | grouped by retailer; checkout is a real Capital One Nessie purchase (`paid`) |
| Closet | `GET /closet/{user_id}`, `POST /closet/upload` (multipart `user_id`, `file`), `DELETE /closet/{user_id}/{item_id}` | upload returns the item with `label` and `duplicate_of` |
| Onboarding photo | `POST /users/{user_id}/body-photo` (multipart `file`) | |
| Fit Check | Nabil's `/fitcheck/...` routes; `POST /ai/tag-fit {image_url}` pre-fills tags | `/fitcheck/{id}/shop` returns buyable items + reasons |

## Known limits
- Catalog is H&M + Uniqlo only (Zara/ASOS/Mango aren't scraped). Fit Check live search is H&M.
- The first feed load takes ~7 s while Claude writes reasons; some cards come back without a reason (Nabil tops up with unranked cards), so hide the reason line when it's empty.
