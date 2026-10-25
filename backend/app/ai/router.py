import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..models import (BodyProfileUpdate, ClosetItem, ClosetOutfit, CompleteLookRequest, FitCreateRequest, FitScoreRequest, PairRequest,
                      PairResult, ShopFitRequest,
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


async def _save_photo(file: UploadFile, upright: bool = True) -> tuple[str, Path | None]:
    """Save an upload and return (public url, local path); `upright` re-saves it as a JPEG with the EXIF
    rotation applied, so the model and the crops see the same upright picture."""
    from ..static_urls import local_static_path
    from .digitize import upright_jpeg

    url = await _save_upload(file)
    path = local_static_path(url, DATA_DIR)
    upright = upright_jpeg(path) if (path and upright) else None
    if upright:
        url = url.rsplit("/", 1)[0] + "/" + upright.name
        path = upright
    return url, path


@router.post("/closet/upload")
async def closet_upload(user_id: str = Form(...), file: Optional[UploadFile] = File(None),
                        files: list[UploadFile] = File([]), kind: Optional[str] = Form(None)):
    """Closet v2 upload. 1-8 `files` parts + `kind` = "piece" (each photo is one garment) or "outfit"
    (each photo is a whole fit: every garment is detected and cropped; default) ->
    {"added": [ClosetItem], "merged": [ClosetItem] (existing items a photo matched; the photo was added to
    their `worn_in`), "skipped": n, "outfits": [outfit record per outfit photo]}. Each item stands alone:
    `display_image_url` (a generated clean shot of the user's own crop, else the crop; never a catalog photo),
    `crop_image_url`, `brand`, `product_id`, `worn_in`, `outfit_id`.
    Backward compat: a single `file` part with no `kind` (the old app call) is digitized like an outfit (every
    garment becomes an item) but the response is the first ClosetItem only. Send `kind` to get them all."""
    from . import closet

    legacy = file is not None and not files and kind is None
    kind = kind or "outfit"
    if kind not in closet.KINDS:
        raise HTTPException(422, "kind must be piece or outfit")
    uploads = [u for u in [file, *files] if u is not None]
    if not uploads:
        raise HTTPException(422, "send 1-8 image parts named files (or one named file)")
    if len(uploads) > closet.MAX_PHOTOS:
        raise HTTPException(413, f"at most {closet.MAX_PHOTOS} photos per upload")
    photos = [await _save_photo(u, upright=kind == "outfit") for u in uploads]
    try:
        out = closet.add_photos(user_id, photos, kind)
    except BadModelOutput as e:
        raise _ai_down("photo tagging", e)
    if legacy:
        if out["added"]:
            return out["added"][0]
        if out["merged"]:
            return out["merged"][0]
        raise HTTPException(422, "not_clothing")
    return out


@router.patch("/closet/{user_id}/{item_id}")
def closet_edit(user_id: str, item_id: str, patch: dict):
    """Edit one piece: {label?, brand?, category?, color?, product_id?}. `product_id: null` clears the catalog
    match (the picture never changes: owned pieces always show the user's own photo); a product id links it for "shop similar"."""
    from . import closet

    item = _own_item(user_id, item_id)
    try:
        return closet.edit(item, patch)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/closet/{user_id}/{item_id}/reshoot")
def closet_reshoot(user_id: str, item_id: str):
    """Regenerate the piece's clean product shot (falls back to the crop when image AI is off)."""
    from . import closet

    return closet.reshoot(_own_item(user_id, item_id))


def _own_item(user_id: str, item_id: str) -> dict:
    item = store.get("closet_items", item_id)
    if not item:
        raise HTTPException(404, "unknown closet item")
    if item.get("user_id") != user_id:
        raise HTTPException(403, "not your closet item")
    return item


@router.get("/closet/{user_id}/outfits", response_model=list[ClosetOutfit])
def closet_outfits(user_id: str):
    """The user's outfits (whole-fit photos: closet uploads with kind=outfit and Fit Check posts), newest
    first, each with its `pieces` (ClosetItems) embedded. Sprint-3 §1.3."""
    from . import closet

    return closet.list_outfits(user_id)


@router.delete("/closet/{user_id}/outfits/{outfit_id}")
def closet_outfit_delete(user_id: str, outfit_id: str):
    """Remove an outfit record. Its pieces stay in the closet (their `outfit_id` is cleared). 404 if it
    isn't that user's."""
    from . import closet

    if not closet.delete_outfit(user_id, outfit_id):
        raise HTTPException(404, "unknown outfit")
    return {"deleted": outfit_id}


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
async def body_scan_route(user_id: str, file: Optional[UploadFile] = File(None), files: list[UploadFile] = File([]),
                          height_cm: float = Form(...), weight_kg: Optional[float] = Form(None), commit: bool = True):
    """Body scan: 1-6 full-body photos (`files`, or the single `file` field) + height (weight optional) ->
    estimated measurements saved as body_profile (used by /size); the first full-body photo becomes the
    try-on photo. Every full-body photo is scanned and the estimates averaged (build by majority vote);
    `body_profile.scan_photos` is how many were used and `confidence` low / medium / high for 1 / 2 / 3+.
    Photos that aren't full-body are ignored and counted in `skipped`.

    `?commit=false` (draft, for a review screen): runs the scan and saves the photo files, but changes
    nothing on the user (no body_photo_url, no body_profile). The response has the same shape with
    `committed: false`; the app then calls POST /users/{id}/body-scan/confirm with the (edited) profile
    and the returned body_photo_url to save it. Default `commit=true` saves right away (`committed: true`)."""
    from .body_scan import HEIGHT_CM, WEIGHT_KG, merge_scan, scan_many

    if not HEIGHT_CM[0] <= height_cm <= HEIGHT_CM[1]:
        raise HTTPException(422, "height_cm must be between 120 and 230")
    if weight_kg is not None and not WEIGHT_KG[0] <= weight_kg <= WEIGHT_KG[1]:
        raise HTTPException(422, "weight_kg must be between 30 and 250")
    uploads = [f for f in [file, *files] if f is not None and (f.filename or f.size)]
    if not uploads:
        raise HTTPException(422, "send a photo in `file` or 1-6 photos in `files`")
    if len(uploads) > MAX_SCAN_PHOTOS:
        raise HTTPException(422, f"at most {MAX_SCAN_PHOTOS} photos")
    urls = [await _save_upload(f) for f in uploads]
    profile, body_url, skipped = scan_many(urls, height_cm, weight_kg)
    url = body_url or urls[0]
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    merged = merge_scan(user.get("body_profile"), profile)
    if not commit:
        return {"body_photo_url": url, "body_profile": merged, "skipped": skipped, "committed": False}
    user["body_photo_url"] = url
    user["body_profile"] = merged
    store.put("users", user_id, user)
    return {"body_photo_url": url, "body_profile": user["body_profile"], "skipped": skipped, "committed": True}


MAX_SCAN_PHOTOS = 6


class BodyScanConfirm(BaseModel):
    """POST /users/{id}/body-scan/confirm (after a `?commit=false` draft).
    `body_photo_url`: the draft's url (must be one of this server's /static/uploads/ photos).
    `profile`: the draft's body_profile as reviewed, edits applied (height_cm, weight_kg, chest_in, waist_in,
    hip_in, inseam_in, build, fit, shoe_us, usual_sizes; source/full_body/note/scanned_at pass through).
    `edited`: the profile fields the user changed; they are saved as `manual` (typed) and win over later
    scans. Fields not listed are scan values, so earlier typed values keep winning over them."""
    body_photo_url: str
    profile: dict = {}
    edited: list[str] = []


_SCAN_PASS = {"source", "full_body", "note", "scanned_at", "build", "fit", "shoe_us", "usual_sizes", "scan_photos",
              "confidence", "presenting"}
_SCAN_NUMS = {"height_cm": (120.0, 230.0), "weight_kg": (30.0, 250.0), "shoe_us": (3.0, 18.0)}


@router.post("/users/{user_id}/body-scan/confirm")
def body_scan_confirm(user_id: str, req: BodyScanConfirm):
    """Saves a reviewed draft scan: sets body_photo_url (try-on photo) and merges `profile` into the user's
    body_profile. Fields in `edited` are stored as typed (`manual`, they win); the rest merge like a scan
    (earlier typed values stay). 422 for a photo URL that isn't one of ours or an impossible number.
    Returns {body_photo_url, body_profile, committed: true}."""
    from ..static_urls import local_static_path
    from .body_scan import BUILDS, RANGES, apply_manual, merge_scan

    path = local_static_path(req.body_photo_url, DATA_DIR)
    if not path or path.parent.name != "uploads":
        raise HTTPException(422, "body_photo_url must be a photo uploaded to this server (/static/uploads/)")
    limits = {**RANGES, **_SCAN_NUMS}
    scanned: dict = {}
    for key, value in req.profile.items():
        if key in limits:
            if value is None:
                scanned[key] = None
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                raise HTTPException(422, f"{key} must be a number")
            lo, hi = limits[key]
            if not lo <= num <= hi:
                raise HTTPException(422, f"{key} must be between {lo:g} and {hi:g}")
            scanned[key] = num
        elif key in _SCAN_PASS:
            scanned[key] = value
    if scanned.get("build") is not None and scanned["build"] not in BUILDS:
        raise HTTPException(422, "build must be one of " + ", ".join(sorted(BUILDS)))
    if scanned.get("fit") is not None and scanned["fit"] not in {"slim", "regular", "oversized"}:
        raise HTTPException(422, "fit must be slim, regular or oversized")
    edited = [f for f in req.edited if f in scanned]
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    profile = merge_scan(user.get("body_profile"), {k: v for k, v in scanned.items() if k not in edited})
    if edited:
        profile = apply_manual(profile, {f: scanned[f] for f in edited})
    user["body_photo_url"] = req.body_photo_url
    user["body_profile"] = profile
    store.put("users", user_id, user)
    return {"body_photo_url": req.body_photo_url, "body_profile": profile, "committed": True}


@router.post("/onboarding/photos")
async def onboarding_photos(user_id: str = Form(...), height_cm: float = Form(...),
                            weight_kg: Optional[float] = Form(None), style_hint: Optional[str] = Form(None),
                            files: list[UploadFile] = File(...)):
    """Photo onboarding: 1-8 photos (outfits, flat lays, mirror selfies) + height -> closet digitized
    (duplicates skipped), body scanned from the best full-body photo (that photo becomes the try-on photo),
    style inferred from the garments and saved as style_text / style_tags (onboarded=true), feed warmed in
    the background. One photo that isn't clothing is skipped, not an error; 502 only if tagging failed
    for every photo."""
    from ..static_urls import local_static_path
    from .body_scan import HEIGHT_CM, WEIGHT_KG, merge_scan
    from .digitize import upright_jpeg
    from .photo_onboarding import MAX_PHOTOS, digitize_batch, infer_style, save_style, scan_best, warm_feed

    if not HEIGHT_CM[0] <= height_cm <= HEIGHT_CM[1]:
        raise HTTPException(422, "height_cm must be between 120 and 230")
    if weight_kg is not None and not WEIGHT_KG[0] <= weight_kg <= WEIGHT_KG[1]:
        raise HTTPException(422, "weight_kg must be between 30 and 250")
    files = [f for f in files if f.filename or f.size]
    if not files:
        raise HTTPException(422, "send at least one photo in `files`")
    if len(files) > MAX_PHOTOS:
        raise HTTPException(422, f"at most {MAX_PHOTOS} photos")
    photos: list[tuple[str, Path | None]] = []
    for f in files:  # 415 / 413 from _save_upload apply to the whole batch
        url = await _save_upload(f)
        path = local_static_path(url, DATA_DIR)
        upright = upright_jpeg(path) if path else None
        if upright:
            url, path = url.rsplit("/", 1)[0] + "/" + upright.name, upright
        photos.append((url, path))

    added, skipped, failed = digitize_batch(user_id, photos)
    if failed == len(photos):
        raise _ai_down("wardrobe scan", RuntimeError(f"tagging failed for all {failed} photos"))

    profile, body_url, _scan_skipped = scan_best(photos, height_cm, weight_kg)
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    user["body_profile"] = merge_scan(user.get("body_profile"), profile)
    if body_url:
        user["body_photo_url"] = body_url
    # store department from how the person presents in the full-body photo, only if they never chose one
    # ("both" is the default). Unisex items pass Nabil's filter either way.
    presenting = user["body_profile"].get("presenting")
    if presenting in ("men", "women") and user.get("shop_for", "both") == "both":
        user["shop_for"] = presenting
    store.put("users", user_id, user)

    # style from what was just digitized; if every garment was already in the closet, from the closet
    garments = [i.model_dump() for i in added] or store.list("closet_items", user_id=user_id)
    style = infer_style(garments, style_hint)
    user = save_style(user_id, style)
    warm_feed(user_id)
    return {"closet_added": added, "closet_skipped_duplicates": skipped, "body_profile": user["body_profile"],
            "body_photo_url": user.get("body_photo_url"), "shop_for": user.get("shop_for", "both"),
            "style": style, "user": user}


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
                         waist_in=req.waist_in or scan.get("waist_in"),
                         chest_in=req.chest_in or scan.get("chest_in"), hip_in=req.hip_in or scan.get("hip_in"),
                         inseam_in=req.inseam_in or scan.get("inseam_in"), usual_size=usual)
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
    """Fit Score v2 badge: {score 0-100, verdict "68 as streetwear: ...", notes, breakdown (v1 keys), criteria
    [{name, score_10, note}], style_scores {style: 0-100}, primary_style, raw_score, source}. Calibrated rubric,
    rules only unless `photo_url` is given with AI on (one cached Claude vision critique, blended 50/50).
    Send a Fit Check post's `tagged` as `items` (+ its `photo_url`), or ids for a complete-the-look / closet outfit.
    `target_style` scores the outfit as that style; `occasion` adds the occasion criterion."""
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
    return score_outfit(items, occasion=req.occasion, target_style=req.target_style, photo_url=req.photo_url)



