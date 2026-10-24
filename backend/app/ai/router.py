from fastapi import APIRouter, HTTPException

from ..models import ClosetItem, PairRequest, PairResult, TagRequest, TryOnRequest, TryOnResponse
from . import service
from .llm import BadModelOutput

router = APIRouter(tags=["ai"])


@router.post("/closet/tag", response_model=ClosetItem)
def closet_tag(req: TagRequest):
    try:
        return service.tag_closet_item(req.user_id, req.image_url)
    except service.NotClothing:
        raise HTTPException(422, "not_clothing")
    except BadModelOutput as e:
        raise HTTPException(502, f"tagger failed: {e}")


@router.post("/tryon", response_model=TryOnResponse)
def tryon(req: TryOnRequest):
    try:
        url, cached = service.try_on(req.user_id, req.product_ids, req.closet_item_ids)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except BadModelOutput as e:
        raise HTTPException(502, f"try-on failed: {e}")
    return TryOnResponse(image_url=url, cached=cached)


@router.post("/pair", response_model=list[PairResult])
def pair(req: PairRequest):
    return service.pair(req.user_id, req.candidate_product_ids)
