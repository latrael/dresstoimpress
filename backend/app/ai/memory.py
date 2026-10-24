"""Style memory: liked/discarded history fed into the pairing prompt.

Today this reads the `swipes` collection directly. Moss (sponsor track) slots in
here: index closet + swipes in Moss and replace `_recent` with a Moss retrieval
call — the Moss Starter Pack on the Live Site has the SDK calls.
"""
from __future__ import annotations

from ..store import store


def _recent(user_id: str, action: str, n: int = 8) -> list[str]:
    names = []
    for s in reversed(store.list("swipes", user_id=user_id, action=action)):
        p = store.get("products", s["product_id"])
        if p:
            names.append(f'{p["name"]} ({p["brand"]})')
        if len(names) >= n:
            break
    return names


def style_memory(user_id: str) -> str:
    liked = _recent(user_id, "cart") + _recent(user_id, "wishlist")
    discarded = _recent(user_id, "discard")
    if not liked and not discarded:
        return ""
    return f"Liked: {'; '.join(liked) or 'none'}\nDiscarded: {'; '.join(discarded) or 'none'}"
