# Council: final sprint (key features + user flow)

Sat Oct 24, 2026, ~3:30 PM PT. Written from Nabil's brain-dump and the council discussion, checked against `staging` and Ryan's latest handoff (`RYAN_TO_ADAM.md`: onboarding, automatic sizing, cart pencil, PR #18). **[assumption]** marks something we filled in; strike it or keep it at the council. Open questions are at the bottom.

**The pitch in one line:** tell Niche who you are once, and every item you see is in your size, in stock, goes with what you own, and is one tap from checkout.

---

## Decisions

| # | Decision | What it means |
| --- | --- | --- |
| D1 | **Google sign-in is a stretch goal** | Back-burner. Until then the app creates a user with `POST /users` and keeps its id on the device. |
| D2 | **Body scan = AI estimates measurements** | The user uploads a full-body photo, AI suggests height/chest/waist/hips/inseam, and the user confirms or edits each one. The same photo powers try-on. New AI work (Adam). |
| D3 | **Soft size ranking** | Show everything in stock; items in the user's size come first with an "in your size" badge. An item not in their size says so; it is never hidden. |
| D4 | **Inspo is one feed for everyone** | Every post is visible to every user. Tapping a name shows that person's posts. No follow system. |
| D5 | **Onboarding answers live on the server** | Measurements, sizes, fit, stores, looks and budgets are saved to the user profile, so ranking, sizing and AI all use them (Ryan's request #1). |
| D6 | **One screen per onboarding step** | Every optional step has **Skip for now**. Everything is editable later under the User icon. |
| D7 | **Three tabs on a floating island at the bottom: Home · Discover · Inspo** | "Quick Browse" is renamed **Home** and is the first screen after onboarding. |
| D8 | **Four persistent icons, top right, on every page: Liked → Cart → Closet → User** | Liked = wishlist; Closet = the digitized closet; User = profile + onboarding answers + settings. |
| D9 | **Every item tap lands on Home, seeded** | Tapping an Inspo tag or a Discover result restarts Home's feed with that item first, then similar items in your size. One way of browsing, everywhere. |
| D10 | **Discover search results = a grid with two sections** | "Similar items" (look-alikes of the query/photo) and "Goes with it" (pieces that complete it, paired with your closet). |
| D11 | **Discover before a search = style chips + trending** | Chips from our catalog's style tags; one tap runs that search. |

---

## Layout

```
 ┌──────────────────────────────────────┐
 │ Niche              ♡   🛒   👕   👤  │  <- persistent on every page: Liked, Cart, Closet, User
 │                                      │
 │            (current tab)             │
 │                                      │
 │      ╭───────────────────────────╮   │
 │      │  Home   Discover   Inspo  │   │  <- floating island tab bar
 │      ╰───────────────────────────╯   │
 └──────────────────────────────────────┘
```

**Icon badges [assumption]:** Cart shows the item count; Liked shows nothing (the count would be noise).

## The user flow

```
[Sign in] -> Onboarding (1 screen per step) -> Home
Home       : scroll recommended items -> add to cart / like
Discover   : type "y2k fits" or 📷 a photo -> grid: Similar | Goes with it -> tap -> Home (seeded)
Inspo      : OOTD feed -> tap photo -> tags on each piece -> tap a tag -> Home (seeded)
Top right  : ♡ Liked · 🛒 Cart -> checkout · 👕 Closet (add photos) · 👤 User (edit everything)
```

### 0. Sign in (stretch)
- Google OAuth, back-burner (D1). For the demo: open the app, get a fresh user, go straight to onboarding. Or start from a pre-onboarded `u_demo` (open question Q6).

### 1. Onboarding, one screen per step

| Screen | What the user does | Required? | Saved to | Status |
| --- | --- | --- | --- | --- |
| 1. Welcome | "Let's make Niche yours", Start / Skip setup | — | — | Built (Ryan) |
| 2. Your style | Plain English: looks they're going for ("y2k fits", "clean minimal, earth tones"), what they like and hate wearing | Optional, but we nudge | `style_text` → parsed by `POST /onboarding` | Built as one combined screen; split it |
| 3. Stores you like | Chips for the stores we carry (H&M, Uniqlo) + a free-text "others you love" **[assumption]** | Skip for now | `preferred_stores` (new) | **Missing** |
| 4. Body scan | Full-body photo → AI estimates measurements → screen 5 comes pre-filled. Photo stays private. **[assumption: scan goes before screen 5 so it can pre-fill it]** | Skip for now | `body_photo_url` (exists); estimates feed screen 5 | **Missing** (photo upload exists; estimation is new) |
| 5. Measurements & size | Height, weight, chest, waist, hips, inseam, shoe size; preferred fit (slim/regular/oversized); usual size per category (top/bottom/shoes) | Skip for now | `measurements`, `fit`, `usual_sizes` (new, server) | Built in the app, **saved on the phone only** |
| 6. Budget | Max price per category: tops, bottoms, jackets, shoes, each blank-able | Skip for now | `price_ranges` (exists) | Built |
| 7. Done | "Your feed is ready" → Home | — | `onboarded: true` (new) | Partial |

### 2. Home (tab 1, the first screen after onboarding; was "Quick Browse")
- One product per screen, continuous scroll (Ryan, PR #18). Each card: photos, price, the AI reason ("goes with your black cargo pants"), a size badge, Add to Cart, Like.
- **Ranking:** the AI pairs each item with the user's closet + style + budget (built). **New:** in-your-size items first (D3) and preferred stores boosted.
- **Size:** chosen automatically from measurements / usual size; only in-stock sizes can be chosen (built, Ryan). Not in their size → "not in your size: try M?", never hidden.
- **Seeded mode (D9):** opened from an Inspo tag or a Discover result, Home shows that item first, then similar items. **[assumption]** A small "Similar to: Baggy jeans ✕" chip at the top; ✕ returns to the normal feed.
- From a card: try-on on your own photo, complete the look + Fit Score (built).
- **Like [assumption]:** a heart on the card (double-tap also works, as it does today) → saves to Liked.

### 3. Discover (tab 2, search)
- **Search bar with a camera button on the left.** The camera opens a choice: take a photo / pick from camera roll.
- **Text search:** a style ("y2k"), an item ("baggy jeans") or a vibe ("fit for a rooftop party").
  - Styles and items work today with keyword search (`GET /products?q=`). The catalog's style tags are minimalist (312 items), classic (285), streetwear (220), athleisure (194), y2k (42), preppy (41), vintage (39), grunge (32), business (30) and boho (16).
  - **Vibes need AI:** turn the sentence into styles + categories + colors, then search (P1, Adam).
- **Photo search:** upload → the AI tags each piece in the photo (`/ai/tag-fit`, built) → find matches (`/ai/shop-fit`, built: it powers Inspo's "shop this fit"). Only a thin route that takes the photo upload is missing.
- **Results (D10):** a grid with two sections:
  - **Similar items:** look-alikes of the query or of each piece in the photo, in your size first.
  - **Goes with it:** pieces that complete the look, paired with your closet (complete the look, built).
  - Tap any result → Home, seeded (D9).
- **Before a search (D11):** style chips (the tags above) + a row of trending items **[assumption: "trending" = most liked/carted across users, falling back to the top of the user's feed]**.

### 4. Inspo (tab 3, social OOTD)
- One feed of everyone's outfit-of-the-day posts (D4): post photo + caption, like, comment. Built as "Fit Check" / "Social"; rename it **Inspo**.
- **Tap the photo → tags appear on each piece, like Instagram's people tags.** Each tag shows what it is + where to buy it ("Baggy jeans · H&M · $34.99"). Tags are AI-made at post time and the poster can fix them (both built).
- **Tap a tag → Home, seeded with that item (D9).** **Missing: needs the "similar to this" feed.**
- "Shop this fit" for the whole outfit still works (built).
- **Tag positions [assumption]:** the tagger doesn't return x/y today, so for the sprint show the tags as a list over the photo. Real pins on each piece are a stretch (the AI would return a box per item).
- **New post** = a + button on Inspo **[assumption]**.

### 5. Top-right icons (on every page)
| Icon | Opens | Status |
| --- | --- | --- |
| ♡ **Liked** | Grid of liked items → tap → Home (seeded) or add to cart | Wishlist routes built (`PUT/DELETE /wishlist/...`); screen needs a home |
| 🛒 **Cart** | Grouped by store, **pencil on each item to change size** (in-stock sizes only, quantity kept), one checkout = one Nessie purchase per store, per-store receipts, order history | Built (4/4 `paid` verified). The pencil is two calls today (add, then remove) and can half-fail, so it needs an **atomic size-change route** (Ryan's request #3). Failed payments can be retried (PR #20). |
| 👕 **Closet** | Your digitized closet: snap a photo → AI tags it → saved; duplicate warning; delete | Built. **[assumption]** one item per photo; a whole-outfit selfie adding every piece is a stretch (it can reuse `/ai/tag-fit`). |
| 👤 **User** | Edit every onboarding answer (one section per step), Style DNA, body photo (private, with delete), orders, settings (server connection, sign out / reset) | Style DNA + preferences built; needs regrouping |

---

## What's left: the sprint list

**P0 = needed for the demo flow above. P1 = makes it feel finished. Stretch = only if time.** Freeze is 17:00 per the plan; the council should confirm (Q7).

### Nabil (commerce backend)
| Pri | Task | Notes |
| --- | --- | --- |
| P0 | **Profile on the server:** add `measurements {height_cm, weight_kg, chest_cm, waist_cm, hips_cm, inseam_cm, shoe_us}`, `fit`, `usual_sizes {top, bottom, shoes}`, `preferred_stores`, `onboarded` to `User`; `PATCH /users/{id}` accepts them | All optional, so existing users stay valid. Ryan swaps local storage for this. |
| P0 | **Home soft size ranking:** `/feed` puts in-your-size items first and adds `your_size` + `in_your_size` to each card; boost preferred stores | Uses the same size logic as `POST /size`. |
| P0 | **Seeded Home:** `GET /feed?seed=<product_id>`: the seed first, then similar items | The landing for Inspo tags and Discover results (D9). Starts rule-based (category + color + style tags); Adam can swap in AI. |
| P0 | **Discover photo search route:** `POST /search/photo` (multipart) → `{tags, similar: [...], goes_with: [...]}` | Wraps the built `tag_fit` + `shop_fit` + complete-look; strips GPS before saving. |
| P0 | **Discover text search:** `GET /search?q=` → `{similar, goes_with}`; style chips = `GET /search/styles` (tags + counts) + trending | Keyword search exists (`GET /products?q=`); this adds the two sections and the chips. |
| P0 | **Inspo: one feed for everyone** | `/fitcheck/feed` ignores friends lists (D4); `?author=` for a person's posts. |
| P1 | **Atomic cart size change:** `PATCH /cart/{user_id}/items/{product_id}` `{size, new_size}` | Keeps quantity and merges into an existing line of the new size. |
| P1 | Merge PR #20 (order retry) + #21 (this doc + photo GPS strip) | Open now. |

### Adam (AI + hosting)
| Pri | Task | Notes |
| --- | --- | --- |
| P0 | **Body scan:** `POST /users/{id}/body-scan` (photo) → `{height_cm?, chest_cm, waist_cm, hips_cm, inseam_cm, confidence, note}` | Needs a known reference: ask the user's height first, and estimate the rest relative to it. The user always confirms. Photo is private. |
| P0 | **Strip EXIF/GPS in `_save_upload`** | Body photos, closet selfies and photo searches all go through it (details in `NABIL_TO_ADAM.md`). |
| P1 | **Vibe search:** sentence → `{styles, categories, colors}` for Discover text search | "Fit for a rooftop party" → smart casual, dark colors, etc. |
| P1 | Use `preferred_stores`, `usual_sizes`, `fit` in `pair()` / reasons | Once the profile fields exist. |
| P1 | Tag quality: the weak spots from the real photos (collared shirt → tees, women's items on men's fits, watches) | `NABIL_TO_ADAM.md`, 2:45 PM. |
| Stretch | Tag pin positions (x/y per item); multi-item closet from one outfit photo | |
| — | Merge PR #19 (fast feed) + #17; restart the shared server after merges | |

### Ryan (app + design)
| Pri | Task | Notes |
| --- | --- | --- |
| P0 | **Shell:** floating island tab bar (Home · Discover · Inspo) + top-right Liked · Cart · Closet · User on every page | Rename Quick Browse → Home, Social → Inspo. Closet and Liked move out of Profile. |
| P0 | **Onboarding as one screen per step** (screens 1–7) with Skip for now; saves to the server profile | Most fields exist; this is splitting + the stores screen + the scan screen. |
| P0 | **Discover:** search bar with camera button (camera / camera roll), chips + trending, two-section results grid | |
| P0 | **Inspo tag overlay:** tap photo → tags (name · store · price); tap a tag → seeded Home | |
| P0 | **Home seeded mode** ("Similar to: … ✕") + "in your size" badge | |
| P1 | Liked screen; User screen regrouped by onboarding step | |
| P1 | Cart pencil on the atomic route once it lands | Already built on two calls. |
| P1 | Merge PR #18 | |

### Everyone
- 17:30 / 18:30 dry runs with the new flow; Devpost "What it does" rewritten to match this doc (Nabil); the demo script follows the flow below.

---

## Demo script outline (follows the flow) [assumption]
1. Fresh user → onboarding: type "y2k fits, baggy jeans, no skinny anything" → stores → body scan pre-fills measurements → skip budget.
2. **Home:** every card in your size, with a reason tied to your closet → add to cart → cart pencil to change size → checkout across two stores, `paid` in Nessie.
3. **Discover:** snap a friend's jacket → "Similar items" + "Goes with it" → tap one → Home seeded with it.
4. **Inspo:** tap a friend's OOTD → tags pop up → tap the jeans → Home full of similar jeans in your size.
5. **Closet:** snap a jacket → it's tagged → Home now pairs with it.

---

## Open questions for the council

1. **Closet input:** one item per photo (works today), or a whole-outfit photo that adds every piece (stretch)?
2. **Onboarding order:** body scan *before* measurements so it pre-fills them (our assumption), or as listed (measurements, then scan)?
3. **Stores screen:** we only carry H&M + Uniqlo. Show just those two, or also let people type others (saved as "stores you want", a Devpost "what's next" signal)?
4. **Tag details:** does a tag show the *matched catalog item* (name, store, price), or only "what it is" + store?
5. **Body scan accuracy:** what do we say on screen? Suggested: "Estimates from your photo. Check them, they're a starting point." Do we keep the photo after the scan (needed for try-on) or delete it?
6. **Demo user:** onboard live on stage (more impressive, more risk) or start pre-onboarded?
7. **Freeze:** this list is bigger than ~1.5 hours. Keep 17:00 and cut to P0 only, or move the freeze?
8. **Trending in Discover:** most liked/carted across users (needs a little traffic), or simply the top of your own Home feed?
9. **Liked vs Closet:** can you mark a liked item as "I bought this / own it" so it moves into Closet?
