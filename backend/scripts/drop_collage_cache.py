"""One-off: drop old collage/outfit-board try-on cache entries (they are a miss now and never shown).
    python -m scripts.drop_collage_cache
"""
from app.store import store


def main() -> None:
    docs = store._cached("tryon_cache")
    keys = [k for k, v in docs.items() if isinstance(v, dict) and v.get("mode") == "collage"]
    for k in keys:
        store.delete("tryon_cache", k)
    print(f"dropped {len(keys)} collage entries, {len(store._cached('tryon_cache'))} try-ons left")


if __name__ == "__main__":
    main()
