import os
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models import (BodyProfileUpdate, ClosetItem, CompleteLookRequest, FitScoreRequest, PairRequest, PairResult, ShopFitRequest,
                      SizeRequest, TagFitRequest, TagRequest, TryOnRequest, TryOnResponse, VibeRequest)
from ..store import DATA_DIR, store
from . import service
from .llm import AI_BUDGET_USD, MAX_TRYONS, BadModelOutput, usage

router = APIRouter(tags=["ai"])


def _ai_down(what: str, err: Exception) -> HTTPException:
    """502 with a plain message for the app; provider details (status codes, request ids) go to the log."""
    import logging

    logging.getLogger(__name__).warning("%s failed: %s", what, err)
    return HTTPException(502, f"{what} is unavailable right now, try again in a minute")

MAX_UPLOAD = 10 * 1024 * 1024
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}


MAX_SIDE_PX = 2048


def _clean_image(data: bytes, content_type: str) -> tuple[bytes, str]:
    """Re-encode an upload without its metadata: phone photos carry EXIF GPS, and /static/uploads
    needs no key. The EXIF rotation is applied first (so the saved image is upright) and the longest
    side is capped. PNG stays PNG; everything else becomes JPEG. If Pillow can't read it (e.g. HEIC
    without a plugin) the bytes are kept as uploaded."""
    import io
    import logging

    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
            buf = io.BytesIO()
            if content_type == "image/png":
                im.save(buf, "PNG")  # no pnginfo / exif passed: metadata is dropped
                return buf.getvalue(), ".png"
            im.convert("RGB").save(buf, "JPEG", quality=90)
            return buf.getvalue(), ".jpg"
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).warning("upload kept as-is (could not re-encode %s): %s", content_type, e)
        return data, EXT[content_type]


async def _save_upload(file: UploadFile) -> str:
    """Save an uploaded image under /static/uploads (metadata stripped, upright) and return its
    public URL. Nabil's commerce/fitcheck.py imports this: don't rename it."""
    if file.content_type not in EXT:
        raise HTTPException(415, f"unsupported image type {file.content_type}")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "image over 10 MB")
    data, ext = _clean_image(data, file.content_type)
    folder = DATA_DIR / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + ext
    (folder / name).write_bytes(data)
    base = os.getenv("PUBLIC_BASE", "http://localhost:8000").rstrip("/")
    return f"{base}/static/uploads/{name}"


@router.post("/closet/upload", response_model=ClosetItem)
async def closet_upload(user_id: str = Form(...), file: UploadFile = File(...)):
    """Photo straight from the app: save, then tag. Same output as /closet/tag."""
    url = await _save_upload(file)
    return closet_tag(TagRequest(user_id=user_id, image_url=url))


@router.get("/closet/{user_id}", response_model=list[ClosetItem])
def closet_list(user_id: str):
    """Everything in this user's closet (newest last)."""
    return store.list("closet_items", user_id=user_id)


@router.delete("/closet/{user_id}/{item_id}")
def closet_delete(user_id: str, item_id: str):
    """Remove one closet item, e.g. after "you already have this" on upload."""
    item = store.get("closet_items", item_id)
    if not item or item.get("user_id") != user_id:
        raise HTTPException(404, "unknown closet item")
    store.delete("closet_items", item_id)
    return {"deleted": item_id}


@router.post("/users/{user_id}/body-photo")
async def body_photo(user_id: str, file: UploadFile = File(...)):
    """Private full-body photo used for try-on."""
    url = await _save_upload(file)
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    user["body_photo_url"] = url
    store.put("users", user_id, user)
    return {"body_photo_url": url}


@router.delete("/users/{user_id}/body-photo")
def body_photo_delete(user_id: str):
    """User screen "delete my photo": forgets the try-on / body-scan photo and deletes the file if it's
    one of ours (/static/uploads). Measurements (body_profile) stay. {"deleted": false} if there was none."""
    from ..static_urls import local_static_path

    user = store.get("users", user_id)
    url = (user or {}).get("body_photo_url")
    if not url:
        return {"deleted": False}
    path = local_static_path(url, DATA_DIR)
    if path and path.parent.name == "uploads":
        path.unlink(missing_ok=True)
    user["body_photo_url"] = None
    store.put("users", user_id, user)
    return {"deleted": True}


@router.post("/closet/digitize", response_model=list[ClosetItem])
async def closet_digitize(user_id: str = Form(...), file: UploadFile = File(...)):
    """Digitize wardrobe: one photo of several clothes (flat lay, rack, mirror selfie) -> one closet
    item per garment, each cropped to its own image. Falls back to one item for the whole photo."""
    from ..static_urls import local_static_path
    from .digitize import digitize, upright_jpeg

    url = await _save_upload(file)
    path = local_static_path(url, DATA_DIR)
    upright = upright_jpeg(path) if path else None
    if upright:
        url = url.rsplit("/", 1)[0] + "/" + upright.name
        path = upright
    try:
        items = digitize(user_id, url, path)
    except Exception as e:  # noqa: BLE001
        raise _ai_down("wardrobe scan", e)
    return items or [closet_tag(TagRequest(user_id=user_id, image_url=url))]


