"""Shared data contract (unified on `staging`; see docs/schema.md).

Field names are fixed: change them only with a PR into `staging` that the whole team reviews.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

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


class ProductImage(BaseModel):
    url: str
    kind: Literal["product", "retailer_model"] = "product"  # garment-only vs. a model wearing it


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
    images: list[ProductImage] = []       # same product + colour only; image_url stays the primary image
    description: Optional[str] = None     # real retailer text (plain), or null; never a pairing reason
    source: Literal["ingest", "live_search", "seed"] = "ingest"
    department: Optional[Literal["men", "women", "unisex"]] = None  # retailer's section; None = unknown (shown to all)


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
    duplicate_of: Optional[str] = None  # id of a closet item that's probably the same garment (set on upload)


class User(BaseModel):
    id: str
    display_name: str
    style_text: str = ""
    price_ranges: dict[str, list[float]] = {}
    body_photo_url: Optional[str] = None
    friends: list[str] = []
    body_profile: Optional[dict] = None  # set by POST /users/{id}/body-scan (estimated inches); /size reads it
    preferred_stores: list[str] = []     # retailer ids ("hm", "uniqlo"); /feed ranks them first (a boost, not a filter)
    onboarded: bool = False              # the app sets it at the last onboarding step
    shop_for: Literal["men", "women", "both"] = "both"  # onboarding "Shop:" question; /feed + Discover filter by it


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
    mode: Literal["ai", "collage"] = "ai"  # collage = outfit board when AI images are unavailable


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
    # filled by POST /ai/tag-fit; used by shop_fit's strict matching (same type + category)
    category: Optional[str] = None
    color: Optional[str] = None
    pattern: Optional[str] = None
    style_tags: list[str] = []
    brand: Optional[str] = None
    # Where the item is in the post photo, for Inspo pins: [x_min, y_min, x_max, y_max] as 0-1 fractions
    # of the image. Set by the AI tagger; optional (old posts and hand-added tags have none). An
    # invalid box is dropped (None), never an error.
    box: Optional[list[float]] = None

    @field_validator("box", mode="before")
    @classmethod
    def _valid_box(cls, v):
        try:
            x0, y0, x1, y1 = (float(n) for n in v)
        except (TypeError, ValueError):
            return None
        ok = 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        return [x0, y0, x1, y1] if ok else None


class VibeRequest(BaseModel):
    q: str = Field(max_length=200)


class ShopFitRequest(BaseModel):
    viewer_id: str
    tagged: list[FitTag] = []
    photo_url: Optional[str] = None  # if set and tagged is empty, items are auto-tagged from the photo


class SizeRequest(BaseModel):
    product_id: str
    height_cm: Optional[float] = None   # optional with user_id: falls back to the user's body scan
    weight_kg: Optional[float] = None
    user_id: Optional[str] = None       # fills missing height / weight / waist from body_profile
    fit: Literal["slim", "regular", "oversized"] = "regular"
    shoe_us: Optional[float] = None
    waist_in: Optional[float] = None


class BodyProfileUpdate(BaseModel):
    """PATCH /users/{id}/body-profile: measurements the user typed (onboarding / profile). Only the
    fields sent change; a field sent as null is cleared. Lengths in cm (stored as inches)."""
    height_cm: Optional[float] = Field(None, ge=120, le=230)
    weight_kg: Optional[float] = Field(None, ge=30, le=250)
    waist_cm: Optional[float] = Field(None, ge=50, le=150)
    chest_cm: Optional[float] = Field(None, ge=60, le=160)
    hip_cm: Optional[float] = Field(None, ge=65, le=165)
    inseam_cm: Optional[float] = Field(None, ge=55, le=100)
    shoe_us: Optional[float] = Field(None, ge=3, le=18)
    fit: Optional[Literal["slim", "regular", "oversized"]] = None
    usual_sizes: Optional[dict[Category, str]] = None  # e.g. {"top": "M", "bottom": "32/32"}


class CompleteLookRequest(BaseModel):
    user_id: str
    product_id: str                     # the product the user just swiped right on
    budget_usd: Optional[float] = None  # total for new items incl. the anchor


class FitScoreRequest(BaseModel):
    """Any mix: raw items (a Fit Check post's `tagged`), catalog products, closet items."""
    items: list[dict] = []
    product_ids: list[str] = []
    closet_item_ids: list[str] = []


class TagFitRequest(BaseModel):
    image_url: str
    hint: Optional[str] = None  # /products/tag only: the product name, for photos of a model in a full outfit
