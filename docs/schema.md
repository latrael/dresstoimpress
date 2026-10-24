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
| `sizes` | `{name, in_stock}[]` | `[{"name": "S", "in_stock": true}, {"name": "M", "in_stock": false}]` | sold-out sizes kept and greyed out (Nabil's idea), **snake_case** `in_stock` |
| `in_stock` | bool | `true` | any size in stock |
| `image_url` | string | | |
| `product_url` | string | | |
| `style_tags` | string[] | `["minimalist"]` | vocabulary: y2k, streetwear, minimalist, preppy, athleisure, vintage, business, boho, grunge, classic |
| `pattern` | enum or null | `solid` | from `POST /products/tag` |
| `formality` | int 1–5 or null | `2` | from `POST /products/tag` |
| `label` | string | `ivory ribbed sweater` | from `POST /products/tag` |
| `scraped_at` | ISO string or null | `2026-10-24T02:16:01Z` | |
| `source` | enum | `ingest` | `ingest` (Nabil), `live_search` (Fit Check lookups), `seed` (demo) |

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

Old shapes still work everywhere in the AI code, and `app.ai.compat.to_canonical(product)` converts any of them to the unified shape before saving.

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
