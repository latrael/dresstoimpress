# DressToImpress | Niche

A swipe feed of real, in-stock clothes from H&M and Uniqlo, ranked against your own closet, with one cart and one checkout across stores.

Claude (Anthropic) tags every product and closet photo and writes the pairings; see Adam's notes in [`ADAM.md`](ADAM.md) and the AI section of [`backend/README.md`](backend/README.md#ai-endpoints-adam).

## Where Apify and Capital One Nessie run

| Sponsor tool | What depends on it | Code |
| --- | --- | --- |
| Apify | Every feed card is a real listing pulled by an actor; Fit Check live search | `backend/app/commerce/ingest.py`, `backend/app/ai/finder.py` |
| Capital One Nessie | Checkout: one cart, one purchase per store | `backend/app/commerce/nessie.py`, `POST /checkout/{user_id}` |

### Apify: the catalog

**Actors and inputs**

| Retailer | Actor | Input |
| --- | --- | --- |
| H&M | `gauzy_penguin/HM-Product-Scraper` | search keywords, `Country: en_us` |
| Uniqlo | `abotapi/uniqlo-com-scraper` | US categories, `fetchDetails: true` (sizes and stock) |

**Pipeline** (`backend/app/commerce/ingest.py`, CLI `backend/scripts/ingest.py`)

1. `run_actor` calls Apify's `run-sync-get-dataset-items`; `fetch_hm` and `fetch_uniqlo` build each actor's input.
2. `normalize_hm` and `normalize_uniqlo` turn raw items into our `Product` shape:
   - drop kids, baby and maternity items;
   - one product per Uniqlo colour (capped), each with its own photos and per-colour stock;
   - per-size stock; Uniqlo `LOW_STOCK` counts as in stock (the actor reports it as `inStock: false`, but it's buyable);
   - image galleries (product + model shots) and plain-text descriptions where the retailer gives one (Uniqlo);
   - a stable id `{retailer}:{code}:{color}`, so re-runs update instead of duplicating.
3. `tag` sends each product photo to Claude, with the product name as a hint, for label, pattern, formality and style tags.
4. `save` validates and writes to the store; `/feed` serves it.

**The result:** a 418-product snapshot (290 H&M, 128 Uniqlo) committed at `backend/seed/products.json`, with the raw actor pulls in `backend/seed/raw/`. That's what `/feed` swipes through.

**Second use:** Fit Check's "shop this fit" looks for each tagged item in the catalog first. If nothing matches, `live_search` in `backend/app/ai/finder.py` (Adam's) runs the same H&M actor through `fetch_hm` + `normalize_hm` and shows the live hits.

**Why these actors:** we tested about a dozen; the multi-store actor returned no sizes, and these two give sizes and stock for US stores (notes in [`NABIL.md`](NABIL.md#apify-findings-reference)).

### Capital One Nessie: checkout

**Code:** `backend/app/commerce/nessie.py` (client) and `POST /checkout/{user_id}` in `backend/app/commerce/router.py`.

**Flow**

1. First checkout for a user creates a Nessie customer and a credit-card account. The first purchase at a retailer creates one Nessie merchant for it. Ids are cached in the store collection `nessie`, so each is created once.
2. Checkout re-checks stock. If a size sold out, it returns 409 with the unavailable items, and nothing is charged.
3. The cart is grouped by retailer, and each store gets one `POST /accounts/{id}/purchases`.
4. Each store's purchase comes back `paid` with its `nessie_id`, or `nessie_failed` with the error. Without `NESSIE_API_KEY` it's `pending_nessie`.
5. `GET /orders/{user_id}` lists past orders with their purchases.

**Quirks:** the API only answers over https (http hangs), and amounts are stored as integers (cents are dropped).

## How to run

Full steps are in [`backend/README.md`](backend/README.md). In short:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # APIFY_TOKEN, NESSIE_API_KEY, ANTHROPIC_API_KEY (or MOCK_AI=1)
python -m scripts.seed_demo && python -m scripts.load_products
uvicorn app.main:app --reload --port 8000
```

Tests: `cd backend && .venv/bin/pytest -q` (no keys needed).
