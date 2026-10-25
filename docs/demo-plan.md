# Niche demo video plan (≈ 110 s)

Sun Oct 25 ~4 AM. For Devpost + the 2-min demo. Companion to `docs/demo-script.md` (the live 3-min stage script); this one is for the **edited video** made with Claude Design. The shot list is also at `~/Desktop/Pics/demo/SHOTLIST.md` for the extraction agent.

Palette (from `app/lib/features/shared/niche_theme.dart`): cream `#FFFBF0`, paper `#FBF3EE`, merlot `#5B1F33`, wine `#722F42`, hook `#E9B9A8`, blush `#F0E5E5`, stone `#EDEAE4`, ink `#1E1517`, muted `#7A6A6E`. Type: Young Serif (wordmark/display) + Manrope (UI).

Account for every shot: **u_adam** (28 clean closet pieces, 9 outfits, 150 pre-rendered try-ons). Simulator: iPhone 17 Pro `CBB994A5-0FAA-434A-825F-82C4500487A9`.

## 1. Storyboard

| # | Time | Beat | Screen | Action | On screen | Caption (kinetic) / voice |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0:00–0:06 | Hook | Title card (not app) | — | Arch icon drops in, "niche" wordmark, merlot on cream | "Five stores. Five carts. Five size guesses." → "Or one app that already knows you." |
| 1 | 0:06–0:18 | Onboarding | Welcome → style → stores → body scan | Tap "Let's go", type a style line, tap H&M + Uniqlo, add a full-body photo | Arch animation, chips selecting with haptics, drop-zone card, "Your feed is ready" beat | "Tell it who you are. Once." |
| 2 | 0:18–0:42 | Home as reels | Home | Flick up through 3 posts; on post 2 swipe slides 1→2→3; tap "see more"; tap Add to cart | Slide 1 hero shot → slide 2 **on you** (your real photo, one garment swapped) → slide 3 2×2 of your own pieces; pill morphs to "Added ✓", bag bounces | "Real listings. In your size." → "On you, before you even swipe." → "With what's already in your closet." |
| 3 | 0:42–1:00 | Closet | Closet pieces → Outfits → one outfit → Fit Score → Create 3 fits | Scroll the pieces grid, tap Outfits, open one, tap Fit Score, tap Create 3 fits | White-background pieces (earbuds, overcoat, boots, tee), the outfit with its pieces row, "72 · as classic" with 8 bars, three outfits from your own closet | "Snap a pile of clothes. It becomes your closet." → "Every fit, scored." |
| 4 | 1:00–1:18 | Inspo / social | Inspo feed → a post → Find similar look | Tap 🔥 reaction, tap "Similar" (top-right), expand one item's dropdown | Reactions row bottom-left, Similar sheet: "You already own" first, then shop rows, "Shop the whole look" | "'Where'd you get that?' is now one tap." |
| 5 | 1:18–1:34 | Discover → cart → checkout | Discover → camera search → cart → receipt | Tap camera, snap a jacket, tap a result, open Bag, change a size, Check out | Similar / Goes with it; cart grouped H&M + Uniqlo; receipt: one paid purchase per store | "Snap it. Find it. One cart, every store, one tap." |
| 6 | 1:34–1:44 | How it's built | Diagram card (not app) | — | Flutter · FastAPI · Apify · Claude · Gemini · Capital One Nessie, one line each | "Real catalog, real checkout, AI only where it earns it." |
| 7 | 1:44–1:50 | Close | Title card | — | Wordmark + icon, dark variant, "niche" | "Real clothes in your size that go with yours." |

Beats 2, 3 and 4 are the money shots; cut the others first if it runs long.

## 2. Shot list (for the extraction agent)

Save everything to `~/Desktop/Pics/demo/`. Static = `xcrun simctl io booted screenshot <file>`; video = `xcrun simctl io booted recordVideo --codec h264 <file>` (Ctrl-C to stop), 10–20 s each, then let Design trim. Light unless marked. Set the simulator to **9:41, full battery** (`xcrun simctl status_bar booted override --time 9:41 --batteryLevel 100 --batteryState charged --wifiBars 3 --cellularBars 4`). Log in as **u_adam** via the team button. Record every scrolling/animation beat as video; take a PNG of each "rest" state too.

