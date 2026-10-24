import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

BACKEND = Path(__file__).resolve().parent.parent
SNAPSHOT = json.loads((BACKEND / "seed" / "products.json").read_text())


@pytest.fixture
def store(tmp_path):
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=BACKEND, check=True,
                   env={**os.environ, "DATA_DIR": str(tmp_path)}, capture_output=True)
    from app.store import JsonStore
    return JsonStore(tmp_path)  # fresh store per test; the app's global store is untouched


def test_snapshot_valid_and_sorted():
    from app.models import Product
    assert [p["id"] for p in SNAPSHOT] == sorted({p["id"] for p in SNAPSHOT})
    assert all(Product.model_validate(p).source == "ingest" for p in SNAPSHOT)
    assert set(Counter(p["retailer"] for p in SNAPSHOT)) == {"hm", "uniqlo"}


def test_load_drops_seed_demo_and_is_idempotent(store):
    from scripts.load_products import load
    assert len(store.list("products", source="seed")) == 5
    load(store)
    load(store)
    assert len(store.list("products")) == len(SNAPSHOT)
    assert not store.list("products", source="seed")
    assert store.get("users", "u_demo")  # other collections untouched


def test_keep_seed_demo(store):
    from scripts.load_products import load
    load(store, keep_seed_demo=True)
    assert len(store.list("products")) == len(SNAPSHOT) + 5


def test_replace_drops_stale_ingest(store):
    from scripts.load_products import load
    stale = {**SNAPSHOT[0], "id": "hm:stale:black"}
    store.put("products", stale["id"], stale)
    load(store)
    assert store.get("products", "hm:stale:black")  # upsert keeps it
    load(store, replace=True)
    assert store.get("products", "hm:stale:black") is None
    assert len(store.list("products", source="ingest")) == len(SNAPSHOT)


def test_export_roundtrip(store, tmp_path):
    from scripts.export_products import export
    from scripts.load_products import load
    load(store)
    out = tmp_path / "out.json"
    export(store, out)
    assert json.loads(out.read_text()) == SNAPSHOT
