"""Home as reels (sprint-4 §10): the extra fields a Home post needs, and pre-loading its try-on slide.

Every /feed card also carries:
  hero_image_url  slide 1, the garment alone (scripts.classify_images); image_url when the store has no such shot
  closet_picks    slide 3, ≤ 4 of the user's own closet pieces that go with it: [{id, label, category, image_url}]
  tryon           slide 2, {status: ready | pending | none | needs_photo | unavailable, image_url?, mode?}
POST /feed/{user_id}/tryons starts rendering the try-ons of the next posts in the background; GET polls them.
closet_picks / tryon_status / prefetch_tryons are Adam's (ai.feed_tryon, via ai.service).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai import service
from ..store import store

log = logging.getLogger(__name__)
router = APIRouter(tags=["reels"])
CLOSET_PICKS = 4
MAX_PREFETCH = 5
NO_TRYON = {"status": "none"}


def _picks(user_id: str, p: dict) -> list[dict]:
    try:
        return list(service.closet_picks(user_id, p, k=CLOSET_PICKS))[:CLOSET_PICKS]
    except Exception as e:  # noqa: BLE001 - a post never fails because its closet slide did
        log.warning("closet_picks failed for %s: %s", p.get("id"), e)
        return []


def _tryon(user_id: str, p: dict, picks: list[dict]) -> dict:
    """The try-on of exactly these picks (the ones slide 3 shows)."""
    try:
        return service.tryon_status(user_id, p, picks) or dict(NO_TRYON)
    except Exception as e:  # noqa: BLE001
        log.warning("tryon_status failed for %s: %s", p.get("id"), e)
        return dict(NO_TRYON)


def decorate(user_id: str, cards: list[dict]) -> list[dict]:
    """The /feed cards with hero_image_url, closet_picks and tryon (sprint-4 §10.1)."""
    out = []
    for c in cards:
        picks = _picks(user_id, c)
        out.append({**c, "hero_image_url": c.get("hero_image_url") or c.get("image_url"),
                    "closet_picks": picks, "tryon": _tryon(user_id, c, picks)})
    return out


class Prefetch(BaseModel):
    product_ids: list[str] = Field(..., min_length=1, max_length=MAX_PREFETCH)


def _products(ids) -> list[dict]:
    out = []
    for pid in dict.fromkeys(ids):  # de-dupe, keep order
        p = store.get("products", pid)
        if not p:
            raise HTTPException(404, f"unknown product {pid}")
        out.append(p)
    return out


@router.post("/feed/{user_id}/tryons")
def prefetch(user_id: str, req: Prefetch):
    """Start the try-ons of the next posts (≤ 5) in the background; answers at once with each one's status.
    Idempotent: a cached or already-rendering try-on isn't started again."""
    products = _products(req.product_ids)
    started = service.prefetch_tryons(user_id, products) or {}
    return {p["id"]: started.get(p["id"]) or _tryon(user_id, p, _picks(user_id, p)) for p in products}


@router.get("/feed/{user_id}/tryons")
def tryon_statuses(user_id: str, ids: str):
    """Poll: `ids` = comma-separated product ids (≤ 5) -> {product_id: tryon}, for the same picks as the card."""
    pids = [i for i in ids.split(",") if i][:MAX_PREFETCH]
    if not pids:
        raise HTTPException(422, "ids required")
    return {p["id"]: _tryon(user_id, p, _picks(user_id, p)) for p in _products(pids)}