| File | Screen / state | Type | Must be visible |
| --- | --- | --- | --- |
| `01-welcome.png` | Fresh install → welcome page | PNG | Arch animation settled, mosaic, "Let's go" pill, step dots |
| `01-onboarding.mp4` | Welcome → style → shop-for → stores → body scan → done | video | Chip select animation, drop-zone card, "Your feed is ready" beat. Use a new account (any team button then "new"), skip budget |
| `02-home-slide1.png` | Home, post 2, slide 1 | PNG | Hero product shot, store caps, name, price, "see more", Add to cart pill, 3-bar indicator |
| `02-home-slide2.png` | Same post, slide 2 | PNG | **"on you"** label; Adam's real photo with the garment swapped (status ready, not "Dressing you…", not the outfit board) |
| `02-home-slide3.png` | Same post, slide 3 | PNG | 2×2 grid of Adam's own clean-shot pieces, different categories |
| `02-home-seemore.png` | Same post, "see more" open | PNG | Description, colour, "in your size: M" line |
| `02-home-reels.mp4` | Home from post 1, flick up 4 posts, swipe slides on post 2, tap see more, tap Add to cart, double-tap like | video | Snap scrolling, "Added ✓" morph, bag bounce |
| `02-home-dark.png` | Home post 2 slide 2, dark mode (`xcrun simctl ui booted appearance dark`) | PNG | Same as slide 2 in dark |
| `03-closet-pieces.png` | Closet, pieces tab | PNG | White-background pieces incl. earbuds, overcoat, boots; brand label only on Carhartt |
| `03-closet-outfits.png` | Closet, Outfits view | PNG | One card per photo, pieces thumbnail row, "In Inspo" badge on one |
| `03-outfit-fitscore.png` | An outfit opened, Fit Score shown | PNG | Big score, style label ("as classic"), 8 category bars |
| `03-create-3-fits.png` | After tapping Create 3 fits | PNG | Three outfit boards made only from closet pieces (needs PR "fits closet-only" merged; else skip) |
| `03-closet.mp4` | Scroll pieces → Outfits → open one → Fit Score → Create 3 fits | video | Score counting up, fits appearing |
| `04-inspo-feed.png` | Inspo feed, a post with reactions | PNG | Reaction counts bottom-left, comment next to it, "Similar" pill top-right, no Fit Score |
| `04-inspo-similar.png` | "Similar" sheet open, one item expanded | PNG | "You already own" row first, then shop items, "Shop the whole look" |
| `04-inspo.mp4` | Tap 🔥 → picker → long-press quick react → tap Similar → expand two items → add one to cart | video | Picker animation, sheet slide-up |
| `04-inspo-dark.png` | Inspo feed, dark | PNG | Reactions readable in dark |
| `05-discover.png` | Discover results after photo search (or the "y2k" chip if the AI is busy) | PNG | Similar items / Goes with it, "From your closet" marks, full-width photos, no letterbox |
| `05-cart.png` | Bag with 2 stores | PNG | H&M + Uniqlo groups, subtotals, pencil on an item |
| `05-size-sheet.png` | Size sheet open from the pencil | PNG | Only in-stock sizes |
| `05-receipt.png` | After Check out | PNG | One `paid` purchase per store, totals |
| `05-checkout.mp4` | Discover camera → tap result → Home seeded ("Similar to: …") → Bag → change size → Check out → receipt | video | Seed chip, receipt reveal |
| `06-icon-tab.png` | iOS home screen with the Niche icon (`xcrun simctl io booted screenshot` after pressing Home) | PNG | Arch icon, "Niche" label |

Before recording: Home for u_adam has pre-rendered try-ons (150 cached); if a slide 2 shows "Dressing you…", wait 20 s and re-shoot. If it shows the outfit board, pick another post. Empty the cart first (`DELETE /cart/u_adam` or remove items in the app) so `05-*` starts clean.

## 3. Assets beyond screenshots

- **Icon:** `app/assets/icon/icon-1024.png` (full), `app/assets/icon/icon-fg.png` (adaptive foreground, transparent). Source `app/assets/icon/make_icon.py`.
- **Wordmark:** lowercase "niche" in Young Serif Regular, merlot on cream / cream on ink. Font file `app/assets/fonts/YoungSerif-Regular.ttf`; UI font `app/assets/fonts/Manrope-{Regular,Medium,SemiBold,Bold}.ttf`.
- **Palette:** the hexes at the top of this doc.
- **Clean-shot closet pieces** (`backend/data/uploads/`, u_adam, all passed the vision check):
  - white wired earbuds `da425590a95444dcb6f787f53a07964c-clean.png`
  - camel wool overcoat `362957c387d0403da660dff0930efa0b-clean.png`
  - black leather boots `b0acd547d46d47e0a5311144d5160f37-clean.png`
  - cream graphic t-shirt `d24bb90ca78548bbab90996b72658273-clean.png`
- **Try-on before/after pairs** (source in `backend/data/uploads/`, result in `backend/data/tryon/`):
  - `b54e7c9d8a9b448b8cfc3a7a9e4c2a5d.jpg` → `6e48654393f2831a003e62dd.png` (body photo)
  - `3894bcb0119a41469dcef5b2150bd047.jpg` → `e35b4b4af499e98944921623.png` (outfit photo)
  - Also the verified samples on the Desktop: `~/Desktop/Pics/dbg/src.jpg` → `full.png` (bookstore, white tee).
- **Existing screenshots:** `docs/sprint-4/` (light Home + two dark) and `~/Desktop/niche-*.png` from the polish pass.
- **Devpost copy:** `docs/devpost.md` (tagline: "Real clothes in your size that go with yours").

## 4. Brief for Claude Design

- **Format:** 1080×1920 vertical for the phone beats inside a 16:9 1920×1080 master (phone centred in a rounded frame, cream background, soft shadow); 110 s; 30 fps; export MP4 + the 6 title/diagram cards as PNG.
- **Style:** Pinterest-sleek. Cream `#FFFBF0` canvas, merlot `#5B1F33` type and accents, hook `#E9B9A8` for the one dot/highlight, ink `#1E1517` for the dark close. Lots of air, rounded 28 px corners, hairline dividers, no drop shadows heavier than the phone frame's.
- **Type:** Young Serif for the wordmark and every caption headline (lowercase, tight tracking); Manrope Medium for sub-captions and the build diagram.
- **Motion:** kinetic captions enter word-by-word from below (120 ms stagger, ease-out), hold, then dissolve; each app beat starts with the phone sliding up 24 px and settling; cut on the beat, no wipes. The arch icon's hook dot bounces once on the title and close cards (mirrors the app's "feed is ready" beat).
- **Phone footage:** use the `.mp4` recordings at native speed, trimmed to the action; speed up any load/wait to 2× rather than cutting it; overlay the PNGs where a rest state needs to hold.
- **Sound:** one soft click on each caption word, a single low tone on "Added ✓" and on the receipt. Music: warm, unhurried, no vocals.
- **Build diagram (beat 6):** six pills in a row with thin connectors: Flutter → FastAPI → {Apify, Claude, Gemini, Nessie}; label each with its job in 3 words.
- **Deliver:** `niche-demo.mp4`, plus `cards/*.png`, into `~/Desktop/Pics/demo/out/`.
