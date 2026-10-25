# Sprint #4: the design overhaul (sleek, soft, alive) + Home as reels

Sun Oct 25, 2026, ~12:30 AM PT. Written by Nabil for the team. `staging` is at `4aa203b` (#64 merged, 672 backend tests pass). Sprint #3 is `docs/sprint-3.md`.

**What this sprint is:** the app works, but it looks and feels basic: system fonts, flat Material defaults, no motion, a black band at the top of the phone, and a Home feed that reads like a form. People who use Niche care about style and notice thoughtfulness in design. This sprint makes the app **feel** like a fashion app, without changing the colour scheme:
- modern type;
- softer, "bubblier" shapes;
- glass bars;
- motion on every tap and page change;
- a **reels-style Home** where one product at a time owns the screen.

**[decide]** = a call for the team before that piece starts. Everything else is decided.

**Reference files (in this repo):**

| File | What it is |
| --- | --- |
| `docs/sprint-4/current-home.png` | Today's Home on Nabil's iPhone 16: the black band at the top, the system font, the letterboxed photo, buttons hidden behind the nav bar |
| `docs/sprint-4/logo-board.png` | **The logo board** (arch mark + "niche" wordmark). **Nabil: save the logo image here; it isn't in the repo yet.** |
| `docs/sprint-4/font-banks.html` | **Five font pairings, rendered** on a Niche product card in our colours. Open it in a browser and pick one (§2). |

---

## 0. Ground rules for the whole sprint

1. **The colour scheme stays.** Cream `#FFFBF0` (background), merlot `#5B1F33` (logo), wine `#722F42` (buttons/seed), hook `#E9B9A8` (the logo's dot), blush `#F0E5E5` (chips), stone `#EDEAE4` (photo backgrounds). They move into named tokens (§3.1). No new hues; only opacity variants of these.
2. **The outfits are the focus.** Minimal chrome, generous whitespace *around* photos (not empty screens), and no text that repeats what the photo already says.
3. **Everything you tap answers back:** a press state, a short animation, and a light haptic on selection.
4. **It must look right on both phones we demo on:** Nabil's **iPhone 16** (iOS 27, Dynamic Island) and **the Pixel 9 Pro** (Android, gesture navigation). Screenshot both at the end of each section (§11).
5. **Content stays the same** on Discover, Inspo and the top-bar screens (Liked, Cart, Closet, Profile). They get the new look, not new features. **Home** and **onboarding** are the only screens that change in structure.

---

## 1. The top of the screen doesn't reach the edges (iPhone 16 + Pixel 9 Pro)

**What's wrong:**
- On both phones there's a solid **black band** behind the status bar (time/battery), above the app's cream header. See `current-home.png`.
- Below it, the header icons look cramped.

**Why:** `app/lib/main.dart:183`. `MaterialApp.builder` wraps the whole app in `SafeArea(bottom: false)`. Nothing paints *above* the safe area, so the area behind the status bar / Dynamic Island shows the window's default black. The header is also a hard-coded `SizedBox(height: 56)` (`main.dart:194-195`) and the page below is pushed down by a fixed `top: 56` (`main.dart:186-187`).
- Android has the same issue. Recent Android versions draw apps **edge-to-edge** (behind the status bar and the gesture bar) by default, so the black band shows there too.

**Change (Ryan):**

| # | Change | Detail |
| --- | --- | --- |
| 1.1 | **Paint behind the system bars** | Put the cream background (`ColoredBox`) *outside* the `SafeArea`, or better, drop the global `SafeArea` and let each layer use `MediaQuery.paddingOf(context)`. |
| 1.2 | **Header extends under the status bar** | The header's height = `MediaQuery.paddingOf(context).top` + the bar height (≈ 52). Its background is the frosted glass from §4.1, so it reaches the very top edge and content scrolls under it. Replace the fixed `top: 56` offsets with that computed height. |
| 1.3 | **Status-bar icons readable** | `AnnotatedRegion<SystemUiOverlayStyle>` with a transparent status bar and **dark** icons on cream (light icons only over a dark photo, if a screen goes full-bleed). |
| 1.4 | **Android edge-to-edge** | Transparent status and navigation bars (`SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge)` + transparent `systemNavigationBarColor`). The floating nav bar (§4.2) sits above the gesture handle using `MediaQuery.paddingOf(context).bottom`. |
| 1.5 | **Content isn't hidden by the nav bar** | In `current-home.png` the "Try it on / Complete the look" buttons sit *under* the nav bar. Every scrolling page gets bottom padding = nav bar height + bottom inset, so its last item can scroll clear. |

**Done when:**
- On both phones, cream reaches the top edge with no black band, and the time/battery are dark and readable.
- Nothing important sits under the Dynamic Island, the camera cut-out or the nav bar.

---

## 2. Typography: from system default to a type system

**What's wrong:** the app uses the platform default (San Francisco / Roboto) at Material's default sizes, everywhere. "Niche" in the header is just bold system text (`main.dart:197-201`), nothing like the logo's soft lowercase serif.

### 2.1 Font banks: pick one **[decide]**
Open **`docs/sprint-4/font-banks.html`**: each bank is shown on the same product card, header and chips. All are free (Google Fonts, OFL licence).

| Bank | Display (wordmark, titles, product names) | UI (everything else) | Feel |
| --- | --- | --- | --- |
| **A. Soft Editorial (recommended)** | **Fraunces** (variable; `SOFT` 100 rounds the serifs, `opsz` for size) | **Plus Jakarta Sans** | Closest to the logo's lowercase serif. Warm, modern editorial; the open UI sans gives the "bubblier" feel. |
| B. Gallery | **Instrument Serif** (+ italic for accents) | **Inter Tight** | Fashion-magazine minimal: the most "let the photos talk". |
| C. Bubbly | **Young Serif** | **Manrope** | Chunky, friendly, the most playful. |
| D. Quiet Luxury | **Newsreader** | **Geist** | Refined and calm; the least bubbly. |
| E. Street Gallery | **Bricolage Grotesque** (no serif) | **DM Sans** | The most eccentric, but it moves away from the serif logo. |

**Recommendation: Bank A.** Fraunces with `SOFT` 100 at weight ~560 is the nearest free match to the wordmark on the logo board (lowercase, soft bracketed serifs, moderate contrast), and Plus Jakarta Sans reads cleanly at small sizes.

### 2.2 Type scale (whichever bank wins; values for Bank A)
Map these onto Flutter's `TextTheme` in one place, so no screen sets raw font sizes.

| Role (`TextTheme`) | Font | Size / line height | Weight | Used for |
| --- | --- | --- | --- | --- |
| Wordmark (custom) | Display | 28 / 28 | 560, tracking −1% | "niche" in the header, lowercase, merlot |
| `displaySmall` | Display | 36 / 40 | 600 | Onboarding hero lines ("Let's make niche yours") |
| `headlineSmall` | Display | 26 / 30 | 600 | Product name on a Home post, page titles |
| `titleMedium` | UI | 17 / 22 | 600 | Section titles, sheet titles |
| `bodyLarge` | UI | 16 / 24 | 400 | Descriptions, captions |
| `bodyMedium` | UI | 14 / 20 | 400 | Secondary text |
| `labelLarge` | UI | 15 / 20 | 600 | Buttons |
| `labelSmall` (caps) | UI | 11 / 14 | 600, tracking +12%, UPPERCASE | Store names ("BRANDY MELVILLE"), tiny labels |
| Price (custom) | UI | 17 / 20 | 600, `FontFeature.tabularFigures()` | Prices, so digits don't jump |

### 2.3 How to ship the fonts
- **Bundle the `.ttf` files** in `app/assets/fonts/` and register them in `pubspec.yaml` under `flutter: fonts:`. Include each font's `OFL.txt`. Don't fetch fonts at runtime (no flash of the system font, works offline, nothing extra on the network during the demo).
- Keep the variable fonts (Fraunces, Plus Jakarta Sans) and set axes with `FontVariation('SOFT', 100)`, `FontVariation('opsz', …)`, `FontVariation('wght', …)`, or bundle static weights if variable axes misbehave on a platform.
- The wordmark is **text in the display font**, not an image, so it stays crisp at any size. Use the arch-mark image only for the app icon and the welcome animation (§5.1).

---

## 3. Design system (the base everything else uses)

Put this in one file (e.g. `app/lib/features/shared/niche_theme.dart`) and use it everywhere, so the look is consistent and easy to tune.

### 3.1 Tokens
| Token | Value |
| --- | --- |
| Colours | `cream #FFFBF0`, `paper #FBF3EE`, `merlot #5B1F33`, `wine #722F42`, `hook #E9B9A8`, `blush #F0E5E5`, `stone #EDEAE4`, `ink #1E1517` (text), `muted #7A6A6E` (secondary text). Glass = `cream` at 70% opacity. Hairlines = `merlot` at 12–14% opacity. |
| Radius ("bubblier") | `xs 10` · `sm 14` · `md 20` · `lg 28` (photos, cards, sheets) · `pill 999` (buttons, chips, nav bar) |
| Spacing | 4-pt grid: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48. Screen side gutter **16**. |
| Elevation | Almost none. Use a soft shadow only on floating things (nav bar, add-to-cart button, sheets): `0 8 24` at merlot 10–12%. No Material grey shadows. |
| Icons | **One outline icon family** everywhere, with a ~1.5 px stroke (e.g. Phosphor *Regular* or Lucide; pin a version). Today's mix of Material `_outlined` icons is part of why it looks stock. 22–24 px glyphs in 40–44 px tap areas. |
| Buttons | Primary: a wine pill, 52 high, `labelLarge`, white text. Secondary: an outline pill with a 1 px merlot @ 25% border. Text buttons stay rare. |
| Chips / tags | Pill, 36 high, 14 px text, 1 px hairline border. Selected: merlot fill + paper text + a small check that slides in. |
| Photos | Radius `lg 28` in cards; `BoxFit.cover` inside a frame at the photo's natural ratio (§7). **Never letterbox** (no grey side bars like `current-home.png`). |

### 3.2 Motion (applies to every section)
| Interaction | Animation | Duration / curve |
| --- | --- | --- |
| Press on anything tappable | Scale to 0.96, back on release | 120 ms down / 180 ms spring back |
| Chip / tag select | Fill colour cross-fades, the check slides in from the left, text colour flips + `HapticFeedback.selectionClick()` | 180 ms, `easeOutCubic` |
| Page forward (onboarding step, push to a screen) | The new page slides in from the right ~30 px and fades in; the old one slides left ~30 px and fades out (shared-axis X) | 320 ms, `Curves.easeInOutCubicEmphasized` |
| Page back | The same in reverse (the new page comes from the left) | 280 ms |
| Tab change (Home ↔ Discover ↔ Inspo) | Follows the finger when swiped (§4.3); when tapped in the nav bar, the same horizontal slide | 300 ms |
| Sheets ("see more", comments, size) | Rise with a slight overshoot; the background dims to 30% | 300 ms |
| Add to cart | The button morphs to "Added ✓", the bag icon in the header bounces (scale 1 → 1.2 → 1) and its badge count rolls up, plus `HapticFeedback.mediumImpact()` | 220 ms + 300 ms |
| Images loading | A soft shimmer on `stone`, then a 250 ms cross-fade, never a pop-in | — |

- **Reduced motion:** when `MediaQuery.disableAnimations` is on, slides become plain cross-fades.
- **Package:** `animations` (Flutter team: `SharedAxisTransition`, `PageTransitionSwitcher`) covers most of this; pin an exact version.

---

## 4. App shell: header, bottom bar, swiping between tabs (Ryan)

### 4.1 Header (the top bar with the icons)
**Today:** "Niche" in bold system text plus **four** default Material `IconButton`s (Liked, Cart, Closet, User) at 48 px each. It feels crowded and stock (`main.dart:189-236`).

**New:**
- **Left: the wordmark "niche"** in the display font (§2.2), lowercase, merlot, like the logo. Optional: the small arch mark (18 px) before it.
- **Right:** **Liked**, **Bag** (with the count badge) and **Closet** as 22 px outline icons from the new icon family, 4–8 px apart. **Profile becomes a 30 px avatar circle** (the user's initial on blush; their photo later) at the far right instead of a fourth generic icon. Same destinations as today.
- **Background:** frosted glass, i.e. `BackdropFilter` (blur σ ≈ 20) + cream at ~70% opacity + a hairline at the bottom that only appears once content has scrolled under it. It extends under the status bar (§1.2).
- **Vertical alignment:** icon centres line up with the wordmark's x-height, not its baseline, so they "fit" the bar.

### 4.2 Bottom bar (Home · Discover · Inspo)
**Today:** an opaque Material `NavigationBar` inside a pink pill with a heavy shadow (`main.dart:642-667`). It covers content.

**New:**
- **A floating glass pill**, more transparent: `BackdropFilter` blur σ ≈ 24, cream at **55–65% opacity**, a 0.5 px white @ 40% inner border, the soft merlot shadow from §3.1. Height ~60, side margins 24, sitting `bottomInset + 10` above the screen bottom (the Android gesture handle stays visible below it).
- **Selected indicator:** a merlot pill behind the active icon that **slides** between tabs and tracks the swipe position live (it's driven by the shell `PageController`'s page value, not just the index).
- **Labels:** show only the active tab's label next to its icon (an icon + label pill); inactive tabs are icon-only. This reads sleeker and saves width.
- **[decide]** Glass in cream (above) or a darker merlot glass at ~80% with cream icons. Cream is the default; try both on the reels Home, where the bar sits over photos.

### 4.3 Swiping left/right between tabs
- Put **Home, Discover and Inspo in one horizontal `PageView`** (the "shell"). Swiping left/right anywhere that isn't a horizontally scrollable thing moves between tabs, and the nav pill follows.
- **Gesture rule (important on Home):** a horizontal drag that **starts inside a photo carousel** flips that carousel's photos and never changes the tab, even at the carousel's last photo (it clamps; it does not hand the drag to the shell). A drag that **starts outside** the carousel box (the caption area, the margins) changes the tab. In Flutter this happens naturally if the carousel is its own horizontal `PageView` with clamping physics: the gesture arena gives the drag to the innermost scrollable under the finger.
- **Android back gesture:** a swipe from the very left/right *edge* on the Pixel is the system "back" gesture. Don't fight it. Tab swipes work from anywhere else, and nothing important needs an edge swipe (`MediaQuery.systemGestureInsetsOf(context)` gives the edge widths).
- Discover keeps its own content inside its page; its search field and chips mustn't steal horizontal drags unless they really scroll horizontally.

---

## 5. Onboarding (Ryan)

### 5.1 Page 1, "Let's make Niche yours": currently bland and mostly empty
**Today** (`app/lib/features/profile/onboarding_screen.dart:479-485`): a `headlineMedium` title and one sentence, then a big empty space down to the buttons.

**New: a welcome screen that fills the phone and shows what Niche is.**
- **Top third: brand moment.**
  - **The arch mark draws itself**: the stroke animates from the left leg, over the arch, down the right leg (~700 ms), then the hook dot drops in with a little bounce (~250 ms).
  - Underneath, the **"niche" wordmark** fades up.
  - The geometry is in `app/assets/icon/make_icon.py` (legs, arch radius, dot position), so this can be a `CustomPainter` path with a `PathMetric`-driven stroke animation.
- **Middle: the line.** "Let's make niche yours." in `displaySmall` (display font), and below it one short muted line: "Your style, your size, the clothes you already own."
- **Bottom half: a moving mosaic of real outfits.**
  - Three columns of real catalog photos (rounded `md 20`, natural ratio, `BoxFit.cover`) drift slowly upward at slightly different speeds, like a living lookbook, and fade into cream at the top and bottom edges.
  - Use ~12 photos from the user's first `/feed` page (or `/search/styles` trending), and cache them so they don't load during the animation.
  - With reduced motion: a static mosaic.
- **Bottom: one pill CTA, "Let's go"**, fixed in the thumb zone over a cream gradient. No other buttons on this page.
- **Progress:** a thin bar of step dots at the very top (below the status bar) that fills as you go.

### 5.2 Every step after that
- **Transitions:** forward = shared-axis slide to the left, back = slide to the right (§3.2). The title, then the text, then the chips each fade up with a 40 ms stagger. **The progress bar animates** between steps.
- **Layout:**
  - **Title:** each step's question is the title, in the display font ("What's your style?", "Where do you shop?", "Men's, women's or both?"), instead of a plain `Text`.
  - **Thumb zone:** controls sit in the lower two-thirds.
  - **Buttons:** "Next" is the fixed primary pill at the bottom; "Skip" is a quiet text button at the top-right; "Back" is a chevron at the top-left.
- **Chips** (styles, stores, men/women/both, sizes) use the §3.1 chip with the §3.2 select animation and haptic. Store chips can show each store's name in its own small caps.
- **Body scan and measurement steps:** the same type and spacing; keep the content as it is. The photo picker becomes a big rounded drop-zone card with a dashed hairline border.
- **The last step ("Your feed is ready"):** a short celebratory beat (the arch mark again, the dot bounces), then the transition straight into the new Home.
- **Order (unchanged):** 0 welcome → 1 style → 7 men/women → 2 stores → 3 body scan → 4 measurements → 5 budgets → 6 done.

---

## 6. Home becomes reels (Ryan for the UI, Nabil + Adam for the data in §10)

**Today:** `QuickBrowse` (`app/lib/features/feed/quick_browse.dart`) shows a long, form-like page per product: a letterboxed photo, store, name, a description with "More", a "Matches your style" box, colour, a size line, and Try it on / Complete the look buttons hidden behind the nav bar (`current-home.png`). It feels formal, and nothing has emphasis.

**New: one product per screen, like Reels or TikTok.**

```
┌──────────────────────────────┐  ← cream reaches the top (§1)
│ niche              ♡  👜 ⌂ (N)│  ← glass header (§4.1)
│ ┌──────────────────────────┐ │
│ │ ▬ ▭ ▭                    │ │  ← 3-slide indicator
│ │                          │ │
│ │   SLIDE 1  the item      │ │  ← photo carousel box (swipe ← → flips slides)
│ │   SLIDE 2  on you        │ │     rounded 28, natural ratio up to 4:5
│ │   SLIDE 3  your closet   │ │
│ │                          │ │
│ └──────────────────────────┘ │
│ BRANDY MELVILLE              │  ← caption area (swipe ← → here = change tab)
│ Anastasia Sweatpants   $35   │
│ see more                     │
│ ┌──────────────────────────┐ │
│ │       Add to cart        │ │  ← the ONLY action button
│ └──────────────────────────┘ │
│   ╭──────────────────────╮   │
│   │ ⌂ Home   ◎    ⚇      │   │  ← glass nav pill (§4.2)
└──────────────────────────────┘
        swipe ↑ = next post, swipe ↓ = previous
```

### 6.1 Scrolling
- **A vertical `PageView`**: each post fills the height between the header and the nav bar and snaps, one at a time. A short flick moves exactly one post.
- **Pre-load:** keep the next 2 posts' slide-1 images in memory (`precacheImage`), and ask the backend to start try-ons for the next 3 posts (§10.2).
- **Keep:** pull-to-refresh at the top of the feed, and the "Similar to: …" seed chip (it floats over the first post as a glass chip).

### 6.2 The photo carousel (three slides, in this order)
1. **Slide 1, the item itself:** the catalog photo of the product on its own (flat lay / product shot) when the store has one, else its first photo. Uses the card's new `hero_image_url` (§10.1).
2. **Slide 2, "on you":** the try-on of this item **on the user**, styled with pieces from their own closet. It's already loaded by the time they swipe to it (§10.2). It's labelled with a small glass tag, "on you".
   - **While it renders:** a shimmer with "Dressing you…".
   - **When ready:** a 250 ms cross-fade.
   - **No photo of the user yet:** a soft card, "Add a photo of you to see this on you", that opens the body-photo step.
   - **Try-on budget is out:** the free outfit-board collage (`mode: "collage"`), labelled "outfit board".
3. **Slide 3, "goes with":** a **2×2 grid of pieces from the user's own closet** that go with this item, one piece per square (§10.1, `closet_picks`).
   - **Accessories count** (bags, belts, jewellery, hats), not just top/bottom/shoes.
   - **Each square:** the closet photo (the user's own, never a catalog shot; sprint-3 decision), rounded `sm 14`, with its label in `labelSmall` on a glass strip.
   - **With fewer than 4 pieces:** the empty squares become "+ add from your closet" tiles that open Closet.
   - **Tapping a square** opens that closet piece.

- **Indicator:** three short bars at the top of the carousel (like Stories); the active one is white.
- **Shape:** the carousel box is rounded `lg 28` with a 12–16 px side gutter, so there's always visible "outside" to swipe on.
- **Height:** the item photo's natural ratio, clamped between 4:5 and 3:4, and the same for all three slides of a post, so the box doesn't jump between slides.

### 6.3 What's removed from the post
Remove these from the Home post (`quick_browse.dart`):
- the "**Matches your style**" box;
- the **Color** line;
- the **size line / "Add your measurements…"** line;
- the **Try it on** and **Complete the look** buttons.

Try-on is now slide 2 and the closet pairing is slide 3, so the buttons aren't needed. **[decide]** The heart on the photo: the brief says Add to cart is the only action. Proposal: remove the heart button and add **double-tap on the photo = like** (a heart pops in the centre, haptic), so Liked still fills without a visible button.

### 6.4 "See more" (like opening a reels caption)
- **Collapsed:** store (caps), name (display font), price (tabular figures), and "see more".
- **Tapping "see more":**
  - the caption expands upward over a soft cream-to-transparent scrim (`AnimatedSize`, 250 ms);
  - it shows the **description**, **colour** and **size** (the size Niche picked for them, e.g. "Your size: M", with a small "change" link that opens the size sheet);
  - tapping anywhere else or "less" collapses it.

### 6.5 Add to cart
- **The only button:** a full-width wine pill.
- **When a size is known:** it adds at that size immediately, with the §3.2 morph to "Added ✓", the bag bounce and a haptic.
- **When no size is known:** it opens the size sheet first, then adds.
- Uses the existing `store.add`.

---

## 7. Discover: photos fit the phone's width, like Inspo (Ryan)

**Today:**
- **Results grid:** 2 columns at a fixed `childAspectRatio: .65` (`app/lib/features/discover/discover_screen.dart:21-27`), so photos are squeezed into one shape.
- **Opened product:** it shows the letterboxed `BoxFit.contain` page from `quick_browse.dart:397` (the grey side bars in `current-home.png`).

**New:**
- **Results** use the same natural-ratio frame as Inspo (`NaturalPhotoFrame`, `app/lib/features/shared/natural_photo_frame.dart`, already capped at 9:16 and centre-cropped): photos fill the width with `BoxFit.cover` and keep their own shape.
  - **[decide]** A single full-width column (most immersive), or a 2-column **masonry** grid where every tile keeps its natural ratio (more browseable). Ryan's call; masonry is suggested for search results, full-width for "Goes with it".
- **Opening a product** from Discover shows **the same reels post as Home** (§6): full width, no letterbox, the same carousel and Add to cart. One component, used in both places.
- **Restyle** (content unchanged): the search field becomes a glass pill with the new icons, the style chips use the new chip, and section titles use `titleMedium`. The camera button becomes a round glass button.

---

## 8. Inspo and the other screens: the new look, same content (Ryan)

- **Inspo** (`social_feed.dart`, `comments_sheet.dart`):
  - the new type scale, tokens and icons;
  - photos keep the natural-ratio frame;
  - like = heart pop + haptic;
  - comment sheet = the new sheet rise;
  - tag chips on photos = glass pills with the press animation;
  - author names in `titleMedium`.
- **Liked, Cart, Closet, Profile, Connection:** the new type, tokens and icons, and the shared-axis push/pop transition. Cart line items get rounded photos and tabular prices. Nothing else changes.

---

## 9. The app icon and name (already done: Adam #61)
- The icon (arch + hook dot) and the name "Niche" are already in the app.
- This sprint only matches the **in-app wordmark** to it (§2.2) and reuses the arch for the welcome animation (§5.1).

---

## 10. Data the new Home needs (Nabil: `/feed` + routes; Adam: AI + core)

### 10.1 New fields on every `/feed` card (Nabil, with Adam's helpers)
| Field | Shape | Meaning | Owner |
| --- | --- | --- | --- |
| `hero_image_url` | string | Slide 1: the item on its own (product shot / flat lay) when the store has one, else `image_url`. | **Nabil** (data, see below) |
| `closet_picks` | `[{id, label, category, image_url}]`, 0–4 | Slide 3: the user's own closet pieces that go with this item, **one per square, different categories**, accessories allowed. The order follows the item: for a bottom → top, shoes, outer/layer, accessory; for a top → bottom, shoes, outer, accessory; for shoes → top, bottom, outer, accessory; for a dress → shoes, outer, bag, accessory. Built with rules (colour/style/formality from the closet tags, the same rubric as Fit Score v2), so it's **free and instant**. `[]` when the closet is empty. | **Adam** (`ai.service.closet_picks(user_id, product, k=4)`), Nabil puts it on the card |
| `tryon` | `{status: "ready" \| "pending" \| "none" \| "needs_photo" \| "unavailable", image_url?, mode?: "ai" \| "collage"}` | Slide 2. Read from the try-on cache: `ready` if this (user, product, closet picks) try-on exists, `pending` while rendering, `none` before prefetch, `needs_photo` if the user has no photo of themselves, `unavailable` if the AI is off or the budget is spent (then `image_url` = the collage). | **Adam** (cache lookup + status), Nabil puts it on the card |

**The hero-image problem (Nabil):** our catalog data doesn't say which photo shows the item on its own.
- **Uniqlo** (798) is labelled `product` (single product shots).
- **The other seven stores (2,390 products) are all labelled `retailer_model`**, even though many galleries contain a flat lay or product-only shot (Brandy Melville has only one photo each, on a model; see the screenshot).
- **Plan:**
  1. Free heuristics from the raw scrapes in `backend/seed/raw/` (H&M asset types / URL patterns; Shopify image position, alt text and dimensions; a mostly-white background check with Pillow).
  2. Then a cheap Claude Haiku image check only for products where the heuristics aren't sure (the first ≤ 4 photos).
  3. **Estimate the cost before running it and ask the team if it's over ~$2** (the `AI_BUDGET_USD` cap is $5 on the shared server).
- **Result:** each `images[]` entry gets a correct `kind`, and `hero_image_url` = the first `kind: "product"` image, else `image_url`. It goes into the snapshot, so it survives rebuilds.

### 10.2 Pre-loaded try-ons (Adam builds the renderer; Nabil the routes)
Slide 2 has to be **ready before the user swipes to it**, but a try-on takes several seconds and costs a Gemini image.
- **`POST /feed/{user_id}/tryons`** `{product_ids: [...]}` (≤ 5): for each product, start rendering in the background **if it isn't cached or already rendering**, with the product + its `closet_picks` (the wearable ones; Adam decides whether accessories go into the render). It returns immediately with `{product_id: tryon}` (the §10.1 shape).
- **`GET /feed/{user_id}/tryons?ids=a,b,c`**: the current status, for polling (every ~3 s while a visible post is `pending`; stop once it's `ready`).
- **App behaviour:** on feed load, prefetch posts 1–3; each time the user lands on post *n*, prefetch *n+1…n+3*.
- **Renderer (Adam):** `service.prefetch_tryons(user_id, items)`.
  - A small worker pool (2 at a time), with in-flight de-duplication.
  - It reuses `service.try_on` and its cache key (the version + user + products + closet pieces + source photo), so a prefetched result is exactly what slide 2 shows.
  - It uses the user's best own photo (`tryon_source.pick_source_photo`, try-on v5).
- **Budget [decide]:**
  - `MAX_TRYONS` is **150 for the whole server** today (`backend/app/ai/llm.py:55`). Pre-loading for every post would use that up fast (4 users × 30 posts = 120).
  - Proposal: raise the cap after checking the Gemini bill, and limit prefetch to **~20 per user per day** (the first posts of each session plus wherever they actually scroll).
  - After that, `tryon.status = "unavailable"` with the free collage.
- **Core (Adam, `app/lib/core`):**
  - Parse `heroImageUrl`, `closetPicks` and `tryOn` on feed cards.
  - Add `Api.prefetchTryOns(userId, productIds)` and `Api.tryOnStatus(userId, ids)`.
  - Add mock data for these, so Ryan can build Home before the backend lands.

### 10.3 Nothing else changes in the API
Cart, checkout, Discover search, Inspo and Closet routes stay as they are. The old `POST /tryon` and `POST /complete-look` stay too (other screens and older builds use them).

---

## 11. Done = it looks right on both phones
For every section, Ryan posts **before/after screenshots from the iPhone 16 and the Pixel 9 Pro** in `RYAN_TO_NABIL.md` (or the PR).
- [ ] No black band at the top. Cream reaches the edges and the status-bar icons are readable (§1).
- [ ] The chosen font bank is used everywhere, with no system font left (search the code for raw `TextStyle(fontSize:` and `fontWeight` outside the theme) (§2).
- [ ] Header: lowercase serif "niche", 3 icons + an avatar, glass, aligned (§4.1).
- [ ] Nav pill: glass, more transparent, a sliding indicator, nothing hidden behind it (§4.2, §1.5).
- [ ] Swiping left/right switches tabs everywhere *except* inside a photo carousel; it doesn't fight Android's edge-back gesture (§4.3).
- [ ] The welcome page fills the screen (arch animation, mosaic, one CTA); steps slide forward/back; chips animate with haptics (§5).
- [ ] Home: one post per screen, a 3-slide carousel (item → on you → your closet 2×2), "see more", Add to cart only (§6).
- [ ] Slide 2 is already loaded on posts 2+ in normal scrolling (§10.2).
- [ ] Discover photos fill the width with no letterbox; an opened product = the Home post (§7).
- [ ] Inspo and the other screens use the new look with the same content (§8).
- [ ] Reduced motion → cross-fades only.

---

## 12. Who does what

| Owner | Items | Depends on |
| --- | --- | --- |
| **Ryan** (all app screens + design) | **First:** §1 edge-to-edge, §3 tokens + motion, §2.3 bundle the chosen fonts. **Then:** §4 shell (header, glass nav, tab swiping), §6 Home reels (start on Adam's mock data), §5 onboarding, §7 Discover, §8 Inspo + other screens. Screenshots on both phones (§11). | The font bank decision (§2.1); Adam's core mocks for §6. |
| **Adam** (AI, hosting, core) | §10.1 `closet_picks` (rules, free) and the `tryon` status lookup; §10.2 the prefetch renderer + budget; core: parse the new card fields, `prefetchTryOns`, `tryOnStatus`, mocks for Ryan **early**; restart the shared server after each backend merge; the try-on budget decision with numbers. | Nabil's routes (§10.2) for the end-to-end path. |
| **Nabil** (commerce backend, data) | §10.1 `hero_image_url`: classify catalog photos (heuristics, then a capped AI pass, budget check first) and put it into the snapshot; add `hero_image_url`, `closet_picks` and `tryon` to `/feed` cards; §10.2 the two `/feed/{user}/tryons` routes + tests; keep `/feed` fast with the new fields (time it); test on the shared server; update `docs/devpost.md` and `docs/demo-script.md` with new screenshots once Ryan's screens land; the Pixel 9 Pro check with the teammate who owns it. | Adam's `closet_picks` + `prefetch_tryons`. |
| **Everyone** | Pick the font bank (§2.1) and settle the other **[decide]** items below **before** Ryan starts §2/§4/§6. | — |

**Suggested order:**
1. **Decisions** (10 min): font bank, heart vs double-tap, nav glass colour, Discover layout, try-on budget.
2. **Ryan:** §1 + §3 + §2.3. **Adam:** core mocks. **Nabil:** hero-image heuristics.
3. **Ryan:** §4 shell + §6 Home on mocks. **Adam:** `closet_picks` + prefetch. **Nabil:** the `/feed` fields + routes.
4. **Ryan:** §5 onboarding, §7 Discover, §8 the rest. **Everyone:** wire up against the real backend and screenshot both phones.

---

## 13. Open decisions
1. **Font bank:** A (recommended), B, C, D or E? See `docs/sprint-4/font-banks.html`.
2. **The like heart on Home posts:** remove it and use double-tap-to-like (proposed), or keep a small heart?
3. **Nav bar glass:** cream (default) or merlot?
4. **Discover results:** a single full-width column, or a natural-ratio masonry in 2 columns?
5. **The try-on budget:** the new `MAX_TRYONS` and the per-user daily prefetch cap (proposed ~20). Adam to bring the current Gemini cost per image.
6. **Accessories in the try-on render** (slide 2) or only in the 2×2 grid (slide 3)? Adam's call based on the render quality.

---

## 14. Files to attach
- `docs/sprint-4/current-home.png`: **added** (Nabil's iPhone 16 screenshot).
- `docs/sprint-4/font-banks.html`: **added** (open it in any browser).
- `docs/sprint-4/logo-board.png`: **Nabil to add.** The logo-board screenshot (arch mark + "niche" wordmark) is the reference for the wordmark font and the welcome animation.
- **Optional:** a screen recording of a reels app's swipe feel, if anyone has a reference they like, at `docs/sprint-4/reference-*.mp4|png`.
