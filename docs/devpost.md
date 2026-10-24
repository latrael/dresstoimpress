# Devpost draft: DressToImpress | Niche

Draft by Nabil's agent, Sat Oct 24 ~3 AM. Numbers are measured on our backend. **[confirm]** marks a claim that depends on work still in progress (mostly app screens); check or cut each one before submitting. Deadline: **Sunday 9:00 AM**, with all three of us added as teammates.

**Tagline (≤ 60 chars):** Swipe real clothes that go with yours. One cart, every store.

---

## Inspiration

Styling apps tell you what to wear but can't sell it to you. Shopping apps sell you things but don't know what's already in your closet. Buying one full outfit still means five tabs, five carts and five checkouts. College students on a budget feel that most: they want pieces that work with the clothes they already own, at a price they set.

## What it does

- **Tell it your style in plain words.** "Y2K, tops under $40" becomes style preferences plus a budget for each category.
- **Swipe a feed of real, in-stock products** from H&M and Uniqlo, 418 of them with real sizes and stock. Every card is ranked against *your* closet and says why: "goes with your black cargos."
- **See it on you.** A virtual try-on on your own photo, a size suggestion, and "complete the look" with your closet plus a 0–100 Fit Score. **[confirm: app screens]**
- **One cart across stores, one checkout.** Checkout makes one real Capital One Nessie purchase per store. If something sold out since you added it, nothing is charged and the app shows exactly which item.
- **Fit Check:** an outfit feed for friends. Post a fit, the AI tags each piece, and friends tap "shop this fit" to buy matching items, found live through Apify when they aren't in our catalog. **[confirm: app screen]**

## How we built it

- **App:** Flutter (one codebase; web build plus an iPhone build). Quick Browse with photo galleries, wishlist, a cart grouped by store, checkout with per-store receipts, and order history.
- **Backend:** one Python FastAPI service. The app never talks to outside services directly, and every API key stays on the server. A shared request key protects the public tunnel.
- **Catalog: Apify.** Two actors (`gauzy_penguin/HM-Product-Scraper` and `abotapi/uniqlo-com-scraper`) feed an ingest pipeline. It drops kids' items, splits Uniqlo by colour, keeps per-size stock, builds image galleries and stable ids, and AI-tags every product. The result is 418 products (290 H&M, including 48 shoes, and 128 Uniqlo). We tested about a dozen actors; the multi-store one returned no sizes, which ruled it out for a store that has to sell you a size.
- **Checkout: Capital One Nessie.** Each user gets a Nessie customer and credit-card account, each retailer becomes a Nessie merchant (created once), and each store in the cart gets one purchase. Orders keep a status per store (`paid` / `nessie_failed`).
- **AI:**
  - **Claude Haiku** tags every product and closet photo (item, colour, pattern, formality, style). It ranks the feed against your closet and writes the reason on each card.
  - **Gemini** renders the virtual try-on on your own photo.
  - **Rules engines (no AI, free)** handle size advice, the Fit Score, Style DNA, colour matching and closet duplicate detection.
  - Tagging the whole catalog cost about **$0.07**, and the whole build about **$0.50** of AI. A hard $5 budget cap, caching everywhere, and fallbacks (Claude → Gemini → rules; try-on → an outfit-board collage) mean the demo never shows an error screen.

## Challenges we ran into

