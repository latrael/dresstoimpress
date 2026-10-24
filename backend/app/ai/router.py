import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models import (ClosetItem, CompleteLookRequest, FitScoreRequest, PairRequest, PairResult, ShopFitRequest,
                      SizeRequest, TagFitRequest, TagRequest, TryOnRequest, TryOnResponse)
from ..store import DATA_DIR, store
from . import service
from .llm import AI_BUDGET_USD, MAX_TRYONS, BadModelOutput, usage

router = APIRouter(tags=["ai"])

MAX_UPLOAD = 10 * 1024 * 1024
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}


async def _save_upload(file: UploadFile) -> str:
    """Save an uploaded image under /static/uploads and return its public URL.
    Nabil's commerce/fitcheck.py imports this: don't rename it."""
    if file.content_type not in EXT:
        raise HTTPException(415, f"unsupported image type {file.content_type}")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "image over 10 MB")
    folder = DATA_DIR / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + EXT[file.content_type]
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
        raise HTTPException(502, f"tagger failed: {e}")


@router.post("/tryon", response_model=TryOnResponse)
def tryon(req: TryOnRequest):
    try:
        url, cached, mode = service.try_on(req.user_id, req.product_ids, req.closet_item_ids)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except BadModelOutput as e:
        raise HTTPException(502, f"try-on failed: {e}")
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
            raise HTTPException(502, f"fit tagger failed: {e}")
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
        raise HTTPException(502, f"tagger failed: {e}")


@router.post("/ai/tag-fit")
def tag_fit(req: TagFitRequest):
    """Items visible in an outfit photo -> Fit Check tags. Ryan: call after a post is created
    to pre-fill tags; Nabil: store them as the post's `tagged`."""
    if not req.image_url.startswith(("http://", "https://")):
        raise HTTPException(400, "image_url must be http(s)")
    try:
        return service.tag_fit(req.image_url)
    except BadModelOutput as e:
        raise HTTPException(502, f"fit tagger failed: {e}")


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
    return recommend_size(product, req.height_cm, req.weight_kg, fit=req.fit,
                          shoe_us=req.shoe_us, waist_in=req.waist_in)


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
