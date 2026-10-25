"""Merge a user's duplicate closet PIECES (the same earbuds / shirt digitized from several outfit photos).

    python -m scripts.dedupe_pieces u_adam --dry-run   # list what would merge
    python -m scripts.dedupe_pieces u_adam             # merge

Match = app.ai.colors.find_duplicate (same category + colour + pattern, label words / canonical noun agree).
Keeps the copy whose display image is a generated clean shot (else the newest), unions `worn_in`, re-points
`outfits.closet_item_ids` and Inspo tags (`fitcheck_posts.tagged[].closet_item_id`), deletes the rest.
"""
from __future__ import annotations

import argparse

from app.ai.colors import find_duplicate
from app.ai.service import store


def _score(item: dict) -> tuple[int, float]:
    url = str(item.get("display_image_url") or "")
    clean = 1 if url.endswith("-clean.png") else 0
    return clean, float(item.get("created_at") or item.get("at") or 0) if isinstance(
        item.get("created_at") or item.get("at"), (int, float)) else 0.0


def plan(user_id: str) -> list[dict]:
    items = [i for i in store.list("closet_items") if i.get("user_id") == user_id]
    items.sort(key=_score, reverse=True)  # best first, so the first of a group is the keeper
    kept: list[dict] = []
    merges: list[dict] = []
    for it in items:
        dup = find_duplicate(it, kept)
        if dup:
            merges.append({"drop": it["id"], "keep": dup, "label": it.get("label"),
                           "keep_label": next(k.get("label") for k in kept if k["id"] == dup)})
        else:
            kept.append(it)
    return merges


def apply(user_id: str, merges: list[dict]) -> None:
    remap = {m["drop"]: m["keep"] for m in merges}
    for m in merges:
        drop, keep = store.get("closet_items", m["drop"]), store.get("closet_items", m["keep"])
        if not drop or not keep:
            continue
        worn = list(keep.get("worn_in") or [])
        seen = {(w.get("photo_url"), tuple(w.get("box") or [])) for w in worn if isinstance(w, dict)}
        for w in drop.get("worn_in") or []:
            if isinstance(w, dict) and (w.get("photo_url"), tuple(w.get("box") or [])) not in seen:
                worn.append(w)
        keep["worn_in"] = worn
        for k in ("brand", "product_id", "catalog_image_url"):
            if not keep.get(k) and drop.get(k):
                keep[k] = drop[k]
        store.put("closet_items", keep["id"], keep)
        store.delete("closet_items", drop["id"])
    for o in store.list("outfits"):
        if o.get("user_id") != user_id:
            continue
        ids = [remap.get(i, i) for i in o.get("closet_item_ids") or []]
        dedup = list(dict.fromkeys(ids))
        if dedup != (o.get("closet_item_ids") or []):
            o["closet_item_ids"] = dedup
            store.put("outfits", o["id"], o)
    for p in store.list("fitcheck_posts"):
        changed = False
        for t in p.get("tagged") or []:
            if isinstance(t, dict) and t.get("closet_item_id") in remap:
                t["closet_item_id"] = remap[t["closet_item_id"]]
                changed = True
        if changed:
            store.put("fitcheck_posts", p["id"], p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("user_id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    merges = plan(args.user_id)
    verb = "would merge" if args.dry_run else "merged"
    for m in merges:
        print(f"{verb} {m['drop']} ({m['label']}) -> {m['keep']} ({m['keep_label']})")
    if not args.dry_run:
        apply(args.user_id, merges)
    print(f"{len(merges)} duplicate piece(s) {verb} for {args.user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