@router.post("/users/{user_id}/body-scan")
async def body_scan_route(user_id: str, file: UploadFile = File(...), height_cm: float = Form(...),
                          weight_kg: Optional[float] = Form(None)):
    """Body scan: full-body photo + height (weight optional) -> estimated measurements saved as
    body_profile (used by /size) and the photo saved as the try-on photo."""
    from .body_scan import HEIGHT_CM, WEIGHT_KG, merge_scan, scan

    if not HEIGHT_CM[0] <= height_cm <= HEIGHT_CM[1]:
        raise HTTPException(422, "height_cm must be between 120 and 230")
    if weight_kg is not None and not WEIGHT_KG[0] <= weight_kg <= WEIGHT_KG[1]:
        raise HTTPException(422, "weight_kg must be between 30 and 250")
    url = await _save_upload(file)
    profile = scan(url, height_cm, weight_kg)
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    user["body_photo_url"] = url
    user["body_profile"] = merge_scan(user.get("body_profile"), profile)
    store.put("users", user_id, user)
    return {"body_photo_url": url, "body_profile": user["body_profile"]}


@router.patch("/users/{user_id}/body-profile")
def body_profile_update(user_id: str, req: BodyProfileUpdate):
    """Measurements the user typed (onboarding / profile), saved server-side so they follow the user
    to any device. Merged with the body scan; typed values win. GET /users/{id} returns body_profile."""
    from .body_scan import apply_manual

    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    user["body_profile"] = apply_manual(user.get("body_profile"), req.model_dump(exclude_unset=True))
    store.put("users", user_id, user)
    return user["body_profile"]


@router.get("/users/{user_id}/style")
def user_style(user_id: str):
    """"Your Style DNA": headline, top styles, palette, formality, learned price ranges. Rules only, free."""
    from .memory import history
    from .style_profile import style_profile

    liked, discarded = history(user_id)
    return style_profile(liked, discarded, store.list("closet_items", user_id=user_id))


@router.post("/users/{user_id}/style/apply")
def apply_style(user_id: str):
    """Save the learned price ranges on the user (pairing ranks in-budget items first), and the
    headline as style_text if they never wrote one. Needs 5+ liked items."""
    profile = user_style(user_id)
    if profile["confidence"] == "low":
        raise HTTPException(409, "like at least 5 items first")
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    user["price_ranges"] = {**(user.get("price_ranges") or {}), **profile["price_ranges"]}
    if not user.get("style_text"):
        user["style_text"] = profile["headline"]
    store.put("users", user_id, user)
    return {"user": user, "profile": profile}


@router.post("/closet/tag", response_model=ClosetItem)
def closet_tag(req: TagRequest):
    if not req.image_url.startswith(("http://", "https://")):
        raise HTTPException(400, "image_url must be http(s)")
    try:
        return service.tag_closet_item(req.user_id, req.image_url)
    except service.NotClothing:
        raise HTTPException(422, "not_clothing")
    except BadModelOutput as e:
        raise _ai_down("photo tagging", e)


@router.post("/tryon", response_model=TryOnResponse)
def tryon(req: TryOnRequest):
    try:
        url, cached, mode = service.try_on(req.user_id, req.product_ids, req.closet_item_ids)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except BadModelOutput as e:
        raise _ai_down("try-on", e)
    return TryOnResponse(image_url=url, cached=cached, mode=mode)


@router.post("/pair", response_model=list[PairResult])
def pair(req: PairRequest):
    return service.pair(req.user_id, req.candidate_product_ids)


@router.post("/ai/shop-fit")
def shop_fit(req: ShopFitRequest):
    """AI half of GET /fitcheck/{post_id}/shop: Nabil's route loads the post and passes its `tagged` here
    (or calls service.shop_fit directly). Returns Products + reason, pairs_with, score, matched_tag."""
    tagged = [t.model_dump() for t in req.tagged]
    if not tagged and req.photo_url:
        if not req.photo_url.startswith(("http://", "https://")):
            raise HTTPException(400, "photo_url must be http(s)")
        try:
            tagged = service.tag_fit(req.photo_url)
        except BadModelOutput as e:
            raise _ai_down("outfit tagging", e)
    return service.shop_fit(req.viewer_id, tagged)


