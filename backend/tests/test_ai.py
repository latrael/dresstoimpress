import os
import subprocess
import sys

import pytest

os.environ["MOCK_AI"] = "1"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    backend = os.path.dirname(os.path.dirname(__file__))
    subprocess.run([sys.executable, "-m", "scripts.seed_demo"], cwd=backend, check=True,
                   env={**os.environ})
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_tag(client):
    r = client.post("/closet/tag", json={"user_id": "u_demo", "image_url": "https://x/y.jpg"})
    assert r.status_code == 200
    assert r.json()["category"] in {"top", "bottom", "outerwear", "shoes", "dress", "accessory"}


def test_tryon_caches(client):
    body = {"user_id": "u_demo", "product_ids": ["hm-demo-1"], "closet_item_ids": ["ci_demo_2"]}
    first = client.post("/tryon", json=body).json()
    second = client.post("/tryon", json=body).json()
    assert first["cached"] is False and second["cached"] is True
    assert first["image_url"] == second["image_url"]


def test_tryon_unknown_user(client):
    r = client.post("/tryon", json={"user_id": "nobody", "product_ids": ["hm-demo-1"]})
    assert r.status_code == 400


def test_pair_budget_first(client):
    r = client.post("/pair", json={"user_id": "u_demo", "candidate_product_ids": []})
    ids = [p["product_id"] for p in r.json()]
    assert ids and ids[-1] == "mango-demo-1"  # $130 bomber is over the outerwear budget


def test_extract_json():
    from app.ai.llm import extract_json
    assert extract_json('sure!\n```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert extract_json('here: {"category": "top"} done') == {"category": "top"}
