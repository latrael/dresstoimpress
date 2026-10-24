# Sprint #2: polish + way more clothes

Sat Oct 24, 2026, ~5:00 PM PT. For the council session. Built from Nabil's list of app details, the "more clothes" ask, and the open asks in every handoff on `staging` (`8763e51`: ADAM_TO_NABIL 4:45, ADAM_TO_RYAN 4:35, RYAN_TO_NABIL 4:00, RYAN_TO_ADAM 4:05), plus Adam's merges through #38. Sprint #1 is `docs/council-final-sprint.md` (all P0s merged). **[decide]** = a call for the council.

**Three goals:**
1. **The app feels finished:** ten UI details, each traced to the file that needs to change.
2. **The catalog gets much bigger** (418 → 2,000+), with sizes, stock and men's/women's tags on every item, for a few dollars of Apify.
3. **Adam's new features reach the screen:** Fit Creator, measurement sizing, onboarding from photos.

---

## Since sprint #1: what Adam shipped (merged to `staging` unless noted)

| What | PR | Status | What it means for this sprint |
| --- | --- | --- | --- |
| **AI Fit Creator:** `POST /fits/create`. Full outfits for your body scan (closet + new in-stock pieces in your size), occasion chips ("class", "date", "rooftop party"), optional try-on per fit, add a whole fit to the cart | #34, #35 | Live on the shared server. Always ≥ 1 new piece; accessories follow `shop_for`. Core: `api.createFits / fit / fitTryOn / addFitToCart` | **No screen yet.** It's the strongest new demo moment. Ryan: a "Fits for you" screen **[decide: where it lives]** |
| **Try-on prompt v3:** same-person lock, garment names, the user's build and recommended size, so clothes drape on their body | #37 | Live | Nothing to build; re-warm try-ons after the catalog grows |
| **Faster phone uploads:** photos shrunk to 1600 px on the phone, 180 s timeout (a Pixel body scan was timing out) | #36 | Live | Body scan, closet and photo search are more reliable on the phone |
| **Short card blurb:** `Product.blurb()`, the first sentence (≤ 110 characters) of the retailer description, on every card | #38 | Merged (app-side) | Covers half of A7. **H&M has no description**, so H&M cards (290 of 418, most new items) still show nothing. B4 fills that. |
| **Sizing from real measurements:** chest/hip/waist/inseam charts + a usual-size check | `adam/measure-sizing` | **Branch, no PR yet** | Touches `commerce/router.py` (3 lines, what `_size_pick` passes). **Nabil reviews.** `your_size` gets better, with no API change. |
| **Onboarding from photos:** `POST /onboarding/photos`. Drop several photos → closet digitized, body scanned, style inferred, `shop_for` detected | — | **In progress** | Could replace several onboarding steps. **[decide]** whether it's a "fast setup" option or stays a stretch goal |
| **Catalog ingest on the shared server:** a men's H&M batch (12 keywords × 25) | — | Running (4:45) | Department is set at ingest. The Uniqlo actor returned 502: run stores separately, retry later |

---

## Part A: app details (Ryan's lane unless noted)

