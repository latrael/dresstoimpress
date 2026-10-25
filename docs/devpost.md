# Devpost: DressToImpress | Niche

Updated Sun Oct 25 ~3 AM for sprint 4 (the redesign and reels Home), after sprint 3 (Fit Score v2, try-on from your own photos, shop the look per piece, the Niche icon). Structured like the Devpost form: **About the project** (paste everything between the two `✂` lines into that one Markdown box), **Built with** (tags), and **"Try it out" links**. Numbers are measured on our backend. **[confirm]** = a screen in Ryan's sprint PR; check it in the app before submitting. Deadline: **Sunday 9:00 AM**, with all three of us added as teammates.

**Tagline (≤ 60 chars):** Real clothes in your size that go with yours. *(50 chars)*

---

## About the project

✂ ---------- paste from here ----------

## Inspiration

Shopping for one outfit means five tabs, five carts, and guessing your size five times. Styling apps tell you what to wear but can't sell it to you. Shopping apps sell you things but have no idea what's already in your closet. College students on a budget feel this the most: we want pieces that work with the clothes we already own, in our size, at a price we pick.

## What it does

Niche learns who you are once, then everything you see is in your size, in stock, goes with what you own, and checks out in one tap across stores.

- **Onboarding, one screen per step.**
  - Describe your style in plain words ("y2k fits, baggy jeans, tops under $40").
  - Pick the stores you like and whether you shop men's, women's or both.
  - Do a body scan: one full-body photo plus your height gives estimated measurements, which you confirm.
  - Every step after the first can be skipped.
- **Home, like reels:** one real product fills the screen at a time, from 8 stores (H&M, Uniqlo, Princess Polly, Edikted, Brandy Melville, True Classic, Kith, Stüssy). Swipe up for the next.
  - **Three slides per product:**
    1. the item on its own;
    2. **the item on you**, styled with your own clothes, rendered before you scroll to it;
    3. a 2×2 grid of **pieces you already own** that go with it.
  - Items in your size come first, with the size already picked. You only see sizes that are actually in stock.
  - Every card says *why* it's there: "goes with your black cargos." Add to cart is the only button. Double-tap to like, and swipe sideways to change tabs.
- **Discover.**
  - Search a style ("y2k") or a vibe ("fit for a rooftop party").
  - Or tap the camera and snap something you like in real life.
  - Results come back as **Similar items** and **Goes with it**, and the pieces you already own are marked.
- **Inspo:** everyone's outfit of the day.
  - Tap a photo and each piece gets a tag, like tagging people on Instagram: what it is, which store, the price.
  - Tap a tag and Home fills with that item and others like it, in your size. **[confirm]**
  - **Shop the look:** each tagged piece gets its own row of up to 6 similar items, in your department.
  - Likes are instant, and comments open in a sheet that loads older ones as you scroll.
- **Closet:** photograph a pile of clothes, or just post your fits, and it splits them into separate, tagged pieces. It also keeps the outfits you wore them in.
  - Your own pieces always show your own photo, never a store's catalog shot.
  - Recommendations are built around what you already own.
- **Try it on, on you.** Pick any item and see it on one of your own outfit photos.
  - It chooses your best photo for that piece (a top replaces a top), then edits only that garment.
  - Your face, pose, background and the rest of your outfit stay untouched.
- **Fit Score:** every outfit gets a 0–100 score from eight stylist criteria (colour, silhouette, pattern, formality, style coherence, shoes, layering, occasion).
  - It's said in terms of a style: "68 as streetwear: strong silhouette, palette too busy."
- **One cart, every store, one checkout.**
  - Change sizes with the pencil on each item.
  - Checkout makes one real Capital One Nessie purchase per store.
  - If something sold out since you added it, nothing is charged and the cart shows which item. If one store's payment fails, you retry just that store.

## How we built it

- **App:** Flutter, one codebase for iPhone, Android and web, named **Niche** with its own arch icon.
  - Its own design system: Young Serif + Manrope type, the merlot/cream palette, frosted-glass header and tab bar, and motion and haptics on every tap and page change.
  - Swipe between Home · Discover · Inspo; Liked, Bag, Closet and your profile sit at the top.
- **Backend:** one Python FastAPI service.
  - The app never talks to outside services directly; every API key stays on the server.
  - A shared request key protects the public tunnel.
- **Catalog: Apify.**
  - Three actors (`gauzy_penguin/HM-Product-Scraper`, `abotapi/uniqlo-com-scraper`, and `autofacts/shopify` for six Shopify brands) feed our ingest pipeline. It drops kids' items, splits Uniqlo by colour, keeps per-size stock, builds photo galleries, tags men's/women's/unisex from the store's own data, and AI-tags every product.
  - The result is 3,476 products from 8 stores (1,922 women's, 1,218 men's, 336 unisex), shoes and accessories included, for about $3.30 of Apify credit.
  - When a photo shows a piece we don't carry, the backend searches H&M live through Apify (capped and cached).
