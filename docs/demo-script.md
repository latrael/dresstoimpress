# Demo script (3 minutes)

Draft by Nabil's agent, Sat Oct 24 ~5 AM. Nabil runs the clock at the dry runs (17:30 / 18:30). **[confirm]** = depends on a screen Ryan is still building; if it isn't in the app by the 17:00 freeze, use the step's fallback or cut it. Who talks is a suggestion: change it at the dry run.

**Setup before a judge arrives:**
- **Demo phone:** u_demo, logged in, charged, on venue Wi-Fi.
- **Second phone:** a teammate's, for the live Fit Check post.
- **Laptop:** backup video queued, and the Nessie purchase list open (`GET /accounts/{id}/purchases`).
- **Backend:** run `smoke_e2e` within the last hour (10/10).
- **Cart and feed:** u_demo's cart is empty, and the feed is warm (open it once, since the first load takes ~7 s).

---

## 0:00–0:15 · Hook (Nabil)

> "Styling apps tell you what to wear but can't sell it to you. Buying one outfit means five tabs and five checkouts. We built one feed of real clothes that go with *yours*, and one checkout across every store."

On screen: the app home.

## 0:15–0:35 · Onboarding (Ryan) **[confirm]**

- Type **"Y2K, tops under $40"**.
- Show it parsed into a style plus a top budget of $0–40.
- Route: `POST /onboarding`.
- Line: "Plain words become a budget for each category."
- **Fallback:** skip this step; u_demo is already onboarded. Say it in one line.

## 0:35–1:20 · Swipe the feed (Ryan drives, Adam narrates the AI)

- Open Quick Browse. The first card is an H&M piece with its reason line: "goes with your black cargos."
  - Route: `GET /feed`. The feed is Apify listings, ranked by Claude against the closet.
- Adam: "Every card is a real, in-stock listing pulled by Apify, and Claude ranks it against what you already own. It tells you *why*."
- Swipe through the photo gallery, pick a size, and add it to the cart.
  - Routes: `POST /size` **[confirm]** for size advice, then `POST /cart/{user}/items`.
- Optional, 10 s: try-on on your own photo **[confirm]**.
  - Route: `POST /tryon`. It's cached (warmed overnight) and returns instantly.
  - **Fallback:** the outfit board (`mode: "collage"`), labeled as such. Don't call it a photo of you.
- Add a **Uniqlo** item too, so the cart has 2 stores.
- **Fallback if the feed stalls:**
  1. Pull to refresh. Ranking is cached for 10 minutes, so it comes back fast.
  2. If the tunnel is down, switch the app's base URL to Nabil's backup server.
  3. If that fails too, play the backup video from 0:35.

## 1:20–1:50 · One checkout, two stores (Nabil)

- Open the cart. It's grouped by store, H&M and Uniqlo, each with its own subtotal (`GET /cart/{user}`).
- Tap checkout (`POST /checkout/{user}`). Receipts show **one `paid` purchase per store**.
- Nabil: "That's two real Capital One Nessie purchases, one per merchant, from one tap." Flip the laptop to the Nessie purchase list.
- **Fallbacks:**
  - **A store comes back `nessie_failed`:** the order is still saved. Say "the payment API hiccuped; the order is kept," and show the earlier `paid` evidence table in `docs/devpost.md`.
  - **409 (sold out since added):** that's a feature. "It re-checks stock and charges nothing."

## 1:50–2:35 · Fit Check, live (Adam posts, Ryan shows) **[confirm]**

- A teammate posts a fit from the second phone (`POST /fitcheck`, multipart). The AI tags the pieces in a few seconds.
- It appears on the demo phone's Fit Check feed (`GET /fitcheck/feed`).
- Tap **"shop this fit"** (`GET /fitcheck/{id}/shop`). Matching items appear, each with how it pairs with your closet. Pieces not in our catalog are searched live on H&M through Apify.
- Optional: the Fit Score (`POST /ai/fit-score`).
- Line: "It turns 'where'd you get that?' into one tap between friends."
- **Fallback:**
  1. Use a seeded real post from this morning (`post_real_fits`) instead of a live upload.
  2. If the shop list is empty, open the next post.
  3. If the screen isn't built, show the backup video segment.

## 2:35–2:50 · How it's built (Adam)

> "Flutter app, one FastAPI service. Apify for real catalog data, Capital One Nessie for checkout, Claude for tagging and ranking, Gemini for try-on. Under fifty cents of AI for the whole build, with a fallback at every step."

## 2:50–3:00 · Close (Nabil)

> "Styling apps style you. We style you **and check you out**, across every store, in one cart."

---

## If something breaks (from `docs/plan-sat/README.md`)

| Problem | Do this |
| --- | --- |
| Adam's Mac or the tunnel dies | Switch the app's base URL to Nabil's backup server (same key) |
| Anthropic credits run out | Nothing: text falls back to Gemini (drilled Sat 2:05 AM: smoke 10/10) |
| Claude **and** Gemini down | Feed reasons come from rules, try-on shows the outfit board, and cart, checkout and shop still work (drilled: 10/10). **Only new photo tagging fails:** closet upload returns a plain 502, and a live Fit Check post goes up untagged. So use a pre-posted real fit instead of a live upload. |
| Try-on fails | The outfit board appears (`mode: "collage"`); warmed try-ons are cached |
| Nessie fails | The order is kept as `nessie_failed`; show the evidence table |
| The iPhone build fails | Demo the web build in Chrome on the laptop |
| Everything fails | Backup video, narrated live |

## Judge Q&A crib

- **Is the data real?** Yes: 418 products from H&M and Uniqlo via two Apify actors, with per-size stock. It's a snapshot taken at ingest; nothing is scraped during the demo, except Fit Check's live H&M search.
- **Is the payment real?** Yes, against Capital One's Nessie sandbox API: one purchase per merchant, verifiable by purchase id.
- **What if the AI is wrong?** Product-name hints cut wrong tags from 37 to 0 out of 418. Every step has a fallback, and users can fix Fit Check tags.
- **Privacy?** The body photo is used only for your own try-ons. Fit Check is friends-only by default. Keys stay on the server.
- **What does it cost?** About $0.07 to tag the whole catalog; there's a hard $5 AI cap.
