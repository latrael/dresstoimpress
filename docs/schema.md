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
| `images` | `{url, kind}[]` | `[{"url": "...", "kind": "product"}, {"url": "...", "kind": "retailer_model"}]` | gallery for Ryan's carousel; same product + colour only; `image_url` stays primary; `kind` = `product` (the garment alone and whole), `retailer_model` (worn by a person), `detail` (close-up) or `other` (size chart, graphic). Labelled by `scripts.classify_images` (sprint 4); the labels are cached per photo in `seed/image_kinds.json` and re-applied on every ingest |
| `hero_image_url` | string or null | `"https://cdn.shopify.com/.../KHMA030579-001-Detail.jpg?v=1"` | the first `product` photo in the gallery: Home slide 1 (sprint-4 §6.2). Null when the store only has model shots. **On `/feed` cards it's never null:** it falls back to `image_url` |
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
- `FitScoreRequest {items: [FitTag-like dicts], product_ids: [], closet_item_ids: [], occasion?, target_style?, photo_url?}` → `POST /ai/fit-score` → `{score, verdict "68 as streetwear: …", notes, breakdown: {color/40, pattern/20, formality/20, completeness/20}, criteria: [{name, score_10, note}], style_scores: {streetwear…grunge: 0–100}, primary_style, raw_score, source: "rules"|"rules+ai"}` (Fit Score v2, Oct 24: calibrated rubric, random outfits ~50, 90+ rare). `POST /complete-look` now also returns `fit_score` (same shape) and `primary_style`.
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
| `display_image_url` | string | what to show (**sprint 3: never the catalog photo**; see "Closet, sprint 3"): generated clean product shot of the crop (Gemini, "only this garment, white background, no person") → the crop. **`image_url` always equals it** |
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

## Closet, sprint 3 (Oct 24, night): every garment, no catalog photos, outfits + pieces

Sprint-3 §1 (`docs/sprint-3.md`). Backend `backend/app/ai/closet.py`; core `Api.closetOutfits`, `Api.deleteClosetOutfit`, `ClosetOutfit`, `ClosetItem.outfitId`.

**1.1 Every garment.** Every `POST /closet/upload` photo with `kind=outfit` (the default) goes through digitize and every detected garment becomes a piece. The legacy single `file` call with no `kind` is digitized the same way (all garments land in the closet) but, for backward compatibility, answers with the **first** `ClosetItem` only; send `kind` to get `{added, merged, skipped, outfits}`. The app's closet button uses `api.uploadClosetPhotos(kind: 'outfit')`.

**1.2 No catalog photos on owned pieces (council).** `display_image_url` = `image_url` = the generated clean shot of the user's own crop, else the crop. `catalog_image_url` is never used for display (kept on the item for "shop similar"). `PATCH product_id` and `POST .../reshoot` never change the picture to a catalog photo. The catalog match is **strict** (`closet.strict_match`): type word + category agree, every descriptor word of the label is in the product text, the colour is the same colour (not merely "both neutral"), and the pattern agrees (a solid piece never matches a product whose name says striped/plaid/floral/graphic, and vice versa). Otherwise `product_id` / `brand` / `match_confidence` stay null.

**Clean shot from the best source photo.** For each piece the clean shot is generated from the source photo where the garment is clearest, among every `worn_in` entry with a `box`: not cut off (box not touching the photo edge) > largest box area > sharpness (Laplacian variance). That region is cropped with padding and sent with the prompt "Product photo of only this garment as worn in the photo: same colour, fabric, print, logo and fit, centered on a plain white background, flat-lay or ghost-mannequin, no person, no text." Recorded on the item as `clean_source_photo_url` + `clean_source_box`. When a merge adds a `worn_in` photo that shows the piece better, the clean shot is regenerated in the background (best effort).

`ClosetItem` new fields (optional; old items read as null):

