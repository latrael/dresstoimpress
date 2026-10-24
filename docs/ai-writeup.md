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

**Privacy:** the body photo is only used for your own try-ons. API keys never touch the repo, and the shared backend requires a private key on every request.

## Sponsor angle (if we enter an AI track)
- Claude does the reasoning work (understanding clothes and explaining why a piece fits your closet).
- Gemini does the generation work (try-on).
- They're cleanly separated, each with a measured cost and a fallback. One line for the demo: "every card tells you *why* it fits what you already own."
