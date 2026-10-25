# Product schema and the `staging` branch

## Branch flow

```
adam/ai-pipeline ─┐
nabil ────────────┼──> staging ──> main  (demo/submission)
ryan ─────────────┘
```

- Everyone opens a pull request into **`staging`**, never straight into `main`.
- `staging` is where we check names match and the tests pass (`cd backend && pytest -q`).
- `main` only gets `staging` once it runs end to end.
- Changing a field name in `backend/app/models.py` = a PR into `staging` that all three of us see.

## Product (one shape for everyone)

Source of truth: `backend/app/models.py` → `Product`. Use these exact names.

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `id` | string | `asos:211172667:ivory` | `{retailer}:{product_code}:{color}`, stable across scrapes (Nabil's format) |
| `retailer` | enum | `asos` | `zara`, `hm`, `asos`, `uniqlo`, `mango`; one Nessie merchant each |
| `name` | string | `Topshop ribbed sweater in ivory` | |
| `brand` | string | `Topshop` | |
| `category` | enum | `top` | **singular**: `top`, `bottom`, `outerwear`, `shoes`, `dress`, `accessory` (same as closet items) |
| `price_usd` | number | `96.73` | |
| `sale_price_usd` | number or null | `null` | |
| `currency` | string | `USD` | always USD for now |
| `colors` | string[] | `["ivory"]` | |
| `sizes` | `{name, in_stock}[]` | `[{"name": "S", "in_stock": true}, {"name": "M", "in_stock": false}]` | sold-out sizes are kept with `in_stock: false`; **snake_case** `in_stock` |
| `in_stock` | bool | `true` | any size in stock |
| `image_url` | string | | |
| `product_url` | string | | |
| `style_tags` | string[] | `["minimalist"]` | vocabulary: y2k, streetwear, minimalist, preppy, athleisure, vintage, business, boho, grunge, classic |
| `pattern` | enum or null | `solid` | from `POST /products/tag` |
| `formality` | int 1–5 or null | `2` | from `POST /products/tag` |
| `label` | string | `ivory ribbed sweater` | from `POST /products/tag` |
| `scraped_at` | ISO string or null | `2026-10-24T02:16:01Z` | |
| `source` | enum | `ingest` | `ingest` (Nabil), `live_search` (Fit Check lookups), `seed` (demo) |
| `images` | `{url, kind}[]` | `[{"url": "...", "kind": "product"}, {"url": "...", "kind": "retailer_model"}]` | gallery for Ryan's carousel; same product + colour only; `image_url` stays primary; `kind` = `product` (garment only) or `retailer_model` |
| `description` | string or null | `"Soft cotton tee with a relaxed fit."` | real retailer text as plain text, else null; never a pairing `reason`; the app shows it behind "More" |
| `summary` | string or null | `"A light-wash baggy jean with a relaxed, streetwear fit."` | card text: ≤ 2 sentences, ≤ 160 chars, plain. Stage 2 (`scripts.tag_catalog`) fills it: Haiku condenses `description`, or writes a one-liner from name + colour + category + style tags when there is none (all H&M). Never invents fabric or fit. Cached per id + `SUMMARY_VERSION`; rules template when AI is off. The app's `Product.blurb()` prefers it and falls back to the first sentence of `description`. Null until stage 2 has run |
| `department` | enum or null | `women` | `men`, `women`, `unisex`; null = unknown (shown to everyone). Set by the ingest normalizer (H&M `ladies_`/`men_` category code, Uniqlo `genderCategory`). **Fallback in stage 2** for nulls only, never overwriting a value: rules from the name / URL (`women's`, `ladies`, `dress`, `skirt`, `blouse`… → women; `men's`, `mens`, `/men/` → men), then the tagger's `department` answer. `tag_catalog --departments-only` backfills just this |

### Where this came from

Two drafts were merged: Nabil's proposal in [`NABIL.md`](../NABIL.md) (merged into `staging`, unchanged) and the first `models.py`. Nabil's pipeline, Apify findings and API plan in `NABIL.md` still apply; only the field names below changed.

Nabil's example product, in the unified shape:

```json
{
  "id": "asos:211172667:ivory",
  "retailer": "asos",
  "name": "Topshop knitted high neck ribbed sweater lace detail in ivory",
  "brand": "Topshop",
  "category": "top",
  "price_usd": 96.73,
  "sale_price_usd": null,
  "currency": "USD",
  "colors": ["ivory"],
  "sizes": [{"name": "S", "in_stock": true}, {"name": "M", "in_stock": false}],
  "in_stock": true,
  "image_url": "https://images.asos-media.com/products/.../211172667-1-white",
  "product_url": "https://www.asos.com/.../prd/211172667",
  "style_tags": ["minimalist"],
  "pattern": "solid",
  "formality": 2,
  "label": "ivory ribbed sweater",
  "scraped_at": "2026-10-24T02:16:01Z",
  "source": "ingest"
}
```

Note: NABIL.md's style words ("cozy", "minimal") become the shared vocabulary (`minimalist`), since the tagger and closet items use the same 10 tags.

### Renames from the two earlier drafts

| NABIL.md draft | `models.py` draft | **Unified** |
| --- | --- | --- |
| `price` | `price_usd` | `price_usd` |
| `url` | `product_url` | `product_url` |
| `category: "tops"` | `category: "top"` | `category: "top"` |
| `color` | `colors[]` | `colors[]` |
| `sizes: [{name, inStock}]` | `sizes: ["S"]` | `sizes: [{name, in_stock}]` |
| `tags.style[]` | `style_tags[]` | `style_tags[]` |
| `tags.pattern` | — | `pattern` |
| `tags.formality: "casual"` | — | `formality: 2` |

Old shapes still work everywhere in the AI code, and `app.ai.compat.to_canonical(product)` converts any of them to the unified shape before saving. It raises on an unknown category (it used to guess `top`) and fills a single-photo `images` gallery from `image_url` when none is given.

## Writing products (Nabil's ingest)

```python
from app.ai.compat import to_canonical
from app.ai.service import tag_product   # or POST /products/tag

p = to_canonical(raw_scraped_item)         # validates against Product, raises if a required field is missing
t = tag_product(p["image_url"])             # cached per image, ~$0.0002 on Haiku
p.update({k: t[k] for k in ("label", "pattern", "formality", "style_tags")})
if not p.get("category") or raw_scraped_item.get("category") is None:
    p["category"] = t["category"]           # ASOS listings have no category
store.put("products", p["id"], p)
```

## Other shapes

`ClosetItem`, `User`, `FitTag`, `PairResult` (`id` = `product_id`) are in `backend/app/models.py`. Size advice: `POST /size {product_id, height_cm, weight_kg, fit, shoe_us?, waist_in?}`.

- `ClosetItem.duplicate_of: string | null` (added Oct 23, 8:45 PM): set by `/closet/upload` and `/closet/tag` when the new item looks like one already in that closet (same category, color, pattern, garment type, similar label). Optional; old items read as null.
- `TagFitRequest.hint: string | null`: `/products/tag` only, the product name, for photos of a model in a full outfit.
- `FitScoreRequest {items: [FitTag-like dicts], product_ids: [], closet_item_ids: []}` → `POST /ai/fit-score` → `{score, verdict, notes, breakdown: {color, pattern, formality, completeness}}`.
- `FitTag.box` (optional): `[x_min, y_min, x_max, y_max]` as 0–1 fractions of the post photo, set by the AI tagger for Inspo pins; null on old posts and hand-added tags, and an invalid box is dropped (never an error).
- `POST /ai/vibe {q}` (≤200 chars) → `{styles, categories, colors, keywords, source: "ai"|"rules"}` for Discover; in-process: `from app.ai.vibe import vibe`.
- `DELETE /users/{id}/body-photo` → `{deleted: bool}`: clears `body_photo_url` and deletes our uploaded file; `body_profile` stays.
- Colors: free text everywhere. `app.ai.colors.normalize_color(text)` maps it to `{name, family, hex}` (31 names, families neutral / earth / warm / cool / unknown) when code needs to compare colors.

## Closet v2 (Oct 24, evening): a real wardrobe

Every closet item is one garment that stands on its own, plus the fits it was worn in. Backend: `backend/app/ai/closet.py`; core: `Api.uploadClosetPhotos`, `Api.updateClosetItem`, `Api.reshootClosetItem`, `ClosetItem`, `WornIn`, `ClosetUploadResult`.

`ClosetItem` new fields (all optional; items from before read as null / `[]`):

| field | type | meaning |
|---|---|---|
| `brand` | string \| null | read off a visible logo / label by the tagger (never guessed), or from the catalog match |
| `product_id` | string \| null | catalog product this piece **is** (confident match only: same type word + color + a descriptor) |
| `catalog_image_url` | string \| null | that product's photo |
| `match_confidence` | 0–1 \| null | with `product_id`; `1.0` when the user linked it by hand |
| `display_image_url` | string | what to show: catalog photo when matched → generated clean product shot of the crop (Gemini, "only this garment, white background, no person") → the crop. **`image_url` always equals it** |
| `crop_image_url` | string | the garment cropped out of the photo it was found in (the whole photo when there was no box) |
| `worn_in` | `[{photo_url, at (ISO UTC), source: "closet" \| "fitcheck"}]` | outfit photos it appeared in, oldest first |

Routes:

- `POST /closet/upload` multipart: `user_id`, **1–8 `files` parts**, `kind` = `"piece"` (each photo is one garment: tagged directly) or `"outfit"` (each photo is a whole fit: every visible garment — top, bottom, shoes, outerwear, watch/necklace/bag/cap — is detected with its own box and cropped; **default**). → `{"added": [ClosetItem], "merged": [ClosetItem], "skipped": int}`. **Dedupe merges**: a garment that matches something already in the closet is not created again; the photo is appended to that item's `worn_in` and it comes back under `merged`. `skipped` = photos that weren't clothing. 413 over 8 photos, 422 bad `kind` / no photos. **Backward compat:** a single `file` part with no `kind` (the old `api.uploadClosetItem`) still returns one `ClosetItem`.
- `POST /closet/digitize` unchanged (old flow, flags `duplicate_of` instead of merging). Core `digitizeCloset` now calls `/closet/upload` with `kind=outfit`.
- `PATCH /closet/{user}/{item}` `{label?, brand?, category?, color?, product_id?}` → `ClosetItem`. `product_id: null` clears the match and the display goes back to the clean shot / crop; a product id links it (display = catalog photo, `match_confidence: 1.0`). 422 bad category / unknown product, 403 someone else's item, 404 unknown.
- `POST /closet/{user}/{item}/reshoot` → `ClosetItem` with a regenerated clean shot (the crop when image AI is off). 403 / 404 as above.
- `GET /closet/{user}` unchanged; carries the new fields.
- **Fit Check → closet:** `POST /fitcheck` (Nabil's create) now calls `app.ai.closet.add_from_fit_later(user_id, photo_url, tagged)` after the post is saved: the post's tagged pieces go through the same per-garment pipeline (crop by `box`, dedupe-merge, `worn_in` source `"fitcheck"`) in a background thread. Best effort: never slows or fails the post.
- Prompts: `TAGGER` v3 and `DIGITIZE` v2 return `brand`; `DIGITIZE` lists every worn garment and accessory separately; `PAIR` v3 gets `brand` in the closet JSON so reasons can say "your Stüssy tee".

## AI Fit Creator

Complete outfits built for the user's body (body scan) that mix closet pieces with new catalog pieces in their size. Core: `Api.createFits({count, occasion, mustInclude, budgetUsd, tryOn})` → `List<OutfitFit>`, `Api.fit(id)`, `Api.fitTryOn(id)` → `TryOnResponse`, `Api.addFitToCart(id)` → `Cart`.

- `POST /fits/create?tryon=false` body `{user_id, count: 3, occasion?: "rooftop party", must_include?: [product_id], budget_usd?}` → `{fits: [OutfitFit], source: "ai"|"rules"}`. Pool = closet + buyable catalog products in the user's department / price ranges / budget that have a `your_size` (no size filter without a body profile). Claude picks; ids are validated against the pool, incomplete fits (need top+bottom or dress, plus shoes) are filled by the outfit rules; rules build one fit per top closet piece when AI is off. Cached 1 h per (user, closet, occasion, must_include, budget). `?tryon=true` also renders each fit (slow) when the user has a body photo.
- `OutfitFit {id: "fit_<hash>", name, occasion, reason (names build/measurement + the closet piece), pieces: [{slot: top|bottom|shoes|outerwear|dress|accessory, source: closet|catalog, closet_item: ClosetItem|null, product: Product card (+your_size/in_your_size)|null, your_size, in_your_size}], new_total_usd (catalog pieces), closet_count, try_on: {image_url, mode: "ai"|"collage"}|null}`.
- `GET /fits/{fit_id}?user_id=` → the cached fit (404 after 1 h). `POST /fits/{fit_id}/try-on?user_id=` → `{image_url, mode}` (same generator as `/tryon`). `POST /fits/{fit_id}/cart?user_id=` adds every catalog piece at `your_size` and returns the cart like `POST /cart/{user}/items`.
