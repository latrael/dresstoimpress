"""Label every catalog photo (product / model / detail / other) and set each product's hero photo (sprint-4 §10.1).

Claude Haiku sees one numbered contact sheet per product (≤ 6 thumbnails) and labels each photo. Labels are cached
per photo in seed/image_kinds.json (re-runs and re-ingests cost nothing), then applied to the snapshot
(seed/products.json): images[].kind + hero_image_url. ~$0.0001 per product.

    python -m scripts.classify_images --limit 20          # dry run: label 20 products, print them, write nothing
    python -m scripts.classify_images --yes --max-usd 1   # label everything not cached yet, write cache + snapshot
    python -m scripts.classify_images --apply-only        # re-apply the cached labels to the snapshot (no AI)
Then commit seed/image_kinds.json + seed/products.json; the server picks it up with scripts.load_products.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.commerce import image_kinds as ik
from scripts.load_products import SEED

THUMB = 256
MAX_PHOTOS = 6
PROMPT = """This contact sheet shows {n} photos from one clothing product listing ({name}), numbered 1 to {n}.
Label each photo:
- "product": the garment alone with all of it visible (packshot, flat lay, on a hanger, ghost mannequin), no person
- "model": a person is wearing it (even if only legs/torso are visible)
- "detail": a close-up where the whole garment is not visible (fabric, logo, collar)
- "other": a size chart, text graphic, drawing or anything else
Reply with JSON only: {{"kinds": [<{n} labels in photo order>]}}"""


def thumb_url(url: str) -> str:
    base = ik.url_key(url)
    if "cdn.shopify.com" in url:
        return base + "?width=400"
    if "image.hm.com" in url:
        return base + "?imwidth=396"
    return url


def contact_sheet(urls: list[str], client) -> bytes:
    """Thumbnails side by side, each numbered, as one JPEG."""
    from PIL import Image, ImageDraw

    tiles = []
    for u in urls:
        try:
            im = Image.open(io.BytesIO(client.get(thumb_url(u)).raise_for_status().content)).convert("RGB")
        except Exception:  # noqa: BLE001 - a dead photo becomes a grey tile; Claude labels it "other"
            im = Image.new("RGB", (THUMB, THUMB), (200, 200, 200))
        im.thumbnail((THUMB, THUMB))
        tiles.append(im)
    sheet = Image.new("RGB", (THUMB * len(tiles) + 8 * (len(tiles) - 1), THUMB), "white")
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(tiles):
        x = i * (THUMB + 8)
        sheet.paste(im, (x + (THUMB - im.width) // 2, (THUMB - im.height) // 2))
        d.rectangle([x, 0, x + 30, 30], fill="black")
        d.text((x + 10, 8), str(i + 1), fill="white")
    out = io.BytesIO()
    sheet.save(out, "JPEG", quality=80)
    return out.getvalue()


class Labeler:
    def __init__(self, max_usd: float):
        from anthropic import Anthropic
        import httpx

        from app.ai.llm import CLAUDE_TAG_MODEL, PRICES

        self.ai, self.http, self.model = Anthropic(), httpx.Client(timeout=30, follow_redirects=True), CLAUDE_TAG_MODEL
        self.pin, self.pout = PRICES.get(self.model, PRICES["claude-sonnet-5-5"])
        self.max_usd, self.usd, self.lock = max_usd, 0.0, threading.Lock()

    def label(self, p: dict, urls: list[str]) -> list[str] | None:
        from app.ai.llm import extract_json

        if self.usd >= self.max_usd:
            return None
        sheet = base64.b64encode(contact_sheet(urls, self.http)).decode()
        msg = self.ai.messages.create(
            model=self.model, max_tokens=120, thinking={"type": "disabled"},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": sheet}},
                {"type": "text", "text": PROMPT.format(n=len(urls), name=p.get("name", "")[:80])}]}])
        with self.lock:
            self.usd += msg.usage.input_tokens / 1e6 * self.pin + msg.usage.output_tokens / 1e6 * self.pout
        try:
            kinds = extract_json("".join(b.text for b in msg.content if b.type == "text"))["kinds"]
        except Exception:  # noqa: BLE001
            return None
        return kinds if len(kinds) == len(urls) and all(k in ik.KINDS for k in kinds) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yes", action="store_true", help="write the cache and the snapshot (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="only this many unlabelled products")
    ap.add_argument("--max-usd", type=float, default=1.0, help="stop calling Claude past this estimated spend")
    ap.add_argument("--apply-only", action="store_true", help="no AI: apply the cached labels to the snapshot")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--retailer", default="", help="only this store (spot checks)")
    a = ap.parse_args(argv)

    products = json.loads(SEED.read_text())
    cache = ik.load_cache()
    if not a.apply_only:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set (load backend/.env first)", file=sys.stderr)
            return 1
        todo = [(p, ik.gallery_urls(p)[:MAX_PHOTOS]) for p in products]
        todo = [(p, urls) for p, urls in todo if urls and any(ik.url_key(u) not in cache for u in urls)
                and (not a.retailer or p.get("retailer") == a.retailer)]
        todo = todo[:a.limit] if a.limit else todo
        print(f"{len(todo)} products to label (≤{MAX_PHOTOS} photos each), cap ${a.max_usd:.2f}")
        lab, done, failed = Labeler(a.max_usd), 0, 0
        with ThreadPoolExecutor(a.workers) as ex:
            for (p, urls), kinds in zip(todo, ex.map(lambda t: lab.label(*t), todo)):
                if kinds is None:
                    failed += 1
                    continue
                done += 1
                cache.update({ik.url_key(u): ik.fixed_kind(u, k) for u, k in zip(urls, kinds)})
                if not a.yes:
                    print(f"  {p['id']:40} {' '.join(kinds)}")
        print(f"labelled {done}, skipped/failed {failed}, est ${lab.usd:.4f}")
    if not a.yes and not a.apply_only:
        print("Dry run: nothing written. Re-run with --yes to save.")
        return 0
    if not a.apply_only:
        ik.CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True) + "\n")
    products = [ik.apply(p, cache) for p in products]
    SEED.write_text(json.dumps(products, indent=1, ensure_ascii=False) + "\n")
    heroes = sum(1 for p in products if p.get("hero_image_url"))
    print(f"snapshot: {heroes}/{len(products)} products have a product-only hero photo -> {SEED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
