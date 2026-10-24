"""Put a demo user back to a clean state before a dry run or the real demo. Safe to re-run.

    python -m scripts.reset_demo                 # u_demo: empty cart, no swipes, no wishlist saves
    python -m scripts.reset_demo --orders        # also clear their order history
    python -m scripts.reset_demo --user u_adam

Keeps: the closet, the user profile (price ranges, style text, body photo), cached try-ons and the
catalog. Clears the feed-ranking cache so the next /feed is ranked fresh (one Claude call).
Works with the JSON store (the shared demo server).
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

from app.store import JsonStore, store  # noqa: E402

PER_USER = ("swipes", "wishlist")  # docs keyed "{user_id}:{product_id}", each with a user_id field


def _ids(collection: str, user_id: str) -> list[str]:
    data = store._load(collection)  # JsonStore internals: {doc_id: doc}
    return [k for k, v in data.items() if isinstance(v, dict) and v.get("user_id") == user_id]


def reset(user_id: str, orders: bool = False) -> dict:
    if not isinstance(store, JsonStore):
        raise SystemExit("reset_demo only supports the JSON store (the shared demo server)")
    counts = {}
    for col in PER_USER + (("orders",) if orders else ()):
        ids = _ids(col, user_id)
        for i in ids:
            store.delete(col, i)
        counts[col] = len(ids)
    cart = store.get("carts", user_id) or {}
    counts["cart_items"] = len(cart.get("items", []))
    store.put("carts", user_id, {"user_id": user_id, "items": []})
    for k in list(store._load("pair_cache")):
        store.delete("pair_cache", k)
    return counts


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default="u_demo")
    ap.add_argument("--orders", action="store_true", help="also clear order history")
    a = ap.parse_args(argv)
    counts = reset(a.user, a.orders)
    print(f"reset {a.user}: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + "; feed cache cleared")
    print("next: python -m scripts.warm_demo  (so the first feed / try-on on stage is instant)")


if __name__ == "__main__":
    main()
