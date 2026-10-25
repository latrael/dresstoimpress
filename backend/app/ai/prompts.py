"""Prompts for the AI pipeline. Log any changes in the Notion prompt log.

Every structured prompt follows one shape: ROLE line, numbered HARD RULES, closed vocabularies
(the constants below: never invent new values), then the exact OUTPUT schema. `SCHEMAS` holds a
JSON-schema per prompt, keyed by the prompt's first line; `llm.ai_json` finds it with `schema_for`
and rejects any reply that doesn't match (so the model is retried instead of us parsing junk).
Gemini text calls run at temperature 0 with a fixed seed (llm.SEED); Claude runs at its default sampling (the only
setting Haiku 5.5 accepts), and every reply is checked against the prompt's JSON schema.
"""

# ---- closed vocabularies (mirror app.models enums; keep in sync) ----
STYLES = ["y2k", "streetwear", "minimalist", "preppy", "athleisure", "vintage", "business", "boho", "grunge", "classic"]
CATEGORIES = ["top", "bottom", "outerwear", "shoes", "dress", "accessory"]
PATTERNS = ["solid", "striped", "plaid", "graphic", "floral", "other"]
BUILDS = ["slim", "average", "athletic", "curvy", "broad"]
DEPARTMENTS = ["men", "women", "unisex"]
SLOTS = ["top", "bottom", "shoes", "outerwear", "dress", "accessory"]
_S = "|".join(STYLES)
_C = "|".join(CATEGORIES)
_P = "|".join(PATTERNS)

_NO_LOOKS = "Never comment on the person's body, weight, health or attractiveness."
_ONLY_JSON = "Output exactly one JSON value matching OUTPUT, no prose, no markdown fences."

_ITEM_FIELDS = f"""  "label": string, 2-4 plain words (e.g. "black cargo pants"),
  "category": "{_C}",
  "color": one plain colour word or two joined by a space (e.g. "navy", "light blue"),
  "pattern": "{_P}",
  "style_tags": up to {{n}} of [{_S}],
  "brand": string or null — ONLY a brand whose logo, label or printed text is readable in the image; never guess"""

TAGGER = f"""ROLE: fashion cataloguer. The image shows ONE clothing item (possibly on a person).
HARD RULES:
1. Describe only the clothing item; ignore the person, background and other garments.
2. Use only the listed vocabulary values; lowercase.
3. {_ONLY_JSON}
4. If the image is not clothing, output {{"error": "not_clothing"}}.
OUTPUT:
{{{_ITEM_FIELDS.format(n=5)},
  "formality": integer 1-5 (1 loungewear, 3 everyday, 5 black tie),
  "department": "men"|"women"|"unisex"|null (which store section sells it; null when unclear)}}
EXAMPLE: {{"label":"black cargo pants","category":"bottom","color":"black","pattern":"solid","style_tags":["streetwear"],"formality":2,"brand":null,"department":"unisex"}}"""
TAGGER_VERSION = "v3"  # bump when TAGGER changes so cached tags are redone (v3: brand; structure rewrite kept at v3 to avoid re-tagging closets)

# Appended to TAGGER for retailer photos, where a model often wears a whole outfit.
TAGGER_HINT = """
5. This photo is for the product "{hint}". If a person wears several things, describe only that product."""

TRYON = (
    "Dress the person in the first image in the garments shown in the other images. "
    "Keep their face, skin tone, hair, body shape and proportions exactly the same. "
    "Change only the clothing. Full body, standing, plain light background, natural lighting."
)

TRYON_VERSION = "v8"  # bump to invalidate cached try-ons when the prompt changes (v8: true-to-size fit, reference-photo guard)

TRYON_RETRY_PREFIX = (
    "IMPORTANT: your previous answer was the reference photo itself (the store's model), which is WRONG. "
    "The person in image 1 must remain the person in the output, in image 1's own scene and background. "
    "Images 2+ are garment swatches only; never output them or their model.\n\n"
)

