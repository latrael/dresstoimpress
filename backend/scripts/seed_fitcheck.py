"""Seed 3 Fit Check posts from u_adam / u_nabil / u_ryan (friends of u_demo) so the demo feed isn't empty.
Tags point at real product ids in the store (ingested ones first) and copy category/color/pattern/
style_tags/brand from the product, as /ai/tag-fit would. Safe to re-run (fixed post ids).

    python -m scripts.seed_fitcheck
Swap the placeholder photos for real outfit pics before the demo.
"""
from datetime import datetime, timedelta, timezone

from app.store import store

IMG = "https://picsum.photos/seed/{}/600/800"
CREW = {"u_adam": "Adam", "u_nabil": "Nabil", "u_ryan": "Ryan"}
POSTS = [  # (post id, author, caption, categories to tag, hours ago)
    ("fc_seed_1", "u_adam", "first day fit, too much denim?", ["bottom", "top"], 1),
    ("fc_seed_2", "u_nabil", "hackathon uniform", ["outerwear", "bottom"], 3),
    ("fc_seed_3", "u_ryan", "thrifted most of this lol", ["top", "shoes", "bottom"], 6),
]

products = store.list("products")
products.sort(key=lambda p: (p.get("source") != "ingest", not p.get("in_stock", True), p["id"]))
by_cat: dict[str, list[dict]] = {}
for p in products:
    by_cat.setdefault(p.get("category", ""), []).append(p)
if not products:
    raise SystemExit("no products in the store; run scripts.seed_demo or the ingest first")

for uid, name in CREW.items():
    user = store.get("users", uid) or {"id": uid, "display_name": name}
    user["friends"] = sorted(set(user.get("friends") or []) | {"u_demo"} | (set(CREW) - {uid}))
    store.put("users", uid, user)

now = datetime.now(timezone.utc)
for i, (pid, uid, caption, cats, hours) in enumerate(POSTS):
    tagged = []
    for cat in cats:
        pool = by_cat.get(cat) or products
        p = pool[i % len(pool)]
        if any(t["product_id"] == p["id"] for t in tagged):
            continue
        tagged.append({"label": " ".join(p["name"].split()[:5]).lower(), "retailer": p.get("retailer"),
                       "product_id": p["id"], "closet_item_id": None, "category": p.get("category"),
                       "color": (p.get("colors") or [None])[0], "pattern": p.get("pattern"),
                       "style_tags": p.get("style_tags") or [], "brand": p.get("brand")})
    old = store.get("fitcheck_posts", pid) or {}
    store.put("fitcheck_posts", pid, {
        "id": pid, "user_id": uid, "photo_url": IMG.format(pid), "caption": caption, "tagged": tagged,
        "created_at": (now - timedelta(hours=hours)).isoformat(), "likes": old.get("likes", []),
        "comments": old.get("comments", []), "visibility": "friends"})
    print(f"{pid} by {uid}: {[t['product_id'] for t in tagged]}")
