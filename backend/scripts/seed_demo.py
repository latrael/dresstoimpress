"""Seed the demo user u_demo with a closet and a few products so the AI
endpoints work before Nabil's Apify ingest lands. Safe to re-run.

    python -m scripts.seed_demo
Replace the placeholder image URLs with real photos before the demo.
"""
from pathlib import Path

from app.store import store

IMG = "https://picsum.photos/seed/{}/600/800"

# AI-generated fictional person (Gemini), neutral outfit so try-on swaps are obvious
import os, shutil  # noqa: E401,E402
from app.store import DATA_DIR  # noqa: E402

_src = Path(__file__).resolve().parent.parent / "assets" / "demo_body.jpg"
(DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
shutil.copy(_src, DATA_DIR / "uploads" / "demo_body.jpg")
BODY = os.getenv("PUBLIC_BASE", "http://localhost:8000").rstrip("/") + "/static/uploads/demo_body.jpg"

store.put("users", "u_demo", {
    "id": "u_demo", "display_name": "Demo", "style_text": "Y2K, baggy jeans",
    "price_ranges": {"top": [10, 40], "bottom": [20, 60], "outerwear": [30, 90]},
    "body_photo_url": BODY, "friends": ["u_adam", "u_nabil", "u_ryan"],
})

closet = [
    ("ci_demo_1", "bottom", "black", ["streetwear"], "black cargos"),
    ("ci_demo_2", "bottom", "light blue", ["y2k"], "baggy jeans"),
    ("ci_demo_3", "shoes", "white", ["classic"], "white sneakers"),
]
for cid, cat, color, tags, seed in closet:
    store.put("closet_items", cid, {
        "id": cid, "user_id": "u_demo", "image_url": IMG.format(seed.replace(" ", "")),
        "category": cat, "color": color, "pattern": "solid", "style_tags": tags,
        "formality": 2, "source": "seed", "label": seed,
    })

products = [
    ("hm-demo-1", "hm", "H&M", "Cropped baby tee", "top", 12.99, ["y2k"]),
    ("zara-demo-1", "zara", "Zara", "Oversized denim jacket", "outerwear", 59.90, ["streetwear"]),
    ("uniqlo-demo-1", "uniqlo", "Uniqlo", "Graphic crewneck", "top", 24.90, ["streetwear"]),
    ("asos-demo-1", "asos", "ASOS", "Butterfly print halter", "top", 28.00, ["y2k"]),
    ("mango-demo-1", "mango", "Mango", "Leather bomber", "outerwear", 129.99, ["classic"]),
]
for pid, ret, brand, name, cat, price, tags in products:
    store.put("products", pid, {
        "id": pid, "retailer": ret, "name": name, "brand": brand, "category": cat,
        "price_usd": price, "sale_price_usd": None, "colors": [],
        "sizes": [{"name": s, "in_stock": s != "XL"} for s in ["XS", "S", "M", "L", "XL"]],
        "in_stock": True, "image_url": IMG.format(pid), "product_url": "https://example.com",
        "style_tags": tags, "currency": "USD", "source": "seed",
    })

print("seeded u_demo: 3 closet items, 5 products")
