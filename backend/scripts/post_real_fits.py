"""Post real outfit photos to Fit Check as u_adam / u_nabil / u_ryan, then remove the picsum seed posts.

    python -m scripts.post_real_fits photos/                          # http://localhost:8000
    python -m scripts.post_real_fits photos/ --base <tunnel> --key <X-DTI-Key>
    python -m scripts.post_real_fits photos/ --dry-run                # show the plan, post nothing

Photos (.jpg/.jpeg/.png/.webp/.heic, 10 MB max; prefer JPEG, since the AI tagger may not read HEIC) are posted
in filename order, authors taking turns (--users).
Optional captions: a captions.txt in the folder, one line per photo in the same order.
Each post goes through POST /fitcheck (multipart, no tags), so the AI pre-fills the tags;
fix wrong ones with PATCH /fitcheck/{id}/tags. The seed posts fc_seed_1..3 are deleted only
if every photo posted (skip with --keep-seeds). Re-running posts the photos again.
"""
import argparse
import mimetypes
import os
import sys
from pathlib import Path

import httpx

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
SEEDS = {"fc_seed_1": "u_adam", "fc_seed_2": "u_nabil", "fc_seed_3": "u_ryan"}


def plan(folder: Path, users: list[str]) -> list[tuple[Path, str, str]]:
    """[(photo, user_id, caption)] in filename order."""
    photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_EXTS)
    cap_file = folder / "captions.txt"
    captions = cap_file.read_text().splitlines() if cap_file.exists() else []
    return [(p, users[i % len(users)], captions[i].strip() if i < len(captions) else "")
            for i, p in enumerate(photos)]


def run(client: httpx.Client, folder: Path, users: list[str], keep_seeds=False, dry_run=False) -> int:
    jobs = plan(folder, users)
    if not jobs:
        print(f"no photos in {folder}")
        return 1
    failed = 0
    for photo, uid, caption in jobs:
        if dry_run:
            print(f"would post {photo.name} as {uid}: {caption!r}")
            continue
        ctype = mimetypes.guess_type(photo.name)[0] or "image/jpeg"
        with photo.open("rb") as f:
            r = client.post("/fitcheck", data={"user_id": uid, "caption": caption},
                            files={"file": (photo.name, f, ctype)})
        if r.status_code != 200:
            failed += 1
            print(f"FAIL {photo.name} as {uid}: {r.status_code} {r.text[:160]}")
            continue
        post = r.json()
        print(f"posted {photo.name} as {uid}: {post['id']} tags={[t['label'] for t in post['tagged']]}")
    if dry_run or keep_seeds:
        return 1 if failed else 0
    if failed:
        print(f"{failed} photo(s) failed; seed posts kept")
        return 1
    for pid, owner in SEEDS.items():
        r = client.delete(f"/fitcheck/{pid}", params={"user_id": owner})
        print(f"removed seed {pid}" if r.status_code == 200 else f"seed {pid}: {r.status_code} (already gone?)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--key", default=os.getenv("API_SHARED_KEY", ""), help="X-DTI-Key (default: $API_SHARED_KEY)")
    ap.add_argument("--users", default="u_adam,u_nabil,u_ryan", help="comma-separated authors, in turn")
    ap.add_argument("--keep-seeds", action="store_true", help="don't delete fc_seed_1..3")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.folder.is_dir():
        print(f"not a folder: {a.folder}")
        return 1
    client = httpx.Client(base_url=a.base.rstrip("/"), timeout=90,
                          headers={"X-DTI-Key": a.key} if a.key else {})
    return run(client, a.folder, [u.strip() for u in a.users.split(",") if u.strip()], a.keep_seeds, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