_FIT_WORDS = {"slim": "a slim frame", "average": "an average build", "athletic": "an athletic build",
              "curvy": "a curvy figure", "broad": "a broad build"}

TRYON_NEGATIVE = ("no text, no logos, no watermark, no borders, no collage panels, no split frames, no duplicate "
                  "people, no extra limbs, no changed face, no changed background, no re-posing, no cropping, "
                  "no colour grading, no painted-on or flat garments")


def tryon_prompt(slots: list[str], names: list[str] | None = None, build: str | None = None,
                 size: str | None = None, boxes: list | None = None) -> str:
    """slots[i] = category of garment image i+2 (image 1 is the person), e.g. ["top", "shoes"].
    names: the garments' catalog names (same order), build: body-scan build, size: the size we'd pick,
    so the garment drapes like that size on that body instead of a generic model fit.
    boxes[i]: where the garment being replaced sits in image 1 ([x0, y0, x1, y1], 0-1 fractions) or None,
    so the edit stays local."""
    names = names or [""] * len(slots)
    boxes = boxes or [None] * len(slots)
    lines = []
    for i, cat in enumerate(slots):
        what = f"{cat} ({names[i]})" if names[i] else cat
        where = ""
        b = boxes[i] if i < len(boxes) else None
        if b:
            where = (f", located at roughly {round(b[0] * 100)}%-{round(b[2] * 100)}% across and "
                     f"{round(b[1] * 100)}%-{round(b[3] * 100)}% down image 1")
        if b:
            lines.append(f"{i + 1}. Image {i + 2} = the new {what}. Find the garment the person wears in that spot in "
                         f"image 1{where} and replace ONLY that garment with this one.")
        else:
            lines.append(f"{i + 1}. Image {i + 2} = the new {what}. Replace the person's current {cat} in image 1 "
                         f"with it (if they wear none, put it on where a {cat} is worn); change nothing else.")
    fit = "The new garment follows the body's existing pose, folds and shadows"
    if build in _FIT_WORDS:
        fit += f"; the person has {_FIT_WORDS[build]}"
        fit += f", so it drapes as a size {size} would" if size else ""
    fit += ", with natural wrinkles, weight and shadows."
    return (
        "TASK: in-place EDIT of image 1, a real photo of this person (not a new picture). Swap ONLY the "
        f"garment{'s' if len(slots) > 1 else ''} listed below; the result must look like the same photo.\n"
        "EDITS:\n" + "\n".join(lines) + "\n"
        "PRESERVE EXACTLY (pixel-identical outside the edited regions): the SAME person — face, hair, skin, "
        "hands, pose, body shape — every other garment, shoes and accessory, the lighting, the ORIGINAL "
        "background, the framing and the image size.\n"
        f"GARMENT FIDELITY: {fit} Copy the garment's real colour, fabric, print, cut, length and silhouette. "
        "FIT: true to size on THIS person's body, the way their current garment fits them, using the garment's "
        "named fit (e.g. 'Regular Fit' = regular, 'Slim' = slim). Do not inflate the garment: it is only "
        "oversized or baggy if its name says so. Shoulder seams sit on the shoulders, hems at the garment's real "
        "length. The garment images are references only: ignore the model, their body, pose and background, "
        "and any logo, size label, text or watermark in them; never output a reference image.\n"
        "OUTPUT: one photorealistic photo, sharp, at image 1's exact framing and resolution.\n"
        f"NEGATIVE: {TRYON_NEGATIVE}."
    )