- **Checkout: Capital One Nessie.**
  - Each user gets a Nessie customer and a credit-card account, and each retailer is a Nessie merchant.
  - Each store in the cart becomes its own purchase, with its own status (`paid` / `nessie_failed`) and a retry that never charges a paid store twice.
- **AI:**
  - **Claude Haiku** tags every product and photo, ranks the feed against your closet and writes the reason on each card. It also turns vibe searches into filters, splits a closet photo into separate items, and estimates measurements from the body scan.
  - **Gemini** renders the virtual try-on and covers for Claude if it's down. The backend scores every photo you've uploaded (body scan, posted fits, closet photos) and picks the one that best shows a garment of the same kind. Then it tells Gemini where that garment is, so the edit stays local.
  - **Plain rules (no AI, free)** handle sizing, colour matching and duplicate detection, so they're instant.
  - **Fit Score v2** is a rubric of eight criteria, each scored 0–10 with written anchors, plus a score for each of ten styles. It's calibrated on 300 random outfits (median 70, none reach 90) and 30 curated ones (median 84). On a posted photo, one Claude vision call grades the same criteria and is blended 50/50 with the rules. Complete the Look uses the same rubric and never pairs athletic with formal.
  - A hard budget cap, caching and fallbacks everywhere (Claude → Gemini → rules; try-on → an honest "try-on unavailable" card with retry) mean the demo never shows an error screen.

## Challenges we ran into

- **Sizes.**
  - Most fashion scrapers read category pages, which don't list sizes, so we had to find actors that open each product page.
  - Then came the store quirks. Uniqlo's "low stock," for example, comes back as `inStock: false` even though you can still buy it.
- **Finding the photo of just the item.** Stores mix product shots with model shots and close-ups, and our data labelled them wrong both ways. Claude Haiku labelled all **11,779** catalog photos from one contact sheet per product, for about **$0.23**, so slide 1 shows the item on its own for 1,167 products. Tight crops of legs in jeans still fooled it, so one store's model-photo filenames override the AI.
- **Model photos confuse taggers.** A retailer's photo of jeans usually shows a whole outfit. Without a hint, 37 of 418 tags described the wrong garment (the model's shirt instead of the jeans). Giving the tagger the product name brought that to **0**.
- **Men's vs women's.** Our first sizing pass recommended a women's size 8 to a 178 cm guy. The stores' raw data already said which department each item belongs to, so we pulled that through and let you pick men's, women's or both.
- **Scores that mean something.** Our first Fit Score just added points up, so nearly every outfit scored 80+. We rebuilt it as a rubric and calibrated it on random outfits until a 90 had to be earned.
- **Try-on that looks like you.** Re-rendering the whole photo changed faces and backgrounds. Editing only the one garment, on the photo that best shows it, fixed that.
- **Photos carry your location.** iPhone photos include GPS coordinates. We strip that metadata from every upload before it's saved.
- **Honest multi-store checkout.**
  - Every store is a separate payment, so stock is re-checked before anything is charged.
  - Each store keeps its own status, so a failure at one never hides a success at another.
- **Three people, one backend, 36 hours.** We split into lanes (app, AI, commerce) and coordinated through handoff files in the repo, with every change going through a pull request into a shared staging branch.

## Accomplishments that we're proud of

- Real products with real sizes and stock, not mock data.
- A real multi-store checkout: one tap made separate Nessie purchases at H&M and Uniqlo (4 of 4 `paid` in our test run).
- Every recommendation explains itself in terms of clothes you already own.
- Snap-to-shop: a photo of something in real life becomes items you can buy, in your size.
- It fails gracefully: we drilled AI outages, and checkout, cart and the feed keep working. 713 backend tests and 185 app tests.

## What we learned

- Pick the data source by the hardest field you need (sizes), not by the number of stores it covers.
- Small hints, like a product name, beat bigger models for accuracy on photos.
- Graceful fallbacks matter more in a live demo than any single model.

## What's next

- More stores (Zara, Mango, ASOS) through more Apify actors, refreshed on a schedule.
- Google sign-in and syncing across devices.
- Real payments and per-store order tracking.
- Creators earning when people shop their Inspo posts.

✂ ---------- paste to here ----------

---

## Built with

Paste one at a time (25 max; these are 19):

`flutter` · `dart` · `python` · `fastapi` · `pydantic` · `uvicorn` · `apify` · `capital-one-nessie` · `anthropic` · `claude` · `google-gemini` · `pillow` · `httpx` · `pytest` · `cloudflare-tunnel` · `ios` · `android` · `github` · `google-fonts`

Add `notability` / `figma` only if Ryan confirms we used them. Don't add `moss` (never switched on) or anything Visa.

## "Try it out" links

- **Code:** https://github.com/latrael/dresstoimpress
- **Demo video:** add after the 18:30 backup recording.
- Don't post the tunnel URL: it's private and needs the key.

