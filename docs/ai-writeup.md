# AI write-up (for Devpost: "How we built it", AI section)

Drafted by Adam's session for Nabil to paste and trim. The numbers are real, measured on our backend on Oct 23–24.

## Short version (paste-ready, ~120 words)

Every outfit decision in the app runs through a small, cheap AI pipeline with free rules-based fallbacks.
- **Claude Haiku** tags every product and closet photo (item, color, pattern, formality, style). It ranks the feed against *your* closet and writes the one-line reason on each card ("goes with your black cargos").
- **Gemini** renders the virtual try-on on your own photo.
- **Rules engines, no AI and free,** handle size advice (letters, waist/inseam, women's sizes, shoes), the 0–100 Fit Score, Style DNA, color matching and closet duplicate detection.
- When a friend's Fit Check outfit isn't in our catalog, we search H&M live through Apify.

Tagging our 418-product catalog cost about **$0.07**. A hard $5 budget cap, caching everywhere and automatic fallbacks keep the demo running even if a model fails.

## Longer version (pick what fits)

**What the AI does**
| Feature | Model | What it does |
| --- | --- | --- |
| Catalog + closet tagging | Claude Haiku (`claude-haiku-5-5`) | photo → label, category, color, pattern, formality 1–5, style tags (fixed 10-word vocabulary) |
| Feed ranking + reasons | Claude Haiku | ranks candidates against the user's closet, budget and swipe history; writes a ≤12-word reason naming the closet item each pick goes with |
| Fit Check tagging | Claude Haiku | outfit photo → each visible item, to pre-fill a post's tags |
| Virtual try-on | Gemini Flash Lite Image | your full-body photo + garment photos → a photorealistic photo of you wearing them, with body, face and pose kept |
| Text fallback | Gemini Flash | takes over automatically if Claude is unavailable |
| Shop this fit | rules + Apify | strict matching (same category and garment type) against the catalog, then a live H&M search through Apify if nothing matches |
| Size advice, Fit Score, Style DNA, color matching, closet duplicates, complete the look | rules (no AI) | free, instant and deterministic |

**Making it accurate**
- **Product-name hints:** retailer photos are often a model in a full outfit. Giving the tagger the product name ("Baggy Jeans") fixed it. Without the hint, 37 of 418 labels described the wrong garment (the model's shirt instead of the jeans); with it, **0**.
- **Strict Fit Check matching:** a hoodie never matches a tee, and a leather bomber never matches a denim jacket. The garment type must agree, and colors are normalized (31 canonical colors, so "ivory" = "off white").
- **Try-on prompt:** it names each garment's slot and ignores logos, size labels and the model in reference photos.

**Keeping it cheap and reliable**
- **Cheapest models:** Haiku by default, with extended thinking off for JSON tasks.
- **Caching:** tags per image + hint, feed ranking for 10 min, every try-on, and live searches. A repeat costs $0.
- **Swipes stay instant:** Claude's reasons go into a per-user reason bank (1 h). After a swipe the next feed is served from the bank right away while Claude re-ranks in the background with the new swipe history, so the feed still learns without a ~6 s wait.
- **Hard caps:** a $5 AI budget (endpoints switch to rules when it's hit) and 150 fresh try-ons.
- **Layered fallbacks:** Claude → Gemini → rules for text. AI try-on → an outfit-board collage. Whatever happens, the demo never shows an error screen.
- **Measured spend** for the whole build, including tagging 418 products and all testing: **about $0.50**.

**Photo onboarding (one step instead of a form):** drop in up to 8 photos (flat lays, mirror selfies, outfit shots) plus your height, and `POST /onboarding/photos` does the rest with the pieces above. Each photo is digitized into tagged closet items (one Haiku call per photo, duplicates across the batch and the existing closet dropped). Every photo is body-scanned and the full-body ones are averaged (more photos = a better estimate: `confidence` low / medium / high for 1 / 2 / 3+ full-body photos); the first full-body photo becomes the try-on photo, otherwise the height/weight formula fills the profile and says so. The same multi-photo averaging is available on the plain body-scan route. Your style is read off the garments by rules (top style tags by frequency, dominant colors, formality) into one sentence like "streetwear and minimalist; grey hoodie, light-wash jeans; mostly casual", with an optional single Haiku call for a nicer sentence that falls back to the rules. That sentence becomes the same `style_text` the feed ranks against, so the first Home screen is already personal. The scan also reads which store department the person's look points to (`presenting`), and fills `shop_for` only when the user never chose one. The reason bank is warmed in the background during the call, so Home opens instantly.

**Privacy:** the body photo is only used for your own try-ons. API keys never touch the repo, and the shared backend requires a private key on every request.

## Sponsor angle (if we enter an AI track)
- Claude does the reasoning work (understanding clothes and explaining why a piece fits your closet).
- Gemini does the generation work (try-on).
- They're cleanly separated, each with a measured cost and a fallback. One line for the demo: "every card tells you *why* it fits what you already own."

## AI Fit Creator
One tap builds complete outfits *for your body*. The pool is what you own plus in-stock pieces that pass your department, your learned price ranges and the sizing engine (only items we can actually order in your size, from the body scan's height/weight/waist/shoe size). Claude gets your build and measurements, style text, occasion, closet and ~40 sized candidates, and returns named fits with a reason that cites a real measurement ("slim build, 30.5 in waist: tapered denim keeps the line clean") and the closet piece each look is built around. Every id is validated against the pool and missing slots are filled by the outfit rules, so a fit is always wearable (top+bottom or dress, plus shoes). No AI? The same rules build one fit around each closet piece. Fits are cached an hour, can be rendered on your body photo on demand (`POST /fits/{id}/try-on`, lazy so the list is instant) and added to the cart in one tap at your size.