| # | Detail (Nabil's words) | Where it is now | Change | Owner |
| --- | --- | --- | --- | --- |
| A1 | Separator between products is too thick | `features/feed/quick_browse.dart:53-55`: a 48 px solid band | Thin and sleek, e.g. a 1 px hairline with ~24 px spacing, or a soft 8 px gap with no colour **[decide: look]** | Ryan |
| A2 | Remove the number next to the style tags in search | `features/discover/discover_screen.dart:344`: `'${tag.tag} · ${tag.count}'` | Label only (`tag.tag`). The API keeps `count` for ordering. | Ryan |
| A3 | The search keyboard should be dismissible | `discover_screen.dart:295`: `TextInputAction.search`, no dismiss | Dismiss on scroll (`keyboardDismissBehavior: onDrag`), on tap outside (`FocusScope.unfocus`) and on Search | Ryan |
| A4 | Heart animation on double-tap, like Instagram | `quick_browse.dart:348`: `onDoubleTap: () => save(value: true)`, no feedback | A heart scales in at the centre of the photo and fades (~600 ms); also fill the card's heart | Ryan |
| A5 | Remove the "X/X" counter on the photo carousel | Product card gallery in `quick_browse.dart` | Remove it; keep the dots, or nothing **[decide]** | Ryan |
| A6 | Pre-load carousel photos (current + next) | No `precacheImage` anywhere in `app/lib` | `precacheImage` the current photo, the next photo, and the next product's first photo | Ryan |
| A7 | Descriptions are far too long | **Half done (#38):** cards show the first sentence (≤ 110 characters). H&M has no description, so H&M cards are blank. A cut-off first sentence can also read oddly. | **Backend:** `summary`, 1–2 sentences from Haiku, or a one-liner from the attributes when there's no text (all H&M). **App:** `blurb()` prefers `summary` and falls back to the first sentence; full text behind "More". See B4. | Nabil (data) + Adam (prompt, `blurb()`) + Ryan (UI) |
| A8 | Your-style onboarding: tags first, like TikTok | Style screen is a text box | A grid of tappable chips (our 10 styles + vibe words), with a "type your own" box underneath. Chips + text go to `POST /onboarding` as text, so no API change. **[decide: chip list]** | Ryan |
| A9 | "Connect your account to digitize your closet" | `main.dart:205-211`: shown when the app is in **demo mode** (no server connection on this phone) | **For you now:** User → **Your connection** → Server URL (current tunnel), Shared access key, User ID → the app goes live. **For the UI:** Adam's ask (3): first-run onboarding opens Connection inline instead of a dead end. | Nabil (now), Ryan (UI) |
| A10 | Pages stack (tap Liked 3 times = 3 backs) | `main.dart:42`: `open()` always `push`es a new route | Top-right icons never stack: if that page is already open, do nothing; otherwise replace the current top-level page (`pushReplacement` / pop back to the shell first) | Ryan |

**Also on Ryan's list (from the handoffs):**
- **From Adam (ADAM_TO_RYAN 4:35):**
  - Scroll pickers for height, weight and measurements.
  - **US units** (ft/in, lb), converted in the app; the server stays metric.
  - Inline Connection on first run (= A9).
  - **"Fits for you"** for the AI Fit Creator (`api.createFits`): occasion chips → 3 outfit cards (closet pieces marked, new pieces in your size, new-items total) → try-on per fit → "Add fit to cart". Promoted from "when there's time": it's live and has no screen.
- **From Nabil (round two, still client-side):**
  - The **Men's / Women's / Both** onboarding screen (`shop_for`). Without it, the gender filter only works when someone sets it manually.
  - `seed_shown=true` on reloads of a seeded Home.
  - Cart-line `image_url` for unavailable items.

---

## Part B: way more clothes

### B1. Today
- **Committed snapshot:** 418 products (H&M 290, Uniqlo 128), all with `department`.
- **Shared server:** 452 products, **440 with `department: null`** (Adam, 4:45). The department snapshot (#31) was never loaded there, so the men's/women's filter can't hide much.
- **Fix now, free, no Apify:** on the shared server, run `python -m scripts.load_products` **without `--replace`**. It updates the 418 snapshot items in place (department + AI tags) and keeps everything else, including Adam's new ingests. `--replace` would delete them. Then `warm_demo --tryons 0`. Don't run `reset_demo` (it wipes u_demo's scan and closet).
- **Already running:** Adam started a men's H&M batch on the shared server (12 keywords × 25 per keyword). The Uniqlo actor returned **502** on his run, so run stores separately and retry Uniqlo later.

### B2. Sources and cost

From the Apify Store research (Sat ~5 PM). **Nothing was run.** Account spend so far: **$7.07** (H&M $5.75, Uniqlo $0.98, early tests $0.35); **~$198 left**.
- **Our plan is still FREE tier,** so free-tier prices and per-run caps apply. There's no residential proxy (datacenter IPs only), which rules out some actors.

**Step 0, $0: recover three pulls that are already paid for.** Today's 4:31–4:33 PM runs all **succeeded**. Adam's Uniqlo "502" was the HTTP wait timing out, not the run failing. The datasets are kept 7 days:

| Run | Items | Already paid | Dataset |
| --- | --- | --- | --- |
| Uniqlo, 18 categories | 211 products (~500 colour-products) | $0.67 | `iGeZpvLVraZfPkDFS` (run `1t465LlAXzkzYAC89`) |
| H&M, 24 gendered keywords × 25 | 586 | $2.34 | `uYlbnLWpWYVVqbnne` |
| H&M, men's batch | 286 (mostly duplicates of the above) | $1.14 | `3Er5Eo1UAC3b6iOVy` |

Download each (`GET /v2/datasets/{id}/items`, a fraction of a cent), save it under `seed/raw/`, then `scripts.ingest --from-file`. **≈ +400 H&M and +500 Uniqlo items for $0.** Also fix `run_actor` in `ingest.py`: when the sync call 502s, fetch the run's dataset instead of re-running (that's how this data got "lost").

**Ranked plan for this sprint:**

| # | Source | Actor | Cost | Adds | Sizes + stock | Department | Work needed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Recover the 3 datasets** | (already run) | **$0** | ~900 | ✅ | ✅ | `--from-file` only |
| 2 | **Uniqlo, new categories** (polos, sweatpants, cardigans, leggings, bags, hats, socks…) | `abotapi/uniqlo-com-scraper`, `resumeFromRunId` so duplicates aren't billed | **~$1.20** | ~700–900 | ✅ | ✅ `genderCategory` | none (~$1.10 per 1k feed items: best value) |
| 3 | **H&M, 32 new keywords × 25**: accessories (caps, bags, belts, jewelry, beanies; we have none), polos, overshirts, blazers, heels | `gauzy_penguin/HM-Product-Scraper` | **~$3.20** (two runs of ~$1.60) | ~600 | ✅ | ✅ `men_` / `ladies_` prefix | none. Keep "mens"/"womens" in keywords so kids' items stay out; check overlap first, since duplicates are billed ($0.004 each) |
| 4 | **Shopify stores**, ~200 each from gendered collections. Women: Princess Polly US, Edikted, Brandy Melville US. Men: True Classic. Unisex: Kith, Stüssy, Culture Kings | `autofacts/shopify` (2,380 users, 4.2★, updated Oct 20); backup `trovevault/shopify-products-scraper` | **~$1.00** | ~1,000 | ✅ per-variant stock | per collection URL / per store | a new `normalize_shopify` (variant Size/Color → sizes, compare-at → sale price, images per colour, drop gift cards/beauty) |
| 5 | Zara (optional) | `parseforge/zara-scraper`, 10 items per run on the free tier → 30 runs | ~$1.20 | ~300 | ✅ | ✅ breadcrumb (WOMAN/MAN) | a new `normalize_zara`; works around the actor's 10-per-run cap |

**Total to reach ~2,500–3,000 products: ≈ $5.40, or $6.60 with Zara.** That's under 4% of the remaining credit.

**Ruled out:**
- **Mango:** the actor needs proxy access our plan lacks.
- **Shein:** no per-size stock.
- **Nike and Bershka/Pull&Bear:** $42 per 1k.
- **ASOS:** UK store, prices in GBP.
- **Gap/Old Navy, Urban Outfitters, Abercrombie, American Eagle:** no actor, and they don't run on Shopify.
- **Gymshark, Hello Molly:** Cloudflare blocks them.
- **Fashion Nova, Skims:** no product JSON.
- **Forever 21 US:** believed closed in 2025.

**Before #4 / #5, a ~$0.20 test run** (2–3 collection URLs × 20 items) answers what research can't:
- Do Apify's datacenter IPs get blocked (429/403)?
- Are prices in USD?
- How good are the stock and gender tags?
- Are there garment-only images?
- Is Zara's cap per run or per day?

**New stores touch other lanes (team call):**
- **Schema:** `models.py` limits `Retailer` to `zara|hm|asos|uniqlo|mango`, and the schema is locked.
- **Checkout:** `nessie.py` `MERCHANTS` needs a merchant per new store.
- **Images:** the image-proxy allowlist (`app/lib/core/api.dart` and `backend/app/main.py`) needs `cdn.shopify.com` / `static.zara.net`, or web builds show no photos.
- **Onboarding:** the Stores screen hard-codes `['hm','uniqlo']` (`onboarding_screen.dart`).

Steps 1–3 need none of this; they're our current two stores.

### B3. The pipeline (two stages, every new item goes through both)

| Stage | What | Tool | Cost | Owner |
| --- | --- | --- | --- | --- |
| **1. Ingest** | Pull → normalize → per-size stock, **department**, galleries, stable ids, kids' items dropped. Save raw output (`--save-raw seed/raw/...`) so re-normalizing is free. One run per store and keyword batch (≤ 6 keywords, under the 600 s actor timeout). | `scripts.ingest` + a normalizer per new actor in `app/commerce/ingest.py` | Apify only | Nabil |
| **2. Enrich** | Claude Haiku tags label / pattern / formality / style_tags (name as hint) **+ the new `summary`** (A7). Department fallback for items whose store data has none: rules from the name/URL ("women's", "ladies", "men's"), then the tagger. | `scripts.tag_catalog` (Adam's) + summary prompt | ~$0.0004/item → ~$1 for 2,500 | Adam (prompt) + Nabil (runs) |
| **3. Size + ship** | Size charts per store × department (women's 0/2/4 vs men's 30/32, S–XL, shoes US). Export the snapshot, commit it, load it on the shared server, then `warm_demo`. | Adam's sizing PR (`adam/measure-sizing`), `export_products`, `load_products` | free | Adam (sizing), Nabil (snapshot) |

**Rules:**
- Every new item needs **sizes with stock + department + ≥ 1 image**, or it isn't loaded.
- Stage 2 must finish before an item shows on Home (untagged items rank badly and have no reason line).
- **Never `--replace`** on the shared server during the sprint.
- Ask Nabil before any Apify run over $2.

### B4. Descriptions (A7, backend half)
- **New optional field `Product.summary`:** at most 2 sentences, plain text, no invented facts (fabric or fit only if the retailer says so).
- **With retailer text:** Haiku condenses it. **Without** (all H&M): a one-liner from name + colour + category + style tags (e.g. "A light-wash baggy jean with a relaxed, streetwear fit.").
- Generated in stage 2, cached per product, so re-runs are free. ~2,500 items ≈ $0.50.
- `description` stays as is, for "More".

### B5. Gender tags
- **Built (#31):** `Product.department` + `User.shop_for`, filtering Home, Discover, trending and shop-this-fit.
- **Gaps:**
  1. The shared server needs the snapshot load (B1).
  2. Every new store's normalizer must set department (B2 table).
  3. Name/URL fallback + the tagger for the rest (B3 stage 2).
  4. The onboarding screen in the app (Part A, Ryan).

---

## Who does what (reconciled with the handoffs)

### Nabil
1. **Now:** connect the demo phone (A9). Ask Adam to run `load_products` (no `--replace`) + `warm_demo --tryons 0` on the shared server (B1).
2. **Catalog stage 1:**
   - **First:** recover the 3 paid datasets (B2 step 0, $0) and fix `run_actor`'s 502 fallback.
   - **Then:** Uniqlo + H&M expansion (steps 2–3), and `normalize_shopify` / `normalize_zara` if the council picks them.
   - Each store runs separately, with raw output saved.
3. **Catalog stage 3:** export + commit the new snapshot, update the counts in NABIL.md / Devpost / demo script.
4. **`Product.summary` field + backfill script** around Adam's prompt (B4).
5. **Review Adam's sizing branch** (`adam/measure-sizing`, 1 commit, touches `commerce/router.py` + `models.py`); it changes what `_size_pick` passes. Reply in `NABIL_TO_ADAM.md`.
6. **Demo script + Devpost:** add Fit Creator as a step and an Anthropic-track feature once its screen exists.

### Adam
1. **Shared server:** `load_products` (no `--replace`) → `warm_demo --tryons 0`; finish the running H&M batch; retry Uniqlo later.
2. **Open the sizing PR** (`adam/measure-sizing`) so Nabil can review it; then add size charts for any new stores × department.
3. **Summary prompt** (B4) in `tag_catalog` + the department fallback in the tagger (B3 stage 2); make `Product.blurb()` prefer `summary`.
4. **`POST /onboarding/photos`** (in flight) and its core method.
5. **Warm Fit Creator + try-ons** for `u_demo` after the catalog grows, so the demo is instant.
6. **Rebuild the iPhone / Android / web apps** after Ryan's polish PR.

### Ryan
1. **A1–A6, A8, A10** (UI details), plus the A7 UI ("More" for the full text).
2. **"Fits for you"** screen (Fit Creator, above).
3. **Onboarding:** the Shop-for screen; the TikTok-style chips (A8); inline Connection (A9); scroll pickers + US units (Adam's asks); "fast setup from photos" if the council picks it.
4. `seed_shown` and cart-line `image_url`.

### Everyone
- Dry run on the new build with the bigger catalog.
- Devpost final (numbers: product count, stores, tests).
- `staging` → `main` when the build is green.

---

## Order of work (suggested)

1. **Free and immediate:** B1 snapshot load, A9 connect phone, A2 / A5 / A3 (one-liners in the app).
2. **In parallel:**
   - Nabil: stage 1 (new stores + keyword batches) + the sizing review.
   - Adam: open the sizing PR, summary prompt, onboarding from photos.
   - Ryan: A1 / A4 / A6 / A8 / A10, "Fits for you", the onboarding screens.
3. **Then:** stage 2 tagging + summaries over everything new → stage 3 snapshot → `warm_demo` → rebuild the apps → dry run.

## Open questions for the council

1. **[decide]** How far down B2's ranked plan:
   - Steps 1–3 only: H&M + Uniqlo, ~2,000+ items, ~$4.40, no cross-lane changes.
   - Also add Shopify (step 4): new stores and ~3,000 items, but schema, merchant, image-proxy and onboarding changes.
   - Also Zara (step 5).
2. **[decide]** Apify budget for this sprint. The recommendation is **≤ $7** total (B2: $5.40, or $6.60 with Zara), including the ~$0.20 test runs.
3. **[decide]** Separator look (A1) and whether the carousel keeps dots (A5).
4. **[decide]** The onboarding chip list (A8): our 10 catalog styles only, or also vibe words ("clean girl", "old money", "gorpcore") that map onto them?
5. **[decide]** Summaries: should the AI one-liner for H&M be labelled as a summary, or shown like a retailer description?
6. **[decide]** Where does **Fits for you** live: a fourth tab, a button on Home, or a section in Discover? And does it go in the 3-minute demo, replacing which step?
7. **[decide]** **Onboarding from photos:** a "fast setup" option at the start of onboarding (drop photos, review what it found), or a stretch goal after the demo?