@router.post("/products/tag")
def products_tag(req: TagFitRequest):
    """Nabil's ingest: product image -> tags (contract fields + NABIL.md `tags` object). Cached per URL."""
    if not req.image_url.startswith(("http://", "https://")):
        raise HTTPException(400, "image_url must be http(s)")
    try:
        return service.tag_product(req.image_url, req.hint)
    except service.NotClothing:
        raise HTTPException(422, "not_clothing")
    except BadModelOutput as e:
        raise _ai_down("photo tagging", e)


@router.post("/ai/tag-fit")
def tag_fit(req: TagFitRequest):
    """Items visible in an outfit photo -> Fit Check tags. Ryan: call after a post is created
    to pre-fill tags; Nabil: store them as the post's `tagged`."""
    if not req.image_url.startswith(("http://", "https://")):
        raise HTTPException(400, "image_url must be http(s)")
    try:
        return service.tag_fit(req.image_url)
    except BadModelOutput as e:
        raise _ai_down("outfit tagging", e)


@router.post("/ai/vibe")
def vibe_route(req: VibeRequest):
    """Discover vibe search: "fit for a rooftop party" -> {styles, categories, colors, keywords, source}.
    Styles/categories use the catalog vocabularies. Never 502s: falls back to keyword rules."""
    from .vibe import vibe

    if not req.q.strip():
        raise HTTPException(422, "q is empty")
    return vibe(req.q)


@router.get("/ai/usage")
def ai_usage():
    """Running AI spend estimate. Check it from a browser during the hackathon."""
    return {**usage(), "budget_usd": AI_BUDGET_USD, "max_tryons": MAX_TRYONS}


@router.post("/size")
def size(req: SizeRequest):
    """'We pick your size': {size, confidence, reason}. Only returns sizes in stock for that product."""
    from .compat import get_product
    from .sizing import recommend_size

    product = get_product(req.product_id)
    if not product:
        raise HTTPException(404, "unknown product")
    scan = ((store.get("users", req.user_id) or {}).get("body_profile") or {}) if req.user_id else {}
    height = req.height_cm or scan.get("height_cm")
    weight = req.weight_kg or scan.get("weight_kg")
    fit = req.fit if "fit" in req.model_fields_set or not scan.get("fit") else scan["fit"]
    usual = (scan.get("usual_sizes") or {}).get(product.get("category"))
    if not height or not weight:
        known = _usual_size(product, usual) if usual else None  # no body numbers, but a usual size
        if known:
            return known
        raise HTTPException(422, "add your height and weight (or do a body scan with both)")
    out = recommend_size(product, height, weight, fit=fit, shoe_us=req.shoe_us or scan.get("shoe_us"),
                         waist_in=req.waist_in or scan.get("waist_in"))
    if not out.get("size") and usual:
        out = _usual_size(product, usual) or out
    return out


def _usual_size(product: dict, usual: str) -> dict | None:
    """The user's usual size for this category, if this product has it in stock."""
    for s in product.get("sizes") or []:
        if str(s).strip().lower() == usual.strip().lower():
            return {"size": s, "confidence": "medium", "reason": "your usual size"}
    return None


@router.post("/complete-look")
def complete_look_route(req: CompleteLookRequest):
    """Full outfit around a swiped product: fills top/bottom/shoes (or dress/shoes) from the user's
    closet first, then in-stock catalog items within budget. No AI call, instant."""
    from .compat import get_product, list_products
    from .complete_look import complete_look

    anchor = get_product(req.product_id)
    if not anchor:
        raise HTTPException(404, "unknown product")
    user = store.get("users", req.user_id) or {}
    closet = store.list("closet_items", user_id=req.user_id)
    catalog = [p for p in list_products() if p["id"] != anchor["id"]]
    return complete_look(anchor, closet, catalog, budget_usd=req.budget_usd,
                         style_text=user.get("style_text", ""))


@router.post("/ai/fit-score")
def fit_score(req: FitScoreRequest):
    """Fit Score badge: {score 0-100, verdict, notes, breakdown}. Rules only: free and instant.
    Send a Fit Check post's `tagged` as `items`, or ids for a complete-the-look / closet outfit."""
    from .compat import get_product
    from .outfit_score import score_outfit

    items = list(req.items)
    for pid in req.product_ids:
        p = get_product(pid)
        if not p:
            raise HTTPException(404, f"unknown product {pid}")
        items.append({"category": p.get("category"), "color": (p.get("colors") or [""])[0],
                      "pattern": p.get("pattern"), "formality": p.get("formality"),
                      "style_tags": p.get("style_tags", []), "label": p.get("label") or p.get("name")})
    for cid in req.closet_item_ids:
        c = store.get("closet_items", cid)
        if not c:
            raise HTTPException(404, f"unknown closet item {cid}")
        items.append(c)
    return score_outfit(items)
