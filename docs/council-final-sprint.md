# Council: final sprint (key features + user flow)

Sat Oct 24, 2026, ~3 PM PT. Written from Nabil's brain-dump, checked against `staging` and Ryan's latest handoff (`RYAN_TO_ADAM.md`, onboarding + automatic sizing + cart pencil, PR #18). **[assumption]** marks something we filled in; strike it or keep it at the council. Open questions are at the bottom.

**The pitch in one line:** tell Niche who you are once, and every item you see is in your size, in stock, goes with what you own, and is one tap from checkout.

---

## Decisions already made (Nabil, 3 PM)

| # | Decision | What it means |
| --- | --- | --- |
| D1 | **Google sign-in is a stretch goal** | Back-burner. Until then the app creates a user with `POST /users` and keeps its id on the device. |
| D2 | **Body scan = AI estimates measurements** | The user uploads a full-body photo, AI suggests height/chest/waist/hips/inseam, and the user confirms or edits each one. The same photo powers try-on. New AI work (Adam). |
| D3 | **Discover uses soft size ranking** | Show everything in stock; items in the user's size come first and carry an "in your size" badge. An item not in their size says so; it is never hidden. |
| D4 | **Inspo is one feed for everyone** | Every post is visible to every user. No follow system. "See what your friends wear" is the framing, not an access rule. |
| D5 | **Onboarding answers live on the server** | Measurements, sizes, fit, stores, looks and budgets are saved to the user profile, so feed ranking, sizing and AI all use them (Ryan's request #1). |
| D6 | **One screen per onboarding step** | Every optional step has **Skip for now**. Everything can be edited later from Profile. |

---

## The user flow

```
[Sign in] -> Onboarding (1 screen per step) -> Discover (Quick Browse) <-> Cart -> Checkout
                                                   ^
                    Closet (digitize what you own) |   Inspo (OOTD feed) -> tap photo -> tags -> tap a tag
                                                   |__________________________________________________|
                                                        Quick Browse seeded with that item
```

**Tabs [assumption]:** Discover · Closet · Inspo · Profile, with Cart as an icon on Discover (badge = item count). Today the app has three tabs, and Closet is under Profile.

### 0. Sign in (stretch)
- Google OAuth, back-burner (D1). For the demo: open the app, get a fresh user, go straight to onboarding. Or use a pre-onboarded `u_demo` (open question Q6).

### 1. Onboarding, one screen per step

| Screen | What the user does | Required? | Saved to | Status |
| --- | --- | --- | --- | --- |
| 1. Welcome | "Let's make Niche yours", Start / Skip setup | — | — | Built (Ryan) |
| 2. Your style | Plain English: looks they're going for ("y2k fits", "clean minimal, earth tones"), what they like and hate wearing | Optional, but we nudge | `style_text` → parsed by `POST /onboarding` | Built (one combined screen today; split it) |
| 3. Stores you like | Chips for the stores we carry (H&M, Uniqlo) + a free-text "others you love" **[assumption]** | Skip for now | `preferred_stores` (new) | **Missing** |
| 4. Body scan | Full-body photo → AI estimates measurements → the next screen comes pre-filled. Photo stays private. **[assumption: scan goes before screen 5 so it can pre-fill it]** | Skip for now | `body_photo_url` (exists), estimates feed screen 5 | **Missing** (photo upload exists; estimation is new) |
| 5. Measurements & size | Height, weight, chest, waist, hips, inseam, shoe size; preferred fit (slim/regular/oversized); usual size per category (top/bottom/shoes) | Skip for now | `measurements`, `fit`, `usual_sizes` (new, server) | Built in the app, **saved on the phone only** |
| 6. Budget | Max price per category: tops, bottoms, jackets, shoes, each blank-able | Skip for now | `price_ranges` (exists) | Built |
| 7. Done | "Your feed is ready" → Discover | — | `onboarded: true` (new) | Partial |

### 2. Discover (Quick Browse)
- One product per screen, continuous scroll (Ryan, PR #18). Each card: photos, price, the AI reason ("goes with your black cargo pants"), a size badge, Add to Cart.
- **Ranking:** the AI pairs each item with the user's closet + style + budget (built). **New:** in-your-size items first (D3) and preferred stores boosted.
- **Size:** chosen automatically from measurements / usual size; only in-stock sizes can be chosen (built, Ryan). Not in their size → "not in your size: try M?" instead of hiding the item.
- From a card: try-on on your own photo, complete the look + Fit Score, save to wishlist (built).

### 3. Cart → checkout
- Grouped by store, one checkout, one Nessie purchase per store, per-store receipts (built, verified 4/4 `paid`).
- **Pencil icon on each item** → change size (in-stock sizes only), quantity preserved (built in the app). It's two calls today (add new, remove old), so it can half-fail; **an atomic size-change route is needed** (Ryan's request #3, Nabil).
- A failed store payment can be retried without re-charging the others (PR #20, open).

### 4. Closet (digitize what you own)
- Snap a photo → AI tags it (category, color, pattern, style) → it's in your digital closet. Possible-duplicate warning (built).
- **Why it matters:** Discover ranks new items by what goes with your closet, and complete the look uses owned pieces first.
- **"Pictures of them" [assumption]:** a mirror selfie of a whole outfit should add *each* piece. Today one photo = one item. Multi-item is a stretch (it can reuse the Fit Check tagger `/ai/tag-fit`).

### 5. Inspo (social OOTD)
- One feed of everyone's outfit-of-the-day posts (D4): post photo + caption, like, comment (built as "Fit Check" / "Social"; rename to **Inspo**).
- **Tap the photo → tags appear on each piece, like Instagram's people tags.** Each tag shows what it is + where to buy it ("Baggy jeans · H&M · $34.99"). Tags are AI-made at post time (built) and can be fixed by the poster (built).
- **Tap a tag → Quick Browse seeded with that item:** the item first, then similar items (same category/color/style, in your size first, ranked against your closet). **Missing: needs a "similar to this" feed.**
- "Shop this fit" for the whole outfit still works (built).
- Tag positions on the photo **[assumption]:** the tagger doesn't return x/y today. For the sprint, show a tag list overlaid on the photo (or pins in a fixed stack). Real pin positions are a stretch (the AI returns a box per item).

### 6. Profile
- Edit every onboarding answer, Style DNA (built), orders, closet shortcut, body photo (private) with delete.

---

## What's left: the sprint list

**P0 = needed for the demo flow above. P1 = makes it feel finished. Stretch = only if time.** Freeze is 17:00 per the plan; the council should confirm (Q7).

### Nabil (commerce backend)
| Pri | Task | Notes |
| --- | --- | --- |
| P0 | **Profile on the server:** add `measurements {height_cm, weight_kg, chest_cm, waist_cm, hips_cm, inseam_cm, shoe_us}`, `fit`, `usual_sizes {top, bottom, shoes}`, `preferred_stores`, `onboarded` to `User`; `PATCH /users/{id}` accepts them | All optional, so existing users stay valid. Ryan swaps local storage for this. |
| P0 | **Discover soft size ranking:** `/feed` puts in-your-size items first and adds `your_size` + `in_your_size` to each card; boost preferred stores | Uses the same size logic as `POST /size`. |
| P0 | **Similar-items feed:** `GET /feed?seed=<product_id>`: the seed first, then similar items | The Quick Browse entry point from an Inspo tag. Ranking by similarity can start rule-based (category + color + style tags); Adam can swap in AI. |
| P0 | **Inspo: one feed for everyone** | `/fitcheck/feed` ignores friends lists (D4). |
| P1 | **Atomic cart size change:** `PATCH /cart/{user_id}/items/{product_id}` `{size, new_size}` | Keeps quantity and merges into an existing line of the new size. |
| P1 | Merge PR #20 (order retry) + #21 (photo GPS strip) | Open now. |

### Adam (AI + hosting)
| Pri | Task | Notes |
| --- | --- | --- |
| P0 | **Body scan:** `POST /users/{id}/body-scan` (photo) → `{height_cm?, chest_cm, waist_cm, hips_cm, inseam_cm, confidence, note}` | Needs a known reference: ask the user's height first, or estimate everything relative to it. The user always confirms. Photo is private. |
| P0 | **Strip EXIF/GPS in `_save_upload`** | Body photos and closet selfies are going through it now (details in `NABIL_TO_ADAM.md`). |
| P1 | Use `preferred_stores`, `usual_sizes`, `fit` in `pair()` / reasons | Once the profile fields exist. |
| P1 | Tag quality: the weak spots from the real photos (collared shirt → tees, women's items on men's fits, watches) | `NABIL_TO_ADAM.md`, 2:45 PM. |
| Stretch | Tag pin positions (x/y per item); multi-item closet from one outfit photo | |
| — | Merge PR #19 (fast feed) + #17; restart the shared server after merges | |

### Ryan (app + design)
| Pri | Task | Notes |
| --- | --- | --- |
| P0 | **Onboarding as one screen per step** (screens 1–7 above) with Skip for now; saves to the server profile | Most of the fields exist; this is splitting + the stores screen + the scan screen. |
| P0 | **Tabs:** Discover · Closet · Inspo · Profile (+ cart icon) | Rename Social → Inspo; Closet becomes a tab. |
| P0 | **Inspo tag overlay:** tap photo → tags on each piece (name · store · price); tap a tag → Quick Browse with `seed=<product_id>` | |
| P0 | Discover: "in your size" badge / "not in your size" note | From the new card fields. |
| P1 | Cart pencil on the atomic route once it lands | Already built on two calls. |
| P1 | Merge PR #18 | |

### Everyone
- 17:30 / 18:30 dry runs with the new flow; Devpost "What it does" rewritten to match this doc (Nabil); the demo script follows the flow above.

---

## Demo script outline (follows the flow) [assumption]
1. Fresh user → onboarding: type "y2k fits, baggy jeans, no skinny anything" → stores → body scan pre-fills measurements → skip budget.
2. Discover: every card in your size, with a reason tied to your closet → add to cart → pencil to change size → checkout, two stores, `paid` in Nessie.
3. Inspo: tap a friend's OOTD → tags pop up → tap the jeans → Quick Browse full of similar jeans in your size.
4. Closet: snap a jacket → it's tagged → Discover now pairs with it.

---

## Open questions for the council

1. **Closet input:** one item per photo (works today), or a whole-outfit photo that adds every piece (stretch)?
2. **Onboarding order:** body scan *before* measurements so it pre-fills them (our assumption), or as you listed (measurements, then scan)?
3. **Stores screen:** we only carry H&M + Uniqlo. Show just those two, or also let people type others (saved as "stores you want", a Devpost "what's next" signal)?
4. **Tag details:** does a tag show the *matched catalog item* (name, store, price, tappable), or only "what it is" + store?
5. **Body scan accuracy:** what do we say on screen? Suggested: "Estimates from your photo. Check them, they're a starting point." Do we keep the photo after the scan (needed for try-on) or delete it?
6. **Demo user:** onboard live on stage (more impressive, more risk) or start pre-onboarded?
7. **Freeze:** this list is bigger than 2 hours. Keep 17:00 and cut to P0 only, or move the freeze?
8. **Inspo tab:** besides friends' posts, should Inspo also show "similar items from public OOTDs" as a section, or is "tap a tag → similar items" enough?
