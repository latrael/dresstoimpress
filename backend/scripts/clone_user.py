"""Copy one user's setup (profile, body scan + photo, shop_for, stores, closet items) to another user id.
Made for giving Adam his own account after the demo user was set up from his photos.

    python -m scripts.clone_user u_demo u_adam --name "Adam"
    python -m scripts.clone_user u_demo u_adam --name "Adam" --no-closet
"""
from __future__ import annotations

import argparse
import uuid

from dotenv import load_dotenv

load_dotenv()

from app.store import store  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--name", default=None, help="display name for the new user")
    ap.add_argument("--no-closet", action="store_true", help="don't copy closet items")
    a = ap.parse_args()

    src = store.get("users", a.src)
    if not src:
        raise SystemExit(f"no user {a.src}")
    dst = store.get("users", a.dst) or {}
    keep = ["style_text", "style_tags", "price_ranges", "body_photo_url", "body_profile", "shop_for",
            "preferred_stores", "onboarded", "fit", "usual_sizes"]
    for k in keep:
        if k in src:
            dst[k] = src[k]
    dst["id"] = a.dst
    dst["display_name"] = a.name or dst.get("display_name") or a.dst
    store.put("users", a.dst, dst)
    n = 0
    if not a.no_closet:
        have = {c.get("image_url") for c in store.list("closet_items", user_id=a.dst)}
        for c in store.list("closet_items", user_id=a.src):
            if c.get("image_url") in have:
                continue
            item = {**c, "id": f"ci_{uuid.uuid4().hex[:8]}", "user_id": a.dst}
            store.put("closet_items", item["id"], item)
            n += 1
    print(f"{a.dst}: profile copied from {a.src}; closet items added: {n}")


if __name__ == "__main__":
    main()