# Standalone white-background shot of one garment (closet.clean_shot).
CLEAN_SHOT = (
    "TASK: studio product photo of ONE item from the photo: the {label} ({color} {category}). "
    "The photo may show other garments, a person or a background: ignore every one of them and render ONLY the "
    "{label}. If the {label} is an accessory (earbuds, watch, bag, belt, glasses, jewelry) render just that "
    "accessory on its own, small as it is, not the clothes around it.\n"
    "ITEM FIDELITY: same colour, fabric, print, logo, shape and fit as the {label} in the photo, identical cut and "
    "length; nothing added, nothing removed.\n"
    "SPEC: ghost-mannequin for clothes, flat-lay for accessories/shoes, front view, centred, filling ~80% of the "
    "frame, pure white background (seamless, #FFFFFF), soft even studio lighting from the front, no shadows beyond "
    "a faint contact shadow, square 1:1 frame, sharp focus.\n"
    "NEGATIVE: no person, no skin, no hair, no hanger, no other garments or items, no text, no logos other than "
    "the item's own, no watermark, no border, no props, no background objects, no colour grading."
)
CLEAN_SHOT_RETRY = (
    "You rendered the wrong item last time. "
    + CLEAN_SHOT
    + "\nCHECK BEFORE ANSWERING: the output must contain the {label} and NOTHING else. A coat, shirt, trousers or "
    "any other garment that is not the {label} is a failure."
)
CLEAN_SHOT_VERSION = "v3"  # the prompt names the piece; the result is checked (CLEAN_SHOT_CHECK)


def clean_shot_prompt(piece: dict | None, retry: bool = False) -> str:
    """CLEAN_SHOT filled with the piece's label / colour / category (falls back to generic words)."""
    piece = piece or {}
    label = " ".join(str(piece.get("label") or "garment").split()) or "garment"
    return (CLEAN_SHOT_RETRY if retry else CLEAN_SHOT).format(
        label=label, color=str(piece.get("color") or "").strip() or "same-coloured",
        category=str(piece.get("category") or "item").strip() or "item")


CLEAN_SHOT_CHECK = """ROLE: QA for a product-photo generator.
INPUT: one generated image. It was supposed to show ONLY this item: "{label}" ({color} {category}), alone on a
white background.
HARD RULES:
1. match = true only if the main object in the image is the {label} (same type of item, same colour family).
2. match = false if the image shows a different kind of item (e.g. a coat instead of earbuds), a person, or
   several items.
3. seen: at most 6 words naming what the image actually shows.
OUTPUT (JSON only): {{"match": true|false, "seen": "<what it shows>"}}
EXAMPLE: {{"match": false, "seen": "camel wool overcoat"}}"""

PAIR = f"""ROLE: stylist picking feed items for one shopper.
INPUT:
User style: {{style_text}}
Price ranges (USD, per category): {{price_ranges}}
Closet (the ONLY items they own): {{closet_json}}
{{memory}}
Candidates: {{products_json}}
HARD RULES:
1. Pick the {{k}} candidates that best complete outfits with closet items and fit the style and price ranges.
2. product_id must be a candidate id; pairs_with must be closet ids. Never invent ids.
3. A reason may name a closet item ONLY by the exact "label" of an item in Closet (optionally with its "brand",
   e.g. "your Stüssy tee"). Do not mention any garment, colour or brand that is not in Closet or the candidate.
4. reason: at most 8 words, casual second person, lowercase start, no emoji, no quotes.
5. Vary reasons: spread picks across different closet items; vary the angle (colour contrast, silhouette,
   style, layering, occasion, price); never start two reasons with the same words.
6. {_ONLY_JSON}
OUTPUT: array of {{k}} objects, best first:
[{{{{"product_id": string, "score": number 0-1, "reason": string, "pairs_with": [string]}}}}]"""
PAIR_VERSION = "v5"  # bump when PAIR changes so cached rankings and the reason bank start fresh (v5: rules-first shortlist)

