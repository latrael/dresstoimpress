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
| `description` | string or null | `"Soft cotton tee with a relaxed fit."` | real retailer text as plain text, else null; never a pairing `reason` |

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

## Discover / Home (council D3, D9, D10, D11; `backend/app/ai/discover.py`, rules only)

A **card** = `Product` + `reason`, `score` (0–1), `pairs_with` + **`your_size: string | null`** and **`in_your_size: bool`** (same logic as `POST /size`: `body_profile` / flat `measurements` + `fit` + `usual_sizes`; no profile → `null` / `false`). Nothing is hidden: in-your-size cards come first, `preferred_stores` (retailer ids on the user) first within each group, the AI order kept otherwise.

- `GET /feed?user_id=&limit=` — as before, plus the two size fields and the size ordering.
- `GET /feed?user_id=&seed=<product_id>&limit=` — the seed first (`reason: "The piece you tapped"`), then look-alikes: same category first, then shared colours / style tags / item type / retailer / price within 40%, then size-ranked. 404 unknown seed.
- `GET /search?q=&user_id=&limit=` → `{query, vibe: {styles, categories, colors, keywords, source}, similar: [card], goes_with: [card]}`. `goes_with` = other-category pieces that complete the top similar item (closet-aware complete-look, then colour harmony). 422 empty `q`.
- `GET /search/styles?user_id=` → `{styles: [{tag, count}] (catalog style_tags, most used first), trending: [card]}`; trending = most wishlisted / carted across users (`trend_count`), else the top of the catalog.
- `POST /search/photo` (multipart `file`, form `user_id`) → `{tags: [FitTag], similar: [card + matched_tag], goes_with: [card]}`. Photo saved metadata-free; 502 when tagging is down, 415 non-image.
