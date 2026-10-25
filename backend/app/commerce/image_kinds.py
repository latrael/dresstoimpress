"""What each catalog photo shows, and the product's hero photo (sprint-4 §10.1: slide 1 of a Home post).

Labels come from scripts/classify_images (Claude Haiku on a numbered contact sheet) and are cached per photo in
seed/image_kinds.json, keyed by the URL without its query string, so a re-ingest re-applies them for free.
  product: the garment alone and whole (packshot, flat lay, hanger, ghost mannequin)
  model:   worn by a person (stored as images[].kind "retailer_model", as before)
  detail:  a close-up where the whole garment isn't visible
  other:   a size chart, graphic, illustration
hero_image_url = the first `product` photo in gallery order; None when the store only has model shots (the app
then shows image_url).
"""
from __future__ import annotations

import json
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "seed" / "image_kinds.json"
KINDS = ("product", "model", "detail", "other")
STORED_KIND = {"product": "product", "model": "retailer_model", "detail": "detail", "other": "other"}


# filename words a store only uses for photos of a model: they override the AI (tight crops of legs in jeans
# fool it). Princess Polly names its model shots "...-modelinfo-<model>-us2_..."
MODEL_WORDS = ("modelinfo",)


def url_key(url: str) -> str:
    return url.split("?", 1)[0]


def fixed_kind(url: str, kind: str) -> str:
    return "model" if any(w in url_key(url).rsplit("/", 1)[-1].lower() for w in MODEL_WORDS) else kind


def load_cache(path: Path | None = None) -> dict[str, str]:
    try:
        cache = json.loads((path or CACHE).read_text())
    except (OSError, ValueError):
        return {}
    return {u: fixed_kind(u, k) for u, k in cache.items()}


def gallery_urls(p: dict) -> list[str]:
    return [i["url"] for i in p.get("images") or [] if i.get("url")] or ([p["image_url"]] if p.get("image_url") else [])


def apply(p: dict, cache: dict[str, str]) -> dict:
    """`p` with images[].kind from the cache and hero_image_url set; unlabelled photos keep their kind.
    A product with no labelled photo comes back unchanged."""
    if not any(url_key(u) in cache for u in gallery_urls(p)):
        return p
    images = [{**i, "kind": STORED_KIND[cache[url_key(i["url"])]]} if url_key(i.get("url", "")) in cache else i
              for i in p.get("images") or []]
    hero = next((u for u in gallery_urls(p) if cache.get(url_key(u)) == "product"), None)
    out: dict = {}
    for k, v in p.items():  # hero_image_url goes right after images (schema order), so key order stays stable
        if k != "hero_image_url":
            out[k] = images if k == "images" and images else v
        if k == "images":
            out["hero_image_url"] = hero
    out.setdefault("hero_image_url", hero)
    return out