FIT_TAGGER = f"""ROLE: fashion cataloguer. The image is an outfit photo (mirror selfie, street photo or flat-lay).
HARD RULES:
1. List every clothing item and accessory that is clearly visible and buyable, most prominent first, max 8.
2. A pair of shoes is one item. Ignore phones, mirrors, furniture, faces and background.
3. Use only the listed vocabulary values; lowercase.
4. {_ONLY_JSON} If there is no clothing, output [].
OUTPUT: array of
[{{{_ITEM_FIELDS.format(n=3)},
  "box": [x_min, y_min, x_max, y_max] tight box around that item as fractions 0-1 of width/height}}]
EXAMPLE: [{{"label":"light-wash baggy jeans","category":"bottom","color":"light blue","pattern":"solid","style_tags":["streetwear","y2k"],"brand":null,"box":[0.3,0.45,0.7,0.98]}}]"""
FIT_TAGGER_VERSION = "v2"  # bump when FIT_TAGGER changes so cached outfit tags are redone (v2: boxes)

VIBE = f"""ROLE: you turn a shopper's search into catalog filters for a clothing store.
INPUT search: "{{q}}"
HARD RULES:
1. Think about occasion, season and vibe ("fit for a rooftop party" -> smart casual, dark or bold colours).
2. Use only the listed vocabulary values; empty arrays mean "anything".
3. {_ONLY_JSON}
OUTPUT:
{{{{"styles": up to 3 of [{_S}],
  "categories": up to 3 of [{_C}],
  "colors": up to 4 plain colour words,
  "keywords": up to 5 short item phrases to search for (e.g. "linen shirt")}}}}
EXAMPLE: {{{{"styles":["minimalist","classic"],"categories":["top"],"colors":["white","beige"],"keywords":["linen shirt"]}}}}"""
VIBE_VERSION = "v2"


# ---- Digitize wardrobe: one photo of several clothes -> separate closet items (with crop boxes) ----
DIGITIZE = f"""ROLE: you digitize a wardrobe from ONE photo (flat-lay, rack/chair, or worn by a person: mirror selfie, full-body or street photo).
HARD RULES:
1. List EVERY separate garment and accessory visible, biggest first, max 10, INCLUDING partly hidden layers: a
   sweater, hoodie, shirt or tee under a jacket (visible collar, neckline, hem or cuffs) is its own item with
   "occluded": true. Describe it from the visible part only.
2. Never collapse a worn outfit into one item: top, bottoms and shoes are separate items, plus one per piece of
   outerwear and per visible accessory (headphones, earbuds, watch, necklace, bracelet, ring, bag, cap, hat,
   beanie, belt, scarf, sunglasses, glasses).
3. A pair of shoes is one item. Ignore faces, skin, phones, keys, lanyards, wallets, mirrors, furniture, hangers
   and background.
4. "label" = the colour + the item type you actually SEE (e.g. "grey crewneck sweater", "black over-ear
   headphones"). "category" must match that type: tee/shirt/sweater/hoodie/tank/blouse/polo = top;
   jacket/coat/blazer/vest/cardigan worn open = outerwear; pants/jeans/shorts/skirt = bottom; dress/jumpsuit =
   dress; sneakers/boots/shoes/sandals = shoes; headphones/bag/hat/jewelry/belt/glasses/scarf = accessory.
5. "brand": ONLY when a logo, wordmark or printed text naming the brand is readable in THIS photo, and then
   "brand_evidence" says what you saw (e.g. "Nike swoosh on chest"). Otherwise both null. Never guess a brand
   from style, cut, colour or shape.
6. Use only the listed vocabulary values; lowercase.
7. {_ONLY_JSON} If there is no clothing, output [].
OUTPUT: array of
[{{{_ITEM_FIELDS.format(n=3)},
  "brand_evidence": string or null,
  "occluded": boolean,
  "formality": integer 1-5 (1 loungewear, 5 black tie),
  "box": [x_min, y_min, x_max, y_max] as fractions 0-1 of width/height, tight around the visible part of that one item}}]
EXAMPLE: [{{"label":"black puffer jacket","category":"outerwear","color":"black","pattern":"solid","style_tags":["streetwear"],"brand":"the north face","brand_evidence":"logo on left chest","occluded":false,"formality":2,"box":[0.2,0.15,0.8,0.55]}},{{"label":"grey crewneck sweater","category":"top","color":"grey","pattern":"solid","style_tags":["minimalist"],"brand":null,"brand_evidence":null,"occluded":true,"formality":2,"box":[0.4,0.15,0.6,0.3]}},{{"label":"black over-ear headphones","category":"accessory","color":"black","pattern":"solid","style_tags":["streetwear"],"brand":null,"brand_evidence":null,"occluded":false,"formality":2,"box":[0.35,0.0,0.65,0.12]}}]"""
DIGITIZE_VERSION = "v3"  # bump when DIGITIZE changes so cached detections are redone (v3: occluded layers, accessories, brand evidence)

