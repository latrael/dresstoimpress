# Sprint #3: fix what's visible, real login, clean database

Sat Oct 24, 2026, ~7 PM PT. For the council session. `staging` is at `6ff18f2` (583 backend tests pass). Sprint #2 is `docs/sprint-2.md`. **[decide]** = a call for the council. Nothing here has been acted on yet: read it, decide, then each owner acts.

**Decided at the council (~7:10 PM):**
- **Inspo starts empty** after the rebuild (no re-posted fits).
- **Owned closet pieces never show a catalog photo** (1.2).
- **Tall Inspo photos are capped at 9:16** (height ≤ 16/9 × width), centre-cropped (3.1).
- **Login is tackled last;** the one-tap team accounts stay until then (4).

---

## 0. Carry-overs from sprint #2 (do these first)

| # | Item | Owner | Detail |
| --- | --- | --- | --- |
| 0.1 | **Sizing bugs** | Adam | **Princess Polly tops show size `12` for an average woman** (165 cm / 58 kg / 34" bust: 136 of 179 tops); should be ~4–6. **Brandy Melville `XS/S`, `S/M` get no size** (161 of 169). `One Size` shows no badge. Root causes + suggested fixes: `NABIL_TO_ADAM.md` 6:10 PM. In short: `ai/sizing.py` step 6 compares numeric sizes to waist **inches**, and combined sizes aren't in `LETTER_TO_IDX`. |
| 0.2 | **Store names in the app** | Ryan | Cart headings (`retailerName()` in `cart_screen.dart`) and the onboarding Stores step still hard-code H&M / Uniqlo, so new stores show as `princesspolly`. Use `GET /stores` (`[{id, name, count, departments}]`). Also remove "We currently carry H&M and Uniqlo". |
| 0.3 | **Shared server has the 3,188-product catalog** | Adam | Unconfirmed. **Superseded by the rebuild (section 6)** if the council approves it; otherwise: restart → `load_products` (no `--replace`) → `tag_catalog --summaries-only` → `warm_demo --tryons 0`. Confirm with `GET /stores` (8 stores). |

---

## 1. Closet

| # | Problem (Nabil's words) | What's going on | Change | Owner |
| --- | --- | --- | --- | --- |
| 1.1 | Uploading a full outfit only adds **one** clothing item | #51 added multi-garment detection (`POST /closet/digitize`), but the upload Nabil used still lands as one item. Either the app calls `/closet/upload` (one item per photo) for that button, or digitize is falling back to one item. | **Verify which route the closet's upload button calls** on the current build. Every closet photo should go through digitize, which detects every garment. | Ryan (which route) + Adam (digitize) |
| 1.2 | **Wrong catalog photos on closet items.** A corduroy shirt we don't carry got a random, unrelated catalog picture | `ai/closet.py` `catalog_match()` takes the best-scoring catalog product above `CONFIDENT_SCORE` and swaps in its `catalog_image_url`. When we don't carry the item, the "best" match is still wrong. | **Decided: never show a catalog photo for an owned piece.** The closet always shows the user's own crop (or the clean shot). `catalog_match` may still set `product_id` / `brand` for "shop similar", but only above a much higher bar, where label words + colour + pattern/fabric agree. `catalog_image_url` is never used as the closet photo. | Adam |
| 1.3 | The closet should hold **both outfits and separate pieces** | Today it's a flat list of pieces | Two views: **Outfits** (the full photo you uploaded, with its pieces tagged, like an Inspo post) and **Pieces** (each garment, its own photo). An outfit upload creates 1 outfit + N pieces linked to it. Backend: an `outfit_id` on closet items + `GET /closet/{user}/outfits`. | Adam (data), Ryan (UI) |

## 2. Home

| # | Problem | Where | Change | Owner |
| --- | --- | --- | --- | --- |
| 2.1 | "Edit in cart" text above Add to Cart | `features/feed/quick_browse.dart:604-605` (`'… · edit in cart'`) | Remove "· edit in cart" from both strings; keep the size text | Ryan |

## 3. Inspo

| # | Problem | Where | Change | Owner |
| --- | --- | --- | --- | --- |
| 3.1 | Photos look stretched or cut off | `features/social/social_feed.dart:321`: every post is forced to `AspectRatio(.85)` | Use **each photo's own aspect ratio**: scale to the app's width, height follows. No stretching, no bars; a wide photo just makes a shorter post. **Decided:** tall photos are capped at **9:16** (height ≤ 16/9 × width) and centre-cropped; anything wider shows whole. Backend can send `width`/`height` per post so the layout doesn't jump while loading. | Ryan (+ Nabil: `photo_w`, `photo_h` on posts) |
| 3.2 | Buttons under each post are squished; the comment bar is too big | Post card footer | Margin between the action row and the next post; smaller comment input, or a "Add a comment…" line that opens the sheet (3.4) | Ryan |
| 3.3 | Liking is slow | `POST /fitcheck/{id}/like` **toggles**, so the app has to wait to know the result | **Optimistic:** flip the heart and count locally right away, send in the background, and roll back only on error. Backend: an idempotent `PUT /fitcheck/{id}/like {user_id, liked: true\|false}`, so a retried or queued request can't double-toggle. The old POST stays. | Nabil (route), Ryan (UI) |
| 3.4 | Comments show up oddly | Comments are inline under the post | A **comment sheet** that slides up: newest at the bottom, input pinned at the bottom, keyboard-safe. Backend: `GET /fitcheck/{id}/comments?limit=&before=` (paged, with author names), so the feed doesn't ship every comment. | Nabil (route), Ryan (UI) |

## 4. Login (tonight)

Today the Welcome screen has one-tap team accounts (#45). There's no sign-in, and the server trusts whatever `user_id` the app sends.

**[decide] which login:**

| Option | What the user does | Work | Risk tonight |
| --- | --- | --- | --- |
| **A. Google sign-in** (the original stretch goal) | "Continue with Google" | App: `google_sign_in` + iOS/Android/web OAuth client ids (Google Cloud console). Backend: verify the Google ID token, map `sub` → our user id, issue our session token | Most setup: OAuth consent screen, 3 client ids, iOS URL scheme, re-signing |
| **B. Email + one-time code** | Type your email, enter the 6-digit code | Backend: `POST /auth/start`, `POST /auth/verify` → session token; needs an email sender | An email provider + deliverability |
| **C. Username + password** | Pick a username and password | Backend: hashed passwords, `POST /auth/signup` / `/login` → token. App: two screens | Least setup; weakest UX and security story |

**Whichever we pick, the backend part is the same** (Nabil):
- `users` gets an auth identity.
- Login returns a **session token**.
- Every route reads the user from the token instead of trusting `user_id` from the app. Keep the `X-DTI-Key` too, for the tunnel.
- **Decided:** login is the **last** item this sprint. The one-tap team accounts stay as they are until then.

Owners: Nabil (auth routes + token check), Adam (core `Api` sends the token), Ryan (screens).

## 5. Speed

- Most of the slowness is venue Wi-Fi plus the tunnel. Optimistic likes (3.3) and paged comments (3.4) hide it.
- Also: the JSON store rewrites its whole file on every write (~6 MB with 3,188 products), so every like or comment write takes longer as data grows. **Nabil:** keep hot collections (likes, comments, carts) in small files, or batch writes. Measure first.

## 6. Database rebuild (reset everything except the Apify catalog)

**Goal:** keep only the products we pulled from Apify (the committed 3,188-product snapshot and its raw pulls), and reset everything generated or user-made, for everyone.

| Collection / folder | Keep or reset | Why |
| --- | --- | --- |
| `products` | **Reset to the snapshot**: `load_products --replace` | Drops live-search items, seed placeholders and anything ingested on the server only. Keeps AI tags + department (they're in the snapshot). |
| `seed/raw/*` (git) | Keep | The Apify pulls; re-normalizing is free |
| `users` | Reset | Everyone re-onboards (or logs in, section 4) |
| `closet_items`, `fits`, `fit_cache` | Reset | The "stinky" generated closet matches and fits |
| `fitcheck_posts` | Reset: **decided, Inspo starts empty** | |
| `carts`, `orders`, `swipes`, `wishlist` | Reset | |
| `pair_cache`, `tryon_cache`, `uploads/`, `tryon/` | Reset | Generated reasons, try-on images and uploaded photos (incl. body photos: privacy win) |
| `ai_usage` | Reset | Fresh budget counter |
| `tag_cache`, `summary_cache` | **Keep [decide]** | Catalog-only AI results. Keeping them makes re-tagging and summaries free; dropping them costs ~$1 to regenerate. |
| `live_search_cache` | Reset | Live Apify search results not in the snapshot |
| `nessie` | Keep merchant ids, reset per-user customers/accounts | Merchants are created once; users get fresh Nessie accounts on their first checkout. The old sandbox purchases stay in Nessie, which is fine. |

**How:**
- **Nabil** writes `scripts/rebuild_db.py`: `--dry-run` prints what would be deleted with counts; the real run **first copies the data dir to `data.bak-<timestamp>`**, then resets the collections above, then runs `load_products --replace`. It works on the JSON store and Firestore.
- **Adam** runs it on the shared server **after the council says go**, then `tag_catalog --summaries-only` (free with the kept cache) and restarts. Nabil does the same on the backup.
- **Then:** re-create the team accounts and the demo setup (body scan + closet) for whoever demos, so size badges and pairing work. `warm_demo` after.
- **[decide] When:** tonight before login lands (everyone re-onboards twice), or right after login lands (once). **Recommendation: after login.**

---

## Who does what (summary)

- **Nabil:**
  - `PUT` like (3.3) + paged comments (3.4) + `photo_w`/`photo_h` (3.1).
  - Login backend (4).
  - `rebuild_db.py` (6).
  - Store write speed (5).
- **Adam:**
  - Sizing (0.1), the catalog on the server (0.3).
  - Digitize every garment (1.1), honest catalog matching (1.2), outfit + pieces data (1.3).
  - Core for login / likes / comments.
  - Runs the rebuild.
- **Ryan:**
  - Store names (0.2), the closet upload route (1.1), outfits/pieces UI (1.3).
  - Remove "edit in cart" (2.1).
  - Inspo aspect ratio, margins, comment sheet, optimistic likes (3.1–3.4).
  - Login screens.

## Open questions for the council

1. Login (tackled last): **A**, **B** or **C**?
2. Rebuild: when? Login is now last, so "after login" may be late; tonight before the dry run is the other option. Keep `tag_cache` / `summary_cache` (free re-tagging)?

~~Closet catalog photos~~ (no) · ~~Inspo max height~~ (9:16) · ~~Inspo re-post~~ (start empty) · ~~team accounts~~ (stay): decided above.
