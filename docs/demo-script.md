# Demo script (3 minutes)

Rewritten Sat Oct 24 ~4 PM for the council flow (`docs/council-final-sprint.md`); **updated Sun Oct 25 ~3 AM for the sprint-4 redesign (Ryan's #71)**: Home is now **reels** (one product per screen, 3 photo slides), **swipe left/right between Home · Discover · Inspo**, and a lowercase **niche** header with **Liked · Bag · Closet** icons plus your avatar. Nabil runs the clock at the dry runs (17:30 / 18:30). **[confirm]** = depends on a screen in Ryan's sprint PR (not merged at the time of writing); check it at the first dry run, and if it isn't there, use the step's fallback. **[decide]** = a call for the team at the dry run. Who talks is a suggestion.

**Setup before a judge arrives:**
- **Demo phone:** team test profile (`u_demo`), charged, on venue Wi-Fi.
  - Body scan done for `u_demo` (Adam), so the **"in your size"** badges show. Without it every badge is blank.
  - `u_demo`'s **Shop for** (Men's / Women's / Both) matches whoever's clothes we're demoing **[decide]**.
- **Second phone:** a teammate's, logged in as someone else, for the live Inspo post.
- **Laptop:** backup video queued, and the Nessie purchase list open (`GET /accounts/{id}/purchases`).
- **Backend:**
  - Run `scripts.reset_demo`, then `scripts.warm_demo` (empty cart, warm feed and shops).
  - **Warm Home's slides (sprint 4):**
    - Open Home on the demo phone and scroll the first ~6 posts once, 15–20 minutes before judging. Each post pre-renders the next 3 try-ons (15–20 s each), so slide 2 ("on you") is instant on stage.
    - **Each account has a daily AI pre-render budget** (`PREFETCH_PER_USER_DAY`, 60 on the shared server tonight). After that, slide 2 shows a "try-on unavailable" card with a retry button. Don't burn them scrolling the demo account the night before; ask Adam to reset or raise the cap if needed.
    - `u_demo` needs a **body photo** (or slide 2 says "Add a photo of you") and **a few closet pieces** (or slide 3 shows empty "+ add from your closet" tiles).
  - Load Home once per team account after any server restart, so Claude's card reasons are cached (the first load takes ~7 s, then ~40 ms).
  - Then `smoke_e2e`: 10/10 within the last hour.
  - Nabil's backup server is running the same commit as the shared one.
- **Inspo:** Nabil's 3 real fits are posted (done), so the feed isn't empty if the live post fails.
- **Discover prop:** a jacket or shoe on the table to photograph (a teammate's, not a judge's).

---

## 0:00–0:15 · Hook (Nabil)

> "Shopping for one outfit means five tabs, five carts, and guessing your size five times. Tell Niche who you are once, and everything you see is in your size, in stock, goes with what you already own, and checks out in one tap across every store."

On screen: Home, already loaded.

## 0:15–0:40 · Onboarding, one screen per step (Ryan) [confirm] [decide: live or skip]

Only if we demo it live (25 s). Otherwise, say the line and start on Home.
- **New account, then step through:**
  1. **Your style:** type "y2k fits, baggy jeans, nothing skinny" (`POST /onboarding`).
  2. **Stores:** tap H&M + Uniqlo (`PATCH /users/{id}` `preferred_stores`).
  3. **Shop for:** pick one (`shop_for`).
  4. **Body scan:** height + a pre-taken full-body photo (`POST /users/{id}/body-scan`). The measurements screen comes up pre-filled.
  5. **Budget:** tap **Skip for now**.
- **Line:** "Every step past your style is skippable, and the photo stays private."
- **Fallback:** the team test profile is already onboarded. "We've set this one up already."

## 0:40–1:15 · Home as reels (Ryan drives, Adam narrates the AI)

- **One product fills the screen.** Swipe up for the next one (`GET /feed`). Slide through its 3 photos:
  1. **The item on its own:** the store's product shot (`hero_image_url`; 1,167 of 3,476 products have one, the rest use their main photo).
  2. **On you:** the item tried on *your* photo with pieces from your closet, already rendered before you got there (`tryon`, prefetched with `POST /feed/{user}/tryons`). Label: "on you".
  3. **Goes with:** a 2×2 grid of pieces **you already own** that go with it, accessories included (`closet_picks`). These are your own photos, never a store's.
- **Adam:** "Every post is a real listing pulled by Apify, in your size and in stock, ranked by Claude against your closet. Slide two is Gemini putting it on you, with the pieces from slide three."
- **Tap "see more":** the description, colour and the size Niche picked for you.
- **Add to cart** is the only button (`POST /cart/{user}/items`). It turns into "Added ✓" and the bag icon bounces. **Double-tap the photo** to like it: it shows up under Liked.
- **Add a Uniqlo item too,** so the cart has two stores.
- **Swipe sideways on the caption** (not the photo) to go to Discover. Sideways on the photo only flips slides.
- **Fallbacks:**
  - Slide 2 still says "Dressing you…": swipe on and come back; it's rendering (15–20 s).
  - Slide 2 says "try-on unavailable": tap **Retry**, or swipe on to slide 3 (your closet pieces). Never fake it with another photo.
  - The feed stalls: pull to refresh (reasons are cached). If the tunnel is down, switch the base URL to Nabil's backup. If that fails too, play the backup video from 0:40.

## 1:15–1:45 · Discover (Adam) [confirm]

- **Tap the camera icon in the search bar** and snap the jacket on the table (`POST /search/photo`).
- Two sections come back:
  - **Similar items:** look-alikes, in your size first.
  - **Goes with it:** pieces that complete it, with pieces you already own marked "From your closet".
- **Tap a similar item.** Home opens **seeded**: "Similar to: …", with that item first and more like it after (`GET /feed?seed=`).
- **Optional, 10 s:** type a vibe like **"fit for a rooftop party"** (`GET /search`). It shows what it understood ("streetwear · black") and real items.
- **Line:** "See something you like in real life? Snap it, and Niche finds it in your size."
- **Fallbacks:**
  - **Photo search returns 502** (the AI is busy): tap the **y2k** style chip instead (keyword search, no AI).
  - **Nothing found:** the photo had no clear garment. Retake it with the jacket flat on the table.

## 1:45–2:15 · Inspo (Adam posts, Ryan shows) [confirm]

- **A teammate posts an outfit-of-the-day** from the second phone (`POST /fitcheck`). The AI tags each piece in a few seconds.
- It shows up on the demo phone's Inspo feed (`GET /fitcheck/feed`; everyone's posts).
- **Tap the photo.** A tag pops up on each piece (Instagram-style), showing name · store · price.
- **Tap the jeans tag.** Home opens seeded with those jeans, then similar jeans in your size (`GET /feed?seed=`).
- **Line:** "It turns 'where'd you get that?' into one tap."
- **Fallbacks:**
  1. Use one of Nabil's real posts instead of a live upload.
  2. **No tag pins:** the post was made before the pins existed, so the tags show as a list. Tap one from the list.
  3. If the screen isn't built, play the backup video segment.

