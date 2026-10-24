"""Style memory: what this user liked and discarded, fed into the pairing prompt.

With MOSS_PROJECT_ID + MOSS_PROJECT_KEY set, every swipe is indexed in Moss
(one index per user) and pairing retrieves the swipes most relevant to the
user's style. Without them, or if Moss errors, it falls back to recent swipes
from the store. Either way the prompt gets the same "Liked / Discarded" text.

Nabil: call `record_swipe(user_id, product, action)` from /swipe.
"""
from __future__ import annotations

import asyncio
import logging
import os

from .compat import get_product, list_products
from ..store import store

log = logging.getLogger(__name__)
LIKED = {"cart", "wishlist", "share"}


def _moss_enabled() -> bool:
    return bool(os.getenv("MOSS_PROJECT_ID") and os.getenv("MOSS_PROJECT_KEY"))


def _index(user_id: str) -> str:
    return f"style-{user_id}".lower().replace("_", "-")


def _describe(product: dict) -> str:
    tags = ", ".join(product.get("style_tags", []))
    colors = ", ".join(product.get("colors", []))
    return (f'{product["name"]} by {product["brand"]}, {product["category"]}'
            f'{", " + colors if colors else ""}{", style " + tags if tags else ""}')


def _run(coro):
    """Run a Moss coroutine from sync code (FastAPI runs sync routes in a threadpool)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(asyncio.run, coro).result()


def _client():
    from moss import MossClient

    return MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])


async def _moss_add(user_id: str, doc: dict) -> None:
    client = _client()
    name = _index(user_id)
    try:
        await client.add_docs(name, [doc])
    except Exception:
        await client.create_index(name, [doc])  # first swipe for this user


async def _moss_query(user_id: str, text: str, k: int):
    from moss import QueryOptions

    client = _client()
    name = _index(user_id)
    await client.load_index(name)
    res = await client.query(name, text, QueryOptions(top_k=k, alpha=0.7))
    return res.docs


def record_swipe(user_id: str, product: dict, action: str) -> None:
    """Index one swipe in Moss. Never raises — memory is best-effort."""
    if not _moss_enabled():
        return
    from .compat import as_product

    product = as_product(product)
    doc = {
        "id": f'{product["id"]}-{action}',
        "text": _describe(product),
        "metadata": {"action": action, "product_id": product["id"]},
    }
    try:
        _run(_moss_add(user_id, doc))
    except Exception as e:  # noqa: BLE001
        log.warning("moss add failed: %s", e)


def _from_store(user_id: str, n: int = 8) -> tuple[list[str], list[str]]:
    liked, discarded = [], []
    for s in reversed(store.list("swipes", user_id=user_id)):
        p = get_product(s["product_id"])
        if not p:
            continue
        bucket = liked if s.get("action") in LIKED else discarded if s.get("action") == "discard" else None
        if bucket is not None and len(bucket) < n:
            bucket.append(_describe(p))
    return liked, discarded


def _from_moss(user_id: str, query: str, n: int = 8) -> tuple[list[str], list[str]]:
    docs = _run(_moss_query(user_id, query, n * 2))
    liked, discarded = [], []
    for d in docs:
        action = (getattr(d, "metadata", None) or {}).get("action")
        bucket = liked if action in LIKED else discarded if action == "discard" else None
        if bucket is not None and len(bucket) < n:
            bucket.append(d.text)
    return liked, discarded


def style_memory(user_id: str, query: str = "") -> str:
    """Text block for the pairing prompt, or "" when there's no history."""
    liked = discarded = None
    if _moss_enabled():
        try:
            liked, discarded = _from_moss(user_id, query or "clothes this person likes")
        except Exception as e:  # noqa: BLE001
            log.warning("moss query failed, using store: %s", e)
    if liked is None:
        liked, discarded = _from_store(user_id)
    if not liked and not discarded:
        return ""
    return f"Liked: {'; '.join(liked) or 'none'}\nDiscarded: {'; '.join(discarded) or 'none'}"