| field | type | meaning |
|---|---|---|
| `outfit_id` | string \| null | the `outfits` record this piece was first digitized from; null for a single piece or after its outfit was deleted |
| `clean_source_photo_url` | string \| null | the source photo the clean shot came from (best of `worn_in`) |
| `clean_source_box` | `[x0, y0, x1, y1]` \| null | the garment's box in it, 0–1 fractions |
| `worn_in[].box` | `[x0, y0, x1, y1]` \| null | where the piece sits in that worn-in photo (new entries; a merge stores the new photo's box) |

**1.3 Outfits + pieces.** An outfit upload creates one `outfits` record per photo and each new piece gets `outfit_id` (a merged piece keeps its first outfit; it is listed in the new outfit's `piece_ids` too). A Fit Check post's auto-add creates an outfit with `source: "fitcheck"`. `kind=piece` uploads make no outfit.

`ClosetOutfit {id: "of_…", user_id, photo_url, created_at (ISO UTC), piece_ids: [string], source: "closet" | "fitcheck", pieces: [ClosetItem]}` (`pieces` = the listed pieces that still exist, in detection order).

Routes:

- `GET /closet/{user}/outfits` → `[ClosetOutfit]` newest first, pieces embedded.
- `DELETE /closet/{user}/outfits/{id}` → `{deleted: id}`; the pieces stay in the closet (their `outfit_id` is cleared). 404 if it isn't that user's.
- `POST /closet/upload` response gains `outfits: [outfit record]` (one per outfit photo that had a garment; `[]` for `kind=piece`).
- `GET /closet/{user}` unchanged; items carry `outfit_id`.

Core: `Api.closetOutfits()` → `List<ClosetOutfit{id, photoUrl, createdAt, time, source, pieceIds, pieces}>`, `Api.deleteClosetOutfit(id)` → `ClosetDeleteResult`, `ClosetItem.outfitId / cleanSourcePhotoUrl / cleanSourceBox`, `WornIn.box`, `ClosetUploadResult.outfits`. Tests: `backend/tests/test_closet_s3.py`, `app/test/core/api_closet_s3_test.dart`.

## AI Fit Creator

Complete outfits built for the user's body (body scan) that mix closet pieces with new catalog pieces in their size. Core: `Api.createFits({count, occasion, mustInclude, budgetUsd, tryOn})` → `List<OutfitFit>`, `Api.fit(id)`, `Api.fitTryOn(id)` → `TryOnResponse`, `Api.addFitToCart(id)` → `Cart`.

- `POST /fits/create?tryon=false` body `{user_id, count: 3, occasion?: "rooftop party", must_include?: [product_id], budget_usd?}` → `{fits: [OutfitFit], source: "ai"|"rules"}`. Pool = closet + buyable catalog products in the user's department / price ranges / budget that have a `your_size` (no size filter without a body profile). Claude picks; ids are validated against the pool, incomplete fits (need top+bottom or dress, plus shoes) are filled by the outfit rules; rules build one fit per top closet piece when AI is off. Cached 1 h per (user, closet, occasion, must_include, budget). `?tryon=true` also renders each fit (slow) when the user has a body photo.
- `OutfitFit {id: "fit_<hash>", name, occasion, reason (names build/measurement + the closet piece), pieces: [{slot: top|bottom|shoes|outerwear|dress|accessory, source: closet|catalog, closet_item: ClosetItem|null, product: Product card (+your_size/in_your_size)|null, your_size, in_your_size}], new_total_usd (catalog pieces), closet_count, try_on: {image_url, mode: "ai"|"collage"}|null}`.
- `GET /fits/{fit_id}?user_id=` → the cached fit (404 after 1 h). `POST /fits/{fit_id}/try-on?user_id=` → `{image_url, mode}` (same generator as `/tryon`). `POST /fits/{fit_id}/cart?user_id=` adds every catalog piece at `your_size` and returns the cart like `POST /cart/{user}/items`.

## Photo onboarding

`POST /onboarding/photos` (multipart, Oct 24): form `user_id`, `height_cm` (120–230, required), `weight_kg?` (30–250), `style_hint?` (free text, same parser as `POST /onboarding`, so "tops under $40" sets a budget), and 1–8 image parts all named `files`. One call does the whole onboarding from photos:

- every photo is digitized (`/closet/digitize` logic) → closet items; items whose `duplicate_of` points at an earlier item in the batch or at the existing closet are **not** saved;
- every photo is body-scanned (smallest first) and the full-body ones are averaged (`body_scan.scan_many`); the first full-body photo becomes `body_photo_url` (try-on photo) and the scan is merged into `body_profile` (typed values win). No full-body photo → formula estimate with `full_body: false`, `scan_photos: 0`, `confidence: "low"` and a note, `body_photo_url` unchanged;
- style is inferred from the digitized garments (top 3 `style_tags` by frequency, dominant colors, formality label, one sentence) and saved as `User.style_text` / `User.style_tags` with `onboarded = true`. `preferred_stores` untouched;
- the BODY_SCAN prompt also returns `presenting: men|women|unknown` (stored as `body_profile.presenting`); when the user's `shop_for` is unset / `"both"` and presenting is `men` or `women`, `shop_for` is set to it. A department the user chose is never overridden;
- the feed's reason bank is warmed in a background thread.

Response: `{closet_added: [ClosetItem], closet_skipped_duplicates: int, body_profile, body_photo_url: string|null, style: {style_text, style_tags, colors, formality}, shop_for, user: User}`. Everything is written immediately (no draft). Errors: 422 (no files, >8, bad height/weight), 415 (a non-image), 502 only if tagging failed for every photo; a photo with no clothing is skipped.

- `User.style_tags: [string]` (new, default `[]`): style vocabulary tags inferred by photo onboarding (hint tags first).

### Multi-photo body scan

`POST /users/{id}/body-scan` now takes 1–6 image parts named `files` (the single `file` part still works). Every photo is scanned; the full-body ones are averaged (chest/waist/hip/inseam to the nearest 0.5 in, `build` and `presenting` by majority vote). New `body_profile` fields: `scan_photos` (full-body photos used; 0 = formula only) and `confidence: "low"|"medium"|"high"` (1 / 2 / 3+ full-body photos). Response adds `skipped` (photos ignored because not full-body). `body_photo_url` is the first full-body photo. `?commit=false` and `/body-scan/confirm` carry the new fields through. App: `Api.bodyScanMany(photos, heightCm:, weightKg:, mimeTypes:, commit:)`, `BodyProfile.scanPhotos` / `.confidence`, `BodyScanResult.skipped`.
- App: `Api.onboardFromPhotos(photos, heightCm:, weightKg:, styleHint:, mimeTypes:)` → `PhotoOnboardingResult{closetAdded, skippedDuplicates, bodyProfile?, bodyPhotoUrl, styleText, styleTags, colors, formality, shopFor, user}`.

## Home reels (sprint 4): extra `/feed` card fields + try-on prefetch

Every `GET /feed` card (plain and `?seed=`) also has:
| Field | Shape | Meaning |
| --- | --- | --- |
| `hero_image_url` | string | Slide 1: the garment alone; `image_url` when the store has no such shot |
| `closet_picks` | `[{id, label, category, image_url}]`, 0–4 | Slide 3: the user's own closet pieces that go with it, one per square (`ai.service.closet_picks`, Adam). `[]` with an empty closet, or until Adam's part lands |
| `tryon` | `{status, image_url?, mode?}` | Slide 2. `status`: `ready` (`image_url` set; `mode` `ai` or `collage`), `pending` (rendering), `none` (not started), `needs_photo` (no photo of the user), `unavailable` (AI off / budget spent; `image_url` = the collage when there is one). `ai.service.tryon_status`, Adam |

- `POST /feed/{user_id}/tryons` `{product_ids: [≤ 5]}` → `{product_id: tryon}`.
  - Starts the try-on of each product **with its `closet_picks`** in the background (`ai.service.prefetch_tryons`, Adam) and answers at once.
  - Idempotent: a cached or already-rendering try-on isn't started again. Duplicate ids are ignored.
  - Errors: 404 unknown product, 422 for 0 or more than 5 ids.
- `GET /feed/{user_id}/tryons?ids=a,b,c` (≤ 5) → `{product_id: tryon}`, for polling a `pending` post every ~3 s.
- Both routes answer **501** until Adam's renderer is on the server. Until then cards carry `tryon: {"status": "none"}`.

