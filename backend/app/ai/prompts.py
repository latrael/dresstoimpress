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

# Appended to TAGGER for retailer photos, where a model often wears a whole outfit.
TAGGER_HINT = """
This photo is for the product "{hint}". If it shows a person wearing several things, describe
only that product and ignore everything else they wear."""

TRYON = (
    "Dress the person in the first image in the garments shown in the other images. "
    "Keep their face, skin tone, hair, body shape and proportions exactly the same. "
    "Change only the clothing. Full body, standing, plain light background, natural lighting."
)

TRYON_VERSION = "v2"  # bump to invalidate cached try-ons when the prompt changes


def tryon_prompt(slots: list[str]) -> str:
    """slots[i] = category of garment image i+2 (image 1 is the person), e.g. ["top", "shoes"]."""
    lines = [f"Image {i + 2} shows a {cat}: put it on the person, replacing only their current {cat}."
             for i, cat in enumerate(slots)]
    return (
        "Image 1 is the person. " + " ".join(lines) + " "
        "Keep everything else from image 1 exactly the same: their other clothing, shoes, face, skin tone, hair, "
        "body shape, proportions, pose and background. "
        "The garment images are references only: if they show a model, a logo, a size label, text or a watermark, "
        "ignore all of it and use only the garment's color, fabric, fit and details. "
        "Output one photorealistic full-body photo of the person from image 1, with no text, logos or borders."
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
{{"product_id": str, "score": number 0-1, "reason": at most 8 words, casual second person, naming the closet item by its label, "pairs_with": [closet item ids]}}
Use only product ids from the candidates. Only mention closet items that are in the closet list, by their label; never invent closet items.
Make every reason sound different, like a friend reacting to each piece:
- spread the picks across different closet items instead of naming the same one every time;
- vary the angle: color contrast, silhouette or fit, the style it pushes, layering, the occasion, or the price;
- never start two reasons with the same words.
Shapes to vary between (fill in real labels): "<color> on <color> with your <item>", "layer it over your <item>",
"gives your <item> a <style> edge", "only $<price> and it works with your <item>"."""
PAIR_VERSION = "v2"  # bump when PAIR changes so cached rankings and the reason bank start fresh

FIT_TAGGER = """You are a fashion cataloguer. The image is an outfit photo (mirror selfie, street photo, or flat-lay).
List every clothing item and accessory you can clearly see that someone could buy.
Return only a JSON array, at most 8 items, most prominent first:
[{"label": 2-4 word plain name, e.g. "light-wash baggy jeans",
  "category": "top" | "bottom" | "outerwear" | "shoes" | "dress" | "accessory",
  "color": main color in plain words,
  "pattern": "solid" | "striped" | "plaid" | "graphic" | "floral" | "other",
  "style_tags": up to 3 from ["y2k","streetwear","minimalist","preppy","athleisure","vintage","business","boho","grunge","classic"],
  "brand": visible brand name or null (only if a logo or text is clearly readable; never guess)}]
Ignore phones, mirrors, furniture and background. If there is no person or clothing, return []."""