---

## Sponsor tracks (confirm against the Live Site before ticking)

Ticking is the team's call; this is the evidence for each. **Visa: do not tick, and we use no Visa APIs** (a teammate works there).

| Track | Status | Where it's used (2–3 sentences for the Devpost field) |
| --- | --- | --- |
| **Apify** | built | Every product in the app is a real listing from one of 8 stores (H&M, Uniqlo and six Shopify brands), pulled by three Apify actors and normalized by our ingest pipeline (`backend/app/commerce/ingest.py`, `ingest_shopify.py`): 3,476 products with per-size stock and men's/women's tags, for about $3.30 of Apify credit. Photo search and Inspo's "shop this fit" also run the H&M actor live when a piece isn't in our catalog (`backend/app/ai/finder.py`). |
| **Capital One Nessie** | built, verified | Checkout groups the cart by store and creates one Nessie purchase per store, on a Nessie customer and credit-card account per user, with a merchant per retailer (`backend/app/commerce/nessie.py`, `POST /checkout/{user_id}`). Stock is re-checked first, so a sold-out size returns 409 and nothing is charged; a failed store can be retried without re-charging the others. Evidence: the test orders below, visible through `GET /accounts/{id}/purchases`. |
| **Meta: Bringing People Closer** | built | Inspo is a shared outfit-of-the-day feed: post a fit, the AI tags each piece, and anyone can tap a tag to find that item (or similar) in their own size, or "shop this fit" for the whole look. It turns "where did you get that?" into one tap between friends. |
| **Anthropic** | built | Claude Haiku tags every product and photo, ranks the feed against each user's closet with a one-line reason per card, turns vibe searches into filters, splits closet photos into items and estimates measurements from a body scan. Community: college students building a wardrobe on a budget. Where it can go wrong: wrong tags (fixed with product-name hints, 37 → 0 errors out of 418) and body bias in sizing and try-on (the body photo stays private, measurements are always confirmed by the user, and try-on keeps body proportions unchanged). |
| Moss | **not live: don't tick** | Code exists (`backend/app/ai/memory.py`), but no Moss keys were ever set, so style memory uses swipe + wishlist history. |
| **Notability** | **[Ryan to confirm]** | Wireframes and meeting notes from the start of the build; link them. |
| **Figma** | **[Ryan to confirm]** | Only if hi-fi screens were made in Figma. |
| Convex / SpacetimeDB | not built | Skip. |
| Visa | **never** | — |

General prizes (no tick needed): Most Creative, Best People-First, Hacker's Choice.

### Nessie evidence for judges

**Latest run: Sat Oct 24, 11:29 PM PT, on the team's shared server** after the sprint-3 database rebuild, as the throwaway user `u_test_checkout`.
- All 4 store purchases came back `paid` (Nessie status `completed`) and appear in Nessie's purchase list for the account. The cart was empty afterwards.
- Failure paths: an empty-cart checkout → 400, a sold-out size → 422 when added. Nothing was charged.

| Checkout | Store | Amount (ours → Nessie, whole dollars) | Nessie purchase id |
| --- | --- | --- | --- |
| H&M only | hm | $7.99 → 8 | `e52275e2-858f-44b6-ada1-3d21c06f9423` |
| Uniqlo only | uniqlo | $3.90 → 4 | `ed6306be-263f-484c-a58f-60c2f485b995` |
| Mixed | hm | $5.99 → 6 | `047fc7ae-6bc4-426b-a137-1971b4ff55f8` |
| Mixed | uniqlo | $3.90 → 4 | `4d57baad-a5bd-4e8a-b927-ff630d6a54fc` |

Nessie account: `357335da-4822-46a3-8208-83325eb8d390`. The rebuild reset the user → account mapping, so this is a new account; the earlier run's purchases below still exist under the old one.

**Earlier run:** overnight Sat Oct 24 (~1:20 AM PT) on Nabil's backup server, which uses the same backend code and the real Nessie API, as the throwaway user `u_test_checkout`. Every purchase came back `paid` and appears in Nessie's purchase list for that account. The cart was emptied afterwards.

| Checkout | Store | Amount (ours → Nessie, whole dollars) | Nessie purchase id |
| --- | --- | --- | --- |
| H&M only | hm | $39.99 → 40 | `4c27c309-ba26-46c9-9a6e-ce7cb3627d3d` |
| Uniqlo only | uniqlo | $24.90 → 25 | `5138caae-3742-4a31-a420-66b434d3ba54` |
| Mixed | hm | $99.00 → 99 | `395ebfeb-f3ee-4ceb-8cf5-8d11b30ffd4b` |
| Mixed | uniqlo | $24.90 → 25 | `87f7e4e2-61e0-453d-bcd3-ce37756758f9` |

Nessie account: `2775aade-9973-4ba3-9075-9b52924bd8e2`. Nessie stores whole-dollar amounts; our order keeps the exact price.
