"""Set a user's full-body photo for try-on from a local file (the morning photo step, one command).

    python -m scripts.set_body_photo ~/dti-photos/body.jpg            # u_demo
    python -m scripts.set_body_photo ~/dti-photos/body.jpg --user u_adam

Copies the photo into uploads and sets body_photo_url. Try-ons cached for the old photo are not reused
(the cache key includes the body photo). Then warm new ones: python -m scripts.precompute_tryons --limit 10
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.store import store  # noqa: E402
from scripts.demo_photos import save_upload  # noqa: E402


def set_body_photo(path: Path, user_id: str = "u_demo") -> str:
    url = save_upload(path.expanduser())
    user = store.get("users", user_id) or {"id": user_id, "display_name": user_id}
    user["body_photo_url"] = url
    store.put("users", user_id, user)
    return url


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("photo", type=Path)
    ap.add_argument("--user", default="u_demo")
    a = ap.parse_args(argv)
    url = set_body_photo(a.photo, a.user)
    print(f"{a.user} body photo -> {url.rsplit('/', 1)[-1]}. Next: python -m scripts.precompute_tryons --limit 10")


if __name__ == "__main__":
    main()