## 2:15–2:40 · One cart, two stores, one tap (Nabil)

- **Tap the cart icon** (top right). The cart is grouped into **H&M** and **Uniqlo**, each with its own subtotal (`GET /cart/{user}`).
- **Tap the pencil on an item and change the size** (`PATCH /cart/{user}/items/{id}`). It shows only sizes in stock, and the quantity stays.
- **Check out** (`POST /checkout/{user}`). The receipt shows **one `paid` purchase per store**.
- **Nabil:** "Those are two real Capital One Nessie purchases, one per store, from one tap." Flip the laptop to the Nessie purchase list.
- **Fallbacks:**
  - **A store comes back `nessie_failed`:** the receipt says "Paid $X of $Y" with **Retry payment** for that store (`POST /orders/{id}/retry`). The paid store is never charged twice.
  - **409 (sold out since added):** that's a feature. The item shows as unavailable, nothing is charged, and you can remove it.

## 2:40–2:50 · How it's built (Adam)

> "A Flutter app on iPhone, Android and web, and one FastAPI backend. Apify pulls the real catalog, Capital One Nessie runs checkout, Claude tags, ranks and searches, and Gemini does try-on. There's a fallback at every step, so nothing breaks on stage."

## 2:50–3:00 · Close (Nabil)

> "Styling apps tell you what to wear. Niche finds it in your size, matches it to your closet, and checks you out across every store in one tap."

---

## If something breaks

| Problem | Do this |
| --- | --- |
| Adam's Mac or the tunnel dies | Switch the app's base URL to Nabil's backup server (same key). |
| Anthropic credits run out | Nothing to do: text falls back to Gemini (drilled Sat 2:05 AM, smoke 10/10). |
| Claude **and** Gemini both down | Feed reasons come from rules, slide 2 shows its "try-on unavailable" card, and cart, checkout and seeded Home still work. **What fails is new photo work:** photo search, closet scans, and auto-tags on a live post. Use the style chips, and a pre-posted real fit instead. |
| Body scan fails | It falls back to height/weight estimates (`source: "estimate"`). Or type the measurements in; the size badges work either way. |
| Try-on fails, or the account's daily pre-renders are used up | Slide 2 shows "try-on unavailable" with **Retry**. Warmed try-ons are cached, so warm the first posts before judging. |
| Nessie fails | **Retry payment** on the receipt; the order is saved as `nessie_failed`. Show the evidence table in `docs/devpost.md`. |
| The iPhone build fails | Demo the Android build, or the web build in Chrome on the laptop. |
| Everything fails | Play the backup video and narrate it live. |

## Judge Q&A crib

- **Is the data real?**
  - Yes: 3,476 products from 8 stores (H&M, Uniqlo and six Shopify brands like Princess Polly, Kith and Stüssy), via three Apify actors, with per-size stock (1,922 women's, 1,218 men's, 336 unisex), including shoes from H&M, Princess Polly and Kith and accessories from six stores.
  - It's a snapshot taken at ingest. The only live scraping is photo search and "shop this fit": if a piece isn't in our catalog, it searches H&M live (capped and cached).
- **Is the payment real?** Yes, against Capital One's Nessie sandbox API: one purchase per store, and each one can be checked by its purchase id.
- **How does it know my size?**
  - From what you tell it, or from a body scan: one photo plus your height gives estimated measurements, which you confirm.
  - Sizing itself is rules, not AI, so it's instant and free. You only see sizes that are actually in stock.
- **What if the AI is wrong?**
  - Product-name hints cut wrong tags from 37 to 0 out of 418.
  - You can fix the tags on your own posts.
  - Every AI step has a fallback.
- **Privacy?**
  - Your body photo is private: it's used only for your own sizing and try-on, and you can delete it.
  - Location data (GPS) is stripped from every uploaded photo.
  - Inspo posts are public by design. API keys never leave the server.
- **What does it cost?** About $0.07 to tag the whole catalog. A hard cap stops AI spend at $5 **[confirm the live total at `/ai/usage`]**.
- **Tests?** 425 backend tests, plus the app's Flutter tests.
