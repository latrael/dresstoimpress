# Context for AI assistants working on dresstoimpress

Paste this as the first message in a new AI chat, then give it a task.

You're helping build **dresstoimpress** at Cal Hacks 13.0 (SF, Oct 23–25, 2026; code is due Sunday 9 AM). Team of three: Adam (AI pipeline), Nabil (data + commerce backend), Ryan (FlutterFlow iPhone app). Work at hackathon speed: small, runnable, tested code; simplest thing that works in a live demo.

**Product:** "Tinder for clothes." Swipe live products from Zara, H&M, ASOS, Uniqlo, Mango (scraped via Apify). Each card is paired with clothes the user already owns ("goes with your black cargos") and can show an AI try-on on the user. Buy from several stores in one checkout (Capital One Nessie mock payments). "Fit Check" feed: friends post outfits and you shop them. Competitor Alta Daily styles you but can't sell anything.

**Stack:** one Python FastAPI backend (Python 3.10+, Pydantic v2) at `backend/app/`. AI text tasks use Claude Haiku (fallback Gemini Flash); try-on uses a Gemini image model. Storage is a JSON-file store (or Firestore) with `store.get(collection, id)`, `store.list(collection, **where)`, `store.put(collection, id, doc)`. Tests are pytest in `backend/tests/`.

**Shared data contract (field names are fixed):**
- Product: `id, retailer (zara|hm|asos|uniqlo|mango), name, brand, category (top|bottom|outerwear|shoes|dress|accessory), price_usd, sale_price_usd, colors[], sizes[], in_stock, image_url, product_url, style_tags[]`
- ClosetItem: `id, user_id, image_url, category, color, pattern (solid|striped|plaid|graphic|floral|other), style_tags[], formality (1-5), source, label` (label = short name like "black cargo pants")
- User: `id, display_name, style_text, price_ranges {category: [min, max]}, body_photo_url, friends[]`
- Style tags vocabulary: y2k, streetwear, minimalist, preppy, athleisure, vintage, business, boho, grunge, classic

**AI endpoints that exist (Adam):** `POST /closet/tag`, `POST /closet/upload`, `POST /users/{id}/body-photo`, `POST /tryon`, `POST /pair`, `POST /ai/shop-fit`, `GET /ai/usage`.

**Rules for code you write:**
- Match the contract exactly; never invent new field names.
- Pure functions where possible; no network calls unless the task says so; no API keys in code.
- Deterministic (no randomness), never crash on odd input, full type hints.
- Reply with complete files only (no partial snippets), plus a pytest file with real assertions.