# ---------- AI Fit Creator ----------

@router.post("/fits/create")
def fits_create(req: FitCreateRequest, tryon: bool = False):
    """Full outfits for the user's body (body scan): closet pieces + in-stock catalog pieces in their size.
    `?tryon=true` also renders each fit on the user's body photo (slow); otherwise `try_on` is null and the app
    lazy-loads it with POST /fits/{id}/try-on. Cached 1 h per (user, closet, occasion, must_include, budget)."""
    from .fit_creator import NoFits, create_fits

    try:
        return create_fits(req.user_id, req.count, req.occasion, req.must_include, req.budget_usd, tryon=tryon)
    except NoFits as e:
        raise _ai_down("fit creator", e)


@router.get("/fits/{fit_id}")
def fit_get(fit_id: str, user_id: str):
    """One cached fit (404 once it expires, after 1 h)."""
    from .fit_creator import get_fit

    fit = get_fit(fit_id, user_id)
    if fit is None:
        raise HTTPException(404, "unknown or expired fit")
    return fit


@router.post("/fits/{fit_id}/try-on")
def fit_try_on_route(fit_id: str, user_id: str):
    """Try-on image for a fit: {image_url, mode "ai"|"collage"}. Same generator as POST /tryon."""
    from .fit_creator import fit_try_on, get_fit

    if get_fit(fit_id, user_id) is None:
        raise HTTPException(404, "unknown or expired fit")
    out = fit_try_on(fit_id, user_id)
    if out is None:
        raise _ai_down("try-on", RuntimeError("no image"))
    return out


@router.post("/fits/{fit_id}/cart")
def fit_cart_route(fit_id: str, user_id: str):
    """Add every catalog piece of the fit to the cart at your_size; returns the cart like POST /cart/{user}/items."""
    from .fit_creator import fit_to_cart

    cart = fit_to_cart(fit_id, user_id)
    if cart is None:
        raise HTTPException(404, "unknown or expired fit")
    return cart