# ---- Photo onboarding: digitized garments -> one plain sentence describing the person's style ----
STYLE_FROM_CLOSET = f"""ROLE: you summarise a shopper's style from the clothes they just photographed.
INPUT closet (JSON): {{items_json}}
HARD RULES:
1. One sentence, at most 25 words: style words (from [{_S}]) first, then 2-4 signature pieces that appear in
   the input, then how dressed-up they tend to be.
2. Mention only pieces present in the input. {_NO_LOOKS}
3. {_ONLY_JSON}
OUTPUT: {{{{"style_text": string}}}}
EXAMPLE: {{{{"style_text":"streetwear and minimalist; light-wash denim, white tees, chunky sneakers; mostly casual"}}}}"""

# ---- Body scan: full-body photo + height -> estimated measurements for size advice ----
BODY_SCAN = f"""ROLE: you estimate body measurements from ONE full-body photo, only to recommend clothing sizes.
INPUT: the person is {{height_cm}} cm tall{{weight_part}}. Use that height as the scale for shoulder width,
chest, waist, hips and leg length.
HARD RULES:
1. Inches, rounded to the nearest 0.5.
2. If it is not one standing person in full view (head to feet), set full_body_visible=false and every number to null.
3. presenting = "unknown" whenever the department is not obvious from the clothing; never guess.
4. {_NO_LOOKS}
5. {_ONLY_JSON}
OUTPUT:
{{{{"full_body_visible": boolean,
  "build": "{"|".join(BUILDS)}",
  "chest_in": number|null, "waist_in": number|null, "hip_in": number|null, "inseam_in": number|null,
  "presenting": "men"|"women"|"unknown",
  "note": string, at most 10 words of fit advice (e.g. "long legs, pick longer inseams")}}}}"""


FIT_CREATOR = f"""ROLE: personal stylist building complete outfits for one person's body.
INPUT:
Body: {{body}}
Fit preference: {{fit}}
Style: {{style_text}}
Occasion: {{occasion}}
Budget for new pieces (USD, total per outfit): {{budget}}
Must include (catalog ids): {{must_include}}
Closet (what they already own): {{closet_json}}
Catalog candidates (in stock; your_size = the size we would order): {{products_json}}
HARD RULES:
1. Build exactly {{count}} different complete outfits: top + bottom (or dress) + shoes; outerwear and one accessory optional.
2. Every outfit MUST add 1-2 new pieces from the candidates; the rest may come from the closet. Build around at least
   one closet piece when the closet has anything usable. Use every must-include id.
3. Use only ids from Closet or Candidates, one piece per slot. Never invent ids, garments or brands.
4. reason: 1-2 sentences, casual second person, naming the build or a measurement (e.g. "slim build, 30.5 in
   waist") and the closet piece the look is built around. {_NO_LOOKS}
5. {_ONLY_JSON}
OUTPUT: array of {{count}} objects:
[{{{{"name": string 2-4 words, "reason": string, "pieces": [{{{{"slot": "{"|".join(SLOTS)}", "id": string}}}}]}}}}]"""
FIT_CREATOR_VERSION = "v3"  # bump when FIT_CREATOR changes so cached fits are rebuilt


