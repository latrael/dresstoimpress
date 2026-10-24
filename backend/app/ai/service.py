"""AI pipeline: closet tagging, try-on, pairing."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from ..models import ClosetItem, PairResult, Product
from ..store import DATA_DIR, store
from . import prompts
from .llm import BadModelOutput, claude_json, gemini_image, mock_mode
from .memory import style_memory

TRYON_DIR = DATA_DIR / "tryon"
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "http://localhost:8000")
CATEGORIES = {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}


class NotClothing(Exception):
    pass


# ---------- /closet/tag ----------

def tag_closet_item(user_id: str, image_url: str) -> ClosetItem:
    if mock_mode("ANTHROPIC_API_KEY"):
        raw = {"category": "top", "color": "black", "pattern": "solid",
               "style_tags": ["streetwear"], "formality": 2}
    else:
        raw = claude_json(prompts.TAGGER, image_url=image_url, max_tokens=300)

    if isinstance(raw, dict) and raw.get("error") == "not_clothing":
        raise NotClothing()

    item = ClosetItem(
        id=f"ci_{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        image_url=image_url,
        category=raw.get("category", "top") if raw.get("category") in CATEGORIES else "top",
        color=str(raw.get("color", "unknown")),
        pattern=raw.get("pattern", "other") if raw.get("pattern") in
        {"solid", "striped", "plaid", "graphic", "floral", "other"} else "other",
        style_tags=list(raw.get("style_tags", []))[:5],
        formality=min(5, max(1, int(raw.get("formality", 3)))),
        source="photo",
    )
    store.put("closet_items", item.id, item.model_dump())
    return item


# ---------- /tryon ----------

def _tryon_key(user_id: str, product_ids: list[str], closet_ids: list[str]) -> str:
    raw = user_id + "|" + ",".join(sorted(product_ids)) + "|" + ",".join(sorted(closet_ids))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def try_on(user_id: str, product_ids: list[str], closet_item_ids: list[str]) -> tuple[str, bool]:
    key = _tryon_key(user_id, product_ids, closet_item_ids)
    hit = store.get("tryon_cache", key)
    if hit:
        return hit["image_url"], True

    user = store.get("users", user_id) or {}
    body = user.get("body_photo_url")
    if not body:
        raise ValueError("user has no body_photo_url")

    garments = [p["image_url"] for pid in product_ids if (p := store.get("products", pid))]
    garments += [c["image_url"] for cid in closet_item_ids if (c := store.get("closet_items", cid))]
    if not garments:
        raise ValueError("no garment images found for given ids")

    if mock_mode("GEMINI_API_KEY"):
        url = garments[0]  # placeholder so the UI flow works
    else:
        img = gemini_image(prompts.TRYON, [body, *garments])
        TRYON_DIR.mkdir(parents=True, exist_ok=True)
        (TRYON_DIR / f"{key}.png").write_bytes(img)
        url = f"{PUBLIC_BASE}/static/tryon/{key}.png"

    store.put("tryon_cache", key, {"image_url": url, "user_id": user_id})
    return url, False


# ---------- /pair ----------

def _in_budget(p: dict, ranges: dict) -> bool:
    r = ranges.get(p["category"])
    price = p.get("sale_price_usd") or p["price_usd"]
    return not r or r[0] <= price <= r[1]


def _fallback(cands: list[dict], ranges: dict, k: int) -> list[PairResult]:
    ranked = sorted(cands, key=lambda p: (not _in_budget(p, ranges), p["price_usd"]))
    return [PairResult(product_id=p["id"], score=0.5, reason="fits your style and budget",
                       pairs_with=[]) for p in ranked[:k]]


def pair(user_id: str, candidate_ids: list[str], k: int = 10) -> list[PairResult]:
    user = store.get("users", user_id) or {}
    ranges = user.get("price_ranges", {})
    closet = store.list("closet_items", user_id=user_id)
    swiped = {s["product_id"] for s in store.list("swipes", user_id=user_id)}

    if candidate_ids:
        cands = [p for pid in candidate_ids if (p := store.get("products", pid))]
    else:
        cands = [p for p in store.list("products") if p["id"] not in swiped]
    # keep budget matches first, cap prompt size
    cands = sorted(cands, key=lambda p: not _in_budget(p, ranges))[:50]
    if not cands:
        return []

    if mock_mode("ANTHROPIC_API_KEY") or not closet:
        return _fallback(cands, ranges, k)

    slim_closet = [{k2: c[k2] for k2 in ("id", "category", "color", "pattern", "style_tags")}
                   for c in closet]
    slim_cands = [{"id": p["id"], "name": p["name"], "brand": p["brand"],
                   "category": p["category"], "price_usd": p.get("sale_price_usd") or p["price_usd"],
                   "colors": p.get("colors", []), "style_tags": p.get("style_tags", [])}
                  for p in cands]
    prompt = prompts.PAIR.format(
        style_text=user.get("style_text", "") or "not given",
        price_ranges=json.dumps(ranges),
        closet_json=json.dumps(slim_closet),
        memory=style_memory(user_id),
        products_json=json.dumps(slim_cands),
        k=k,
    )
    try:
        raw = claude_json(prompt, max_tokens=2000)
    except BadModelOutput:
        return _fallback(cands, ranges, k)

    valid_ids = {p["id"] for p in cands}
    closet_ids = {c["id"] for c in closet}
    out: list[PairResult] = []
    for r in raw if isinstance(raw, list) else []:
        if r.get("product_id") not in valid_ids:
            continue  # drop hallucinated ids
        out.append(PairResult(
            product_id=r["product_id"],
            score=min(1.0, max(0.0, float(r.get("score", 0.5)))),
            reason=" ".join(str(r.get("reason", "")).split()[:8]) or "pairs with your closet",
            pairs_with=[c for c in r.get("pairs_with", []) if c in closet_ids],
        ))
    return out[:k] or _fallback(cands, ranges, k)