- **Sizes.** Most fashion scrapers read category pages, which don't list sizes. We had to find actors that open product pages, and handle store quirks. For example, Uniqlo's "low stock" comes back as `inStock: false` but is buyable.
- **Model photos lie to taggers.** A retailer photo of jeans usually shows a whole outfit. Without a hint, 37 of 418 tags described the wrong garment (the model's shirt instead of the jeans). Giving the tagger the product name brought that to **0**.
- **Multi-store checkout honesty.** Each store is a separate payment. We re-check stock before charging (a 409 with the exact unavailable items, nothing charged) and keep each store's status separately, so a failure at one store never hides a success at another.
- **No-code to code mid-hackathon.** FlutterFlow needed a paid plan to call our API, so we moved the app to plain Flutter overnight.

## Accomplishments that we're proud of

- Real products with real sizes and stock, not mock data.
- A real multi-merchant checkout: one checkout made separate Nessie purchases at H&M and Uniqlo. **[confirm: from the phone at checkpoint A]**
- Every recommendation explains itself in terms of clothes you already own.
- The AI is cheap and fails gracefully: about $0.50 of AI for the whole build, a fallback at every step, and 248 backend tests.

## What we learned

- Pick the data source by the hardest field you need (sizes), not by the number of stores.
- Small hints (a product name) beat bigger models for vision accuracy.
- A design that degrades gracefully matters more in a live demo than any single model.

## What's next

- More stores (Zara, Mango, ASOS) through more actors, refreshed on a schedule.
- Publishing our multi-store ingest as a public Apify actor.
- Real payments, plus order tracking per store.
- Fit Check beyond our friends: public posts, and creators earning from "shop this fit."

---

## Sponsor tracks (confirm against the Live Site before ticking)

Ticking is the team's call; this is the evidence for each. **Visa: do not tick, and we use no Visa APIs** (a teammate works there).

| Track | Status | Where it's used (2–3 sentences for the Devpost field) |
| --- | --- | --- |
| **Apify** | built | Every feed card is a real H&M or Uniqlo listing pulled by two Apify actors and normalized by our ingest pipeline (`backend/app/commerce/ingest.py`): 418 products with per-size stock. Fit Check's "shop this fit" also runs the H&M actor live when an outfit piece isn't in our catalog (`backend/app/ai/finder.py`). The README section "Where Apify and Capital One Nessie run" walks through it. |
| **Capital One Nessie** | built, verified | Checkout groups the cart by store and creates one Nessie purchase per store, on a Nessie customer and credit-card account per user, with a merchant per retailer (`backend/app/commerce/nessie.py`, `POST /checkout/{user_id}`). Stock is re-checked first, so a sold-out size returns 409 and nothing is charged. Evidence: the test orders below are visible through `GET /accounts/{id}/purchases`. |
| **Meta: Bringing People Closer** | backend built; app screen **[confirm]** | Fit Check is a friends' outfit feed: post a fit, the AI tags each piece, and friends tap "shop this fit" to buy matching items paired with their own closet. It turns "where did you get that?" into a one-tap purchase between friends. Friends-only by default. |
| **Anthropic** | built | Claude Haiku tags every product and closet photo and ranks the feed against each user's closet, with a one-line reason per card. Community: college students building a wardrobe on a student budget. Where it can go wrong: wrong tags (fixed with product-name hints, 37 → 0 errors out of 418) and body bias in try-on (the body photo stays private, and the prompt keeps body proportions unchanged). |
| **Moss** | code in place **[Adam to confirm]** | Style memory: every swipe is indexed in Moss and retrieved to personalize picks (`backend/app/ai/memory.py`), falling back to recent swipes if Moss is off. |
| **Notability** | **[Ryan to confirm]** | Wireframes and meeting notes from the start of the build; link them. |
| **Figma** | **[Ryan to confirm]** | Only if hi-fi screens were made in Figma. |
| Convex / SpacetimeDB | not built | Skip unless someone builds it; Fit Check runs on our own store. |
| Visa | **never** | — |

General prizes (no tick needed): Most Creative, Best People-First, Hacker's Choice (the Fit Check QR on our table).

### Nessie evidence for judges

Run overnight Sat Oct 24 (~1:20 AM PT) on Nabil's backup server, which uses the same backend code and the real Nessie API, as the throwaway user `u_test_checkout`. Every purchase came back `paid` and appears in Nessie's purchase list for that account. The cart was emptied afterwards.

| Checkout | Store | Amount (ours → Nessie, whole dollars) | Nessie purchase id |
| --- | --- | --- | --- |
| H&M only | hm | $39.99 → 40 | `4c27c309-ba26-46c9-9a6e-ce7cb3627d3d` |
| Uniqlo only | uniqlo | $24.90 → 25 | `5138caae-3742-4a31-a420-66b434d3ba54` |
| Mixed | hm | $99.00 → 99 | `395ebfeb-f3ee-4ceb-8cf5-8d11b30ffd4b` |
| Mixed | uniqlo | $24.90 → 25 | `87f7e4e2-61e0-453d-bcd3-ce37756758f9` |

Nessie account: `2775aade-9973-4ba3-9075-9b52924bd8e2`. Nessie stores whole-dollar amounts; our order keeps the exact price.

## Links to add

- GitHub repo · demo video (backup recording) · Notability notes **[Ryan]** · Figma **[Ryan]**
