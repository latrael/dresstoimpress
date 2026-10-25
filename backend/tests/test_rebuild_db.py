"""scripts.rebuild_db: back up, reset everything but the catalog, reload the snapshot, team accounts."""
import json
import os
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    from app.store import store
    from scripts import rebuild_db
    if not hasattr(store, "root"):
        pytest.skip("JSON store only")
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(store, "root", data)
    monkeypatch.setattr(rebuild_db, "DATA_DIR", data)
    snap = [{"id": "hm:1:blue", "retailer": "hm", "source": "ingest", "name": "Tee", "summary": "A tee."},
            {"id": "kith:2:black", "retailer": "kith", "source": "ingest", "name": "Hoodie"}]
    seed = tmp_path / "products.json"
    seed.write_text(json.dumps(snap))
    monkeypatch.setattr(rebuild_db, "SEED", seed)
    store.put("products", "hm:1:blue", {**snap[0], "price_usd": 1})
    store.put("products", "live:9", {"id": "live:9", "source": "live_search"})
    store.put("users", "u_x", {"id": "u_x"})
    store.put("fitcheck_posts", "fc_1", {"id": "fc_1"})
    store.put("closet_items", "ci_1", {"id": "ci_1"})
    store.put("tag_cache", "t1", {"id": "t1"})
    store.put("nessie", "merchants", {"hm": "m1"})  # real shape: keyed docs, no id field
    store.put("nessie", "accounts", {"u_x": "a1"})
    store.put("mystery", "m", {"id": "m"})
    (data / "uploads").mkdir()
    (data / "uploads" / "body.jpg").write_bytes(b"x")
    return store, rebuild_db, data


def test_dry_run_changes_nothing(env, capsys):
    store, rebuild_db, data = env
    assert rebuild_db.main([]) == 0
    out = capsys.readouterr().out
    assert "Dry run" in out and "'users': 1" in out and "mystery" in out
    assert store.get("users", "u_x") and (data / "uploads" / "body.jpg").exists()
    assert not list(data.parent.glob("data.bak-*"))


def test_rebuild_resets_everything_but_the_catalog(env):
    store, rebuild_db, data = env
    assert rebuild_db.main(["--yes"]) == 0
    [bak] = list(data.parent.glob("data.bak-*"))
    assert json.loads((bak / "users.json").read_text())["u_x"]  # backup taken first
    assert sorted(p["id"] for p in store.list("products")) == ["hm:1:blue", "kith:2:black"]  # exactly the snapshot
    assert store.get("products", "hm:1:blue").get("price_usd") is None  # snapshot copy, not the server's
    assert store.list("fitcheck_posts") == [] and store.list("closet_items") == []  # Inspo starts empty
    assert sorted(u["id"] for u in store.list("users")) == ["u_adam", "u_demo", "u_nabil", "u_ryan"]
    assert store.get("users", "u_x") is None
    assert store.get("tag_cache", "t1")  # catalog AI cache kept
    assert store.get("nessie", "merchants") and store.get("nessie", "accounts") is None
    assert store.get("mystery", "m")  # unknown collections left alone
    assert not (data / "uploads" / "body.jpg").exists() and (data / "uploads").is_dir()


def test_flags(env):
    store, rebuild_db, _ = env
    rebuild_db.main(["--yes", "--drop-ai-cache", "--no-team"])
    assert store.list("tag_cache") == [] and store.list("users") == []