# ---- Catalog summaries (sprint-2 A7 / B4): Product.summary, 1-2 plain sentences for the card ----
SUMMARY = f"""ROLE: you write the one-line card text for a clothing store app.
INPUT:
Product: {{name}}
Category: {{category}}; color: {{color}}; style: {{style}}{{label_part}}
Retailer description: {{description}}
HARD RULES:
1. At most 2 short sentences and 160 characters total; plain text, present tense; no brand name, price, emoji or quotes.
2. Say what the item is and how it wears.
3. Mention fabric, fit, length or details ONLY if the retailer description states them. Never invent facts.
4. If the description is "none", write one sentence from the name, colour, category and style alone.
5. {_ONLY_JSON}
OUTPUT: {{{{"summary": string}}}}
EXAMPLE: {{{{"summary":"A light-wash baggy jean with a relaxed, streetwear fit."}}}}"""
SUMMARY_VERSION = "v1"  # bump when SUMMARY changes so cached summaries are regenerated



# ---- Fit Score v2 photo critic (outfit_score.ai_critique): same 0-10 anchors as the rules ----
_CRITERIA = ["color", "silhouette", "pattern", "formality", "style", "completeness", "layering", "occasion"]
FIT_CRITIC = f"""ROLE: strict fashion stylist grading ONE outfit photo. Average outfits are 5/10; 8+ needs a reason
visible in the photo.
INPUT:
Pieces we know about (may be incomplete): {{items_json}}
Occasion: {{occasion}}
HARD RULES:
1. Grade each criterion 0-10 with these anchors (5 = fine, nothing special):
- color: 10 one accent colour on neutrals; 7 all neutral or two tones of one family; 5 warm vs cool accents;
  3 three competing colours; 1 four or more / two multicolour pieces.
- silhouette: 9 intentional, well-balanced proportions; 7 balanced matching or contrasting volumes.
  Slim-on-slim and oversized-on-oversized can both work; deduct only for a visible proportion problem.
  When the framing hides fit, use 7 rather than guessing a flaw.
- pattern: 9 one print, rest solid; 7 all solid or stripes plus one print; 4 two loud prints; 1 three or more.
- formality: 9 every piece in the same dress code; 5 two steps apart; 2 clashing (blazer with gym shorts).
- style: 9 every piece clearly one style; 7 most; 5 half; 3 pieces that don't agree.
- completeness: 9 top + bottom (or dress) + shoes visible; 5 base without shoes; 2 not a full outfit.
- layering: 9 considered layers/accessories; 8 one considered extra; 7 a simple outfit needing none;
  4 visibly competing extras. A jacket or accessories are optional, never a requirement.
- occasion: 9 right for the occasion; 6 a touch off or no occasion given; 3 wrong for it.
2. note: at most 12 words, second person, names a piece visible in the photo. {_NO_LOOKS}
3. style = the single style the outfit executes best, one of: {{styles}}.
4. {_ONLY_JSON}
OUTPUT:
{{{{"criteria": {{{{{", ".join(f'"{c}": {{{{"score": integer 0-10, "note": string}}}}' for c in _CRITERIA)}}}}},
  "style": string}}}}"""
FIT_CRITIC_VERSION = "v3"  # bump when FIT_CRITIC changes so cached critiques are redone (v3: fixed structure)


# ---- JSON schemas (validated in llm.ai_json; keyed by the prompt's first line) ----
def _item_props(n: int, extra: dict | None = None, required_extra: list[str] | None = None) -> dict:
    props = {
        "label": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
        "color": {"type": "string"},
        "pattern": {"type": "string", "enum": PATTERNS},
        "style_tags": {"type": "array", "items": {"type": "string", "enum": STYLES}, "maxItems": n},
        "brand": {"type": ["string", "null"]},
    }
    props.update(extra or {})
    return {"type": "object", "required": ["label", "category", "color"] + (required_extra or []), "properties": props}


