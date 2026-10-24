"""Prompts for the AI pipeline. Log any changes in the Notion prompt log."""

TAGGER = """You are a fashion cataloguer. Look at the single clothing item in the image.
Return only JSON, no prose:
{"label": 2-4 word plain name of the item, e.g. "black cargo pants", "white baby tee",
 "category": "top" | "bottom" | "outerwear" | "shoes" | "dress" | "accessory",
 "color": main color in plain words,
 "pattern": "solid" | "striped" | "plaid" | "graphic" | "floral" | "other",
 "style_tags": up to 5 from ["y2k","streetwear","minimalist","preppy","athleisure","vintage","business","boho","grunge","classic"],
 "formality": integer 1-5}
If the image is not clothing, return {"error": "not_clothing"}."""

TRYON = (
    "Dress the person in the first image in the garments shown in the other images. "
    "Keep their face, skin tone, hair, body shape and proportions exactly the same. "
    "Change only the clothing. Full body, standing, plain light background, natural lighting."
)

PAIR = """You are a stylist.
User style: {style_text}
Price ranges (USD, per category): {price_ranges}
Closet: {closet_json}
{memory}
Candidates: {products_json}

Pick the {k} candidates that best complete outfits with items already in the closet
and fit the style and price ranges.
Return only a JSON array of objects:
{{"product_id": str, "score": number 0-1, "reason": at most 8 words, casual second person, naming the closet item by its label, e.g. "goes with your black cargo pants", "pairs_with": [closet item ids]}}
Use only product ids from the candidates."""
