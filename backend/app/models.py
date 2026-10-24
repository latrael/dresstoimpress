"""Shared data contract (unified on `staging`; see docs/schema.md).

Field names are fixed: change them only with a PR into `staging` that the whole team reviews.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["top", "bottom", "outerwear", "shoes", "dress", "accessory"]
Retailer = Literal["zara", "hm", "asos", "uniqlo", "mango"]
Pattern = Literal["solid", "striped", "plaid", "graphic", "floral", "other"]
StyleTag = Literal[
    "y2k", "streetwear", "minimalist", "preppy", "athleisure",
    "vintage", "business", "boho", "grunge", "classic",
]


class Size(BaseModel):
    name: str                 # "M", "32", "9.5", "One size"
    in_stock: bool = True


class Product(BaseModel):
    id: str                   # "{retailer}:{product_code}:{color}", stable across scrapes
    retailer: Retailer
    name: str
    brand: str
    category: Category        # singular, same vocabulary as closet items
    price_usd: float
    sale_price_usd: Optional[float] = None
    currency: Literal["USD"] = "USD"
    colors: list[str] = []
    sizes: list[Size] = []    # sold-out sizes kept with in_stock=false (greyed out in the app)
    in_stock: bool = True     # any size in stock
    image_url: str
    product_url: str
    style_tags: list[str] = []
    pattern: Optional[Pattern] = None     # from the tagger
    formality: Optional[int] = Field(None, ge=1, le=5)  # from the tagger
    label: str = ""           # short plain name from the tagger, e.g. "white baby tee"
    scraped_at: Optional[str] = None      # ISO time of the scrape
    source: Literal["ingest", "live_search", "seed"] = "ingest"


class ClosetItem(BaseModel):
    id: str
    user_id: str
    image_url: str
    category: Category
    color: str
    pattern: Pattern = "solid"
    style_tags: list[str] = []
    formality: int = Field(3, ge=1, le=5)
    source: Literal["photo", "receipt", "seed"] = "photo"
    label: str = ""  # short plain name, e.g. "black cargo pants" (optional, added Fri night)


class User(BaseModel):
    id: str
    display_name: str
    style_text: str = ""
    price_ranges: dict[str, list[float]] = {}
    body_photo_url: Optional[str] = None
    friends: list[str] = []


# ---- AI endpoint requests / responses ----

class TagRequest(BaseModel):
    user_id: str
    image_url: str


class TryOnRequest(BaseModel):
    user_id: str
    product_ids: list[str] = []
    closet_item_ids: list[str] = []


class TryOnResponse(BaseModel):
    image_url: str
    cached: bool


class PairRequest(BaseModel):
    user_id: str
    candidate_product_ids: list[str] = []


class PairResult(BaseModel):
    product_id: str
    id: str = ""  # same as product_id; NABIL.md reads `id`
    score: float = Field(ge=0, le=1)
    reason: str
    pairs_with: list[str] = []


class FitTag(BaseModel):
    label: str
    retailer: Optional[str] = None
    product_id: Optional[str] = None
    closet_item_id: Optional[str] = None


class ShopFitRequest(BaseModel):
    viewer_id: str
    tagged: list[FitTag] = []
    photo_url: Optional[str] = None  # if set and tagged is empty, items are auto-tagged from the photo


class SizeRequest(BaseModel):
    product_id: str
    height_cm: float
    weight_kg: float
    fit: Literal["slim", "regular", "oversized"] = "regular"
    shoe_us: Optional[float] = None
    waist_in: Optional[float] = None


class TagFitRequest(BaseModel):
    image_url: str