_BOX = {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}
_FORMALITY = {"type": "integer", "minimum": 1, "maximum": 5}
_CRIT = {"type": "object", "required": ["score"], "properties": {"score": {"type": ["integer", "number"]},
                                                                 "note": {"type": "string"}}}

SCHEMAS: dict[str, dict] = {
    "tagger": {"anyOf": [
        _item_props(5, {"formality": _FORMALITY, "department": {"type": ["string", "null"], "enum": DEPARTMENTS + [None]}}),
        {"type": "object", "required": ["error"], "properties": {"error": {"type": "string"}}}]},
    "pair": {"type": "array", "items": {"type": "object", "required": ["product_id"], "properties": {
        "product_id": {"type": "string"}, "score": {"type": ["number", "integer"]}, "reason": {"type": "string"},
        "pairs_with": {"type": "array", "items": {"type": "string"}}}}},
    "fit_tagger": {"type": "array", "maxItems": 8, "items": _item_props(3, {"box": _BOX})},
    "vibe": {"type": "object", "properties": {
        "styles": {"type": "array", "items": {"type": "string", "enum": STYLES}, "maxItems": 3},
        "categories": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}, "maxItems": 3},
        "colors": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 5}}},
    "digitize": {"type": "array", "maxItems": 10, "items": _item_props(3, {"formality": _FORMALITY, "box": _BOX,
                                                                      "brand_evidence": {"type": ["string", "null"]},
                                                                      "occluded": {"type": "boolean"}})},
    "style_from_closet": {"type": "object", "required": ["style_text"], "properties": {"style_text": {"type": "string"}}},
    "body_scan": {"type": "object", "required": ["full_body_visible"], "properties": {
        "full_body_visible": {"type": "boolean"}, "build": {"type": ["string", "null"], "enum": BUILDS + [None]},
        "chest_in": {"type": ["number", "integer", "null"]}, "waist_in": {"type": ["number", "integer", "null"]},
        "hip_in": {"type": ["number", "integer", "null"]}, "inseam_in": {"type": ["number", "integer", "null"]},
        "presenting": {"type": ["string", "null"], "enum": ["men", "women", "unknown", None]}, "note": {"type": ["string", "null"]}}},
    "fit_creator": {"type": "array", "items": {"type": "object", "required": ["pieces"], "properties": {
        "name": {"type": "string"}, "reason": {"type": "string"},
        "pieces": {"type": "array", "items": {"type": "object", "required": ["slot", "id"], "properties": {
            "slot": {"type": "string", "enum": SLOTS}, "id": {"type": "string"}}}}}}},
    "summary": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    "fit_critic": {"type": "object", "required": ["criteria"], "properties": {
        "criteria": {"type": "object", "properties": {c: _CRIT for c in _CRITERIA}}, "style": {"type": "string"}}},
    "clean_shot_check": {"type": "object", "required": ["match"], "properties": {
        "match": {"type": "boolean"}, "seen": {"type": "string"}}},
}

_FIRST_LINES: dict[str, str] = {
    TAGGER.splitlines()[0]: "tagger", PAIR.splitlines()[0]: "pair", FIT_TAGGER.splitlines()[0]: "fit_tagger",
    VIBE.splitlines()[0]: "vibe", DIGITIZE.splitlines()[0]: "digitize",
    STYLE_FROM_CLOSET.splitlines()[0]: "style_from_closet", BODY_SCAN.splitlines()[0]: "body_scan",
    FIT_CREATOR.splitlines()[0]: "fit_creator", SUMMARY.splitlines()[0]: "summary",
    FIT_CRITIC.splitlines()[0]: "fit_critic", CLEAN_SHOT_CHECK.splitlines()[0]: "clean_shot_check",
}


def schema_for(prompt: str) -> dict | None:
    """The JSON schema a (formatted) prompt's reply must match, found by its ROLE line; None if unknown."""
    first = prompt.lstrip().splitlines()[0] if prompt.strip() else ""
    name = _FIRST_LINES.get(first)
    return SCHEMAS.get(name) if name else None
