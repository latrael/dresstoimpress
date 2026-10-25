import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

os.environ["MOCK_AI"] = "1"

BACKEND = Path(__file__).resolve().parent.parent
SEED = BACKEND / "seed" / "products.json"
SNAPSHOT = json.loads(SEED.read_text())
# load/replace semantics run on a slice of the real snapshot: the JSON store rewrites its file on every put,
# so loading all of a 2,500-product snapshot takes ~30 s per load. The full file is checked without a store.
SAMPLE = SNAPSHOT[:40]


@pytest.fixture
def store(tmp_path):
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=BACKEND, check=True,
                   env={**os.environ, "DATA_DIR": str(tmp_path)}, capture_output=True)
    from app.store import JsonStore
    return JsonStore(tmp_path)  # fresh store per test; the app's global store is untouched


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample_products.json"
    path.write_text(json.dumps(SAMPLE, indent=1, ensure_ascii=False) + "\n")
    return path


class MemStore:
    """Just enough store for export(): list() with a where filter."""

    def __init__(self, docs):
        self.docs = docs

    def list(self, collection, **where):
        return [d for d in self.docs if all(d.get(k) == v for k, v in where.items())]


def test_snapshot_valid_and_sorted():
    from app.models import Product
    assert len(SNAPSHOT) > len(SAMPLE)
    assert [p["id"] for p in SNAPSHOT] == sorted({p["id"] for p in SNAPSHOT})
    assert all(Product.model_validate(p).source == "ingest" for p in SNAPSHOT)
    assert {"hm", "uniqlo"} <= set(Counter(p["retailer"] for p in SNAPSHOT))


def test_load_drops_seed_demo_and_is_idempotent(store, sample):
    from scripts.load_products import load
    assert len(store.list("products", source="seed")) == 5
    load(store, sample)
    load(store, sample)
    assert len(store.list("products")) == len(SAMPLE)
    assert not store.list("products", source="seed")
    assert store.get("users", "u_demo")  # other collections untouched


def test_keep_seed_demo(store, sample):
    from scripts.load_products import load
    load(store, sample, keep_seed_demo=True)
    assert len(store.list("products")) == len(SAMPLE) + 5


def test_replace_drops_stale_ingest(store, sample):
    from scripts.load_products import load
    stale = {**SNAPSHOT[0], "id": "hm:stale:black"}
    store.put("products", stale["id"], stale)
    load(store, sample)
    assert store.get("products", "hm:stale:black")  # upsert keeps it
    load(store, sample, replace=True)
    assert store.get("products", "hm:stale:black") is None
    assert len(store.list("products", source="ingest")) == len(SAMPLE)


def test_export_roundtrip(store, sample, tmp_path):
    from scripts.export_products import export
    from scripts.load_products import load
    load(store, sample)
    out = tmp_path / "out.json"
    export(store, out)
    assert out.read_text() == sample.read_text()


def test_committed_snapshot_is_export_output(tmp_path):
    """The whole committed file is exactly what export_products writes (sorted, same formatting)."""
    from scripts.export_products import export
    out = tmp_path / "out.json"
    export(MemStore(list(reversed(SNAPSHOT)) + [{"id": "seed1", "source": "seed"}]), out)
    assert out.read_text() == SEED.read_text()
