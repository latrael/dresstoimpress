"""End-to-end smoke test against a running backend: the full demo journey.

    python -m scripts.smoke_e2e                      # http://localhost:8000, user u_demo
    python -m scripts.smoke_e2e --base https://xyz.ngrok.app

Run before merging staging -> main and before judging. Exits 1 if any step fails.
Spends a little real AI (one pairing call, cached try-ons); check GET /ai/usage.
"""
import argparse
import os
import sys
import time

import httpx

PASS, FAIL = "PASS", "FAIL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--user", default="u_demo")
    ap.add_argument("--key", default=os.getenv("API_SHARED_KEY", ""), help="X-DTI-Key (default: $API_SHARED_KEY)")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base.rstrip("/"), timeout=90, headers={"X-DTI-Key": a.key} if a.key else {})
    results: list[tuple[str, str, str]] = []

    def step(name, fn):
        t = time.time()
        try:
            note = fn() or ""
            results.append((PASS, name, f"{note} ({time.time() - t:.1f}s)"))
        except Exception as e:  # noqa: BLE001
            results.append((FAIL, name, str(e)[:160]))

    state: dict = {}

    def health():
        assert c.get("/health").json() == {"ok": True}

    def feed():
        r = c.get("/feed", params={"user_id": a.user, "limit": 8})
        r.raise_for_status()
        cards = r.json()
        assert cards, "empty feed"
        top = cards[0]
        for f in ("id", "name", "price_usd", "image_url", "sizes", "retailer"):
            assert f in top, f"card missing {f}"
        state["cards"] = cards
        with_reason = sum(1 for x in cards if x.get("reason"))
        return f"{len(cards)} cards, {with_reason} with reasons; top: {top['name'][:30]} — {top.get('reason', '')[:45]}"

    def size():
        p = next(x for x in state["cards"] if any(s.get("in_stock") for s in x["sizes"]))
        state["product"] = p
        r = c.post("/size", json={"product_id": p["id"], "height_cm": 168, "weight_kg": 60})
        r.raise_for_status()
        rec = r.json()
        in_stock = [s["name"] for s in p["sizes"] if s.get("in_stock")]
        state["size"] = rec["size"] if rec["size"] in in_stock else in_stock[0]
        return f"{p['name'][:30]} -> {rec['size']} ({rec['confidence']})"

    def tryon():
        r = c.post("/tryon", json={"user_id": a.user, "product_ids": [state["product"]["id"]]})
        r.raise_for_status()
        j = r.json()
        assert c.get(j["image_url"].replace(a.base.rstrip("/"), "")).status_code == 200, "image not served"
        return f"mode={j['mode']} cached={j['cached']}"

    def complete():
        r = c.post("/complete-look", json={"user_id": a.user, "product_id": state["product"]["id"]})
        r.raise_for_status()
        j = r.json()
        return f"{len(j['items'])} pieces, missing={j['missing']}, new total ${j['new_items_total_usd']}"

    def swipe():
        r = c.post("/swipe", json={"user_id": a.user, "product_id": state["product"]["id"],
                                   "action": "like", "size": state["size"]})
        r.raise_for_status()
        assert r.json().get("in_cart"), r.json()
        if len(state["cards"]) > 1:
            c.post("/swipe", json={"user_id": a.user, "product_id": state["cards"][-1]["id"], "action": "discard"})

    def cart():
        r = c.get(f"/cart/{a.user}")
        r.raise_for_status()
        j = r.json()
        assert j["count"] >= 1
        return f"{j['count']} items in {len(j['groups'])} store group(s), total ${j['total_usd']}"

    def checkout():
        r = c.post(f"/checkout/{a.user}")
        r.raise_for_status()
        j = r.json()
        return f"{len(j['purchases'])} purchase(s), statuses {[p['status'] for p in j['purchases']]}"

    def fitcheck():
        img = "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=700"
        tags = c.post("/ai/tag-fit", json={"image_url": img})
        tags.raise_for_status()
        shop = c.post("/ai/shop-fit", json={"viewer_id": a.user, "photo_url": img})
        shop.raise_for_status()
        return f"{len(tags.json())} items tagged, {len(shop.json())} shoppable"

    def usage():
        u = c.get("/ai/usage").json()
        return f"claude {u['claude_calls']} calls, est ${u['est_usd']:.4f}, gemini images {u['gemini_images']}"

    for name, fn in [("health", health), ("feed (+pairing)", feed), ("size advice", size),
                     ("try-on", tryon), ("complete the look", complete), ("swipe like -> cart", swipe),
                     ("cart grouped by store", cart), ("checkout", checkout),
                     ("fit check tag + shop", fitcheck), ("AI usage", usage)]:
        if name not in ("health", "feed (+pairing)", "fit check tag + shop", "AI usage") and "product" not in state \
                and name != "size advice":
            results.append((FAIL, name, "skipped: no product from feed"))
            continue
        step(name, fn)

    for status, name, note in results:
        print(f"{status}  {name:<24} {note}")
    failed = [r for r in results if r[0] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
