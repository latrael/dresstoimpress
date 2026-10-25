"""Catalog pipeline: re-ingest keeps paid-for AI fields; Apify runs are async + polled + capped, and a
finished run's dataset can be ingested directly. No network: httpx is faked, MOCK_AI is on."""
import copy
import gzip
import json
import os
from pathlib import Path

import httpx
import pytest

os.environ["MOCK_AI"] = "1"

from app.commerce import ingest  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
HM = json.loads((FIX / "hm_raw.json").read_text())
TOKEN = "apify-secret-token"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    from app.store import store
    if hasattr(store, "root"):
        monkeypatch.setattr(store, "root", Path(tmp_path))  # empty store per test
    return store


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(ingest.time, "sleep", lambda s: None)


# ---------- 1. re-ingest keeps the AI fields ----------

def _fresh(**kw):
    p = {"id": "hm:1:black", "retailer": "hm", "name": "Loose Fit Hoodie", "brand": "H&M", "category": "top",
         "price_usd": 19.99, "colors": ["Black"], "sizes": [{"name": "M", "in_stock": False}], "in_stock": False,
         "image_url": "https://img/new.jpg", "product_url": "https://hm/1", "scraped_at": "2026-10-24T20:00:00+00:00",
         "images": [{"url": "https://img/new.jpg", "kind": "retailer_model"}], "department": "men",
         "source": "ingest", "label": "", "pattern": None, "formality": None, "style_tags": []}
    return {**p, **kw}


TAGGED = {**_fresh(price_usd=29.99, sizes=[{"name": "M", "in_stock": True}], in_stock=True,
                   image_url="https://img/old.jpg", images=[], department=None,
                   scraped_at="2026-10-23T10:00:00+00:00"),
          "label": "black oversized hoodie", "pattern": "solid", "formality": 2, "style_tags": ["streetwear"],
          "summary": "Black oversized hoodie with a streetwear look."}


def test_save_keeps_ai_fields_and_refreshes_the_rest(store):
    store.put("products", TAGGED["id"], TAGGED)
    [saved] = ingest.save([_fresh()])
    got = store.get("products", "hm:1:black")
    assert got == saved
    assert {k: got[k] for k in ingest.AI_FIELDS} == {k: TAGGED[k] for k in ingest.AI_FIELDS}  # summary too
    fresh = _fresh()
    for k in ("price_usd", "sizes", "in_stock", "image_url", "images", "department", "scraped_at"):
        assert got[k] == fresh[k], k


def test_save_new_ai_values_win(store):
    store.put("products", TAGGED["id"], TAGGED)
    ingest.save([_fresh(label="black zip hoodie", style_tags=["athleisure"], formality=1)])
    got = store.get("products", "hm:1:black")
    assert got["label"] == "black zip hoodie" and got["style_tags"] == ["athleisure"] and got["formality"] == 1
    assert got["pattern"] == "solid" and got["summary"] == TAGGED["summary"]  # empty in the fresh copy: kept


def test_save_new_product_and_dry_run(store):
    assert ingest.keep_ai_fields(_fresh(), None) == _fresh()
    store.put("products", TAGGED["id"], TAGGED)
    [p] = ingest.save([_fresh()], dry_run=True)
    assert p["label"] == TAGGED["label"] and p["price_usd"] == 19.99  # what would be saved...
    assert store.get("products", "hm:1:black") == TAGGED               # ...but nothing written
    [q] = ingest.save([_fresh(id="hm:2:black")])
    assert q["label"] == "" and "summary" not in q  # nothing stored to carry over


def test_process_reingest_keeps_tags(store):
    first, _ = ingest.process({"hm": HM}, do_tag=False)
    pid = "hm:1361447006:burgundy-striped"
    tagged = {**next(p for p in first if p["id"] == pid), "label": "burgundy striped top", "pattern": "striped",
              "formality": 2, "style_tags": ["preppy"], "summary": "A striped top.", "price_usd": 1.0}
    store.put("products", pid, tagged)
    raw = copy.deepcopy(HM)
    next(it for it in raw if it["id"] == "1361447006")["price"] = 12.99
    ingest.process({"hm": raw}, do_tag=False)
    got = store.get("products", pid)
    assert got["price_usd"] == 12.99 and got["label"] == "burgundy striped top" and got["summary"] == "A striped top."


# ---------- 2. Apify: async run, polling, paging, cap ----------

class FakeApify:
    """httpx.request stand-in for the three Apify endpoints run_actor / dataset_items use."""

    def __init__(self, statuses, items=(), page_total=True, drop_in_page=None):
        self.statuses = {"run1": list(statuses)} if not isinstance(statuses, dict) else statuses
        self.items, self.page_total, self.drop_in_page = list(items), page_total, drop_in_page
        self.calls = []

    def __call__(self, method, url, headers=None, params=None, json=None, timeout=None):
        assert url.startswith(ingest.APIFY_API) and TOKEN not in url and TOKEN not in str(params)
        assert headers == {"Authorization": f"Bearer {TOKEN}"}
        path, params = url[len(ingest.APIFY_API):], dict(params or {})
        self.calls.append((method, path, params, json))
        req = httpx.Request(method, url)
        if method == "POST" and path.startswith("/acts/") and path.endswith("/runs"):
            run = "run1" if len(self.statuses) == 1 else path.split("/")[2]
            return httpx.Response(201, json={"data": {"id": run, "status": "READY",
                                                      "defaultDatasetId": f"ds-{run}"}}, request=req)
        if method == "GET" and path.startswith("/actor-runs/"):
            run = path.rsplit("/", 1)[1]
            status = self.statuses[run].pop(0)
            if isinstance(status, int):
                return httpx.Response(status, request=req)  # e.g. a 502 while the run goes on
            return httpx.Response(200, json={"data": {"id": run, "status": status, "defaultDatasetId": f"ds-{run}",
                                                      "statusMessage": "actor crashed"}}, request=req)
        if method == "GET" and path.startswith("/datasets/") and path.endswith("/items"):
            assert params["clean"] == "true" and params["format"] == "json"
            off, lim = int(params["offset"]), int(params["limit"])
            page = self.items[off:off + lim]
            if self.drop_in_page is not None and off == self.drop_in_page:
                page = page[1:]  # clean=true skipped an empty item: a short page that isn't the last
            headers = {"x-apify-pagination-total": str(len(self.items))} if self.page_total else {}
            return httpx.Response(200, json=page, headers=headers, request=req)
        raise AssertionError(f"unexpected {method} {path}")

    def paths(self, method=None):
        return [c[1] for c in self.calls if method is None or c[0] == method]


def _items(n):
    return [{"id": str(i)} for i in range(n)]


def test_run_actor_polls_through_502_then_pages_dataset(monkeypatch):
    fake = FakeApify(["RUNNING", 502, "RUNNING", "SUCCEEDED"], _items(5))
    monkeypatch.setattr(ingest.httpx, "request", fake)
    monkeypatch.setattr(ingest, "DATASET_PAGE", 2)
    got = ingest.run_actor("someone/some-actor", {"q": 1}, TOKEN)
    assert got == _items(5)
    method, path, params, body = fake.calls[0]
    assert (method, path, body) == ("POST", "/acts/someone~some-actor/runs", {"q": 1})
    assert params == {"maxTotalChargeUsd": ingest.MAX_CHARGE_USD}  # capped by default
    polls = [c for c in fake.calls if c[1] == "/actor-runs/run1"]
    assert len(polls) == 4 and all(0 < c[2]["waitForFinish"] <= 60 for c in polls)
    assert [c[2]["offset"] for c in fake.calls if c[1] == "/datasets/ds-run1/items"] == [0, 2, 4]
    assert not any("run-sync" in p for p in fake.paths())


def test_run_actor_failed_raises_clear_error(monkeypatch):
    fake = FakeApify(["RUNNING", "FAILED"], _items(3))
    monkeypatch.setattr(ingest.httpx, "request", fake)
    with pytest.raises(ingest.ApifyRunError) as e:
        ingest.run_actor("a/b", {}, TOKEN)
    msg = str(e.value)
    assert "run1 FAILED" in msg and "actor crashed" in msg and "--from-dataset ds-run1" in msg
    assert e.value.run_id == "run1" and e.value.dataset_id == "ds-run1" and TOKEN not in msg
    assert not any(p.startswith("/datasets/") for p in fake.paths())


@pytest.mark.parametrize("status", ["TIMED-OUT", "ABORTED"])
def test_run_actor_keeps_partial_items_of_stopped_run(monkeypatch, status):
    monkeypatch.setattr(ingest.httpx, "request", FakeApify([status], _items(2)))
    assert ingest.run_actor("a/b", {}, TOKEN) == _items(2)  # already paid for


def test_run_actor_gives_up_waiting_with_recovery_hint(monkeypatch):
    fake = FakeApify(["RUNNING"] * 5)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    with pytest.raises(ingest.ApifyRunError, match="still READY after 0s.*--from-dataset ds-run1"):
        ingest.run_actor("a/b", {}, TOKEN, timeout=0)
    assert fake.paths() == ["/acts/a~b/runs"]  # never aborted, never re-run


def test_run_actor_auth_error_not_retried(monkeypatch):
    fake = FakeApify([401, "SUCCEEDED"])
    monkeypatch.setattr(ingest.httpx, "request", fake)
    with pytest.raises(httpx.HTTPStatusError) as e:
        ingest.run_actor("a/b", {}, TOKEN)
    assert e.value.response.status_code == 401 and TOKEN not in str(e.value)


def test_dataset_items_pages_by_total_not_page_size(monkeypatch):
    fake = FakeApify([], _items(5), drop_in_page=2)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    got = ingest.dataset_items("ds-x", TOKEN, page=2)
    assert [it["id"] for it in got] == ["0", "1", "3", "4"]  # short middle page didn't stop the paging
    fake = FakeApify([], _items(4), page_total=False)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    assert ingest.dataset_items("ds-x", TOKEN, page=2) == _items(4)  # no total header: stop at an empty page
    assert len(fake.paths()) == 3


@pytest.mark.parametrize("cap, sent", [(1.5, {"maxTotalChargeUsd": 1.5}), (None, {})])
def test_max_charge_threaded_through_fetchers(monkeypatch, cap, sent):
    for fetch in (ingest.fetch_hm, ingest.fetch_uniqlo):
        fake = FakeApify(["SUCCEEDED"], _items(1))
        monkeypatch.setattr(ingest.httpx, "request", fake)
        assert fetch(["mens polos"], 5, TOKEN, max_charge_usd=cap) == _items(1)
        assert fake.calls[0][2] == sent


def test_finder_style_call_still_works(monkeypatch):
    fake = FakeApify(["SUCCEEDED"], HM)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    assert ingest.normalize_hm(ingest.fetch_hm(["hoodie"], 3, TOKEN))  # positional, as app/ai/finder.py calls it
    assert fake.calls[0][2] == {"maxTotalChargeUsd": ingest.MAX_CHARGE_USD}
    assert fake.calls[0][3] == {"keywords": "hoodie", "Country": "en_us", "maxItems": 3}


# ---------- CLI: --from-dataset, --max-charge ----------

@pytest.fixture()
def cli(monkeypatch, store):
    from scripts import ingest as cli
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    return cli


def test_cli_from_dataset_saves_raw_and_normalizes(cli, monkeypatch, tmp_path, capsys):
    fake = FakeApify([], HM)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    raw_path = tmp_path / "raw" / "{retailer}_recovered.json.gz"
    summary = cli.main(["--from-dataset", "uYlbnLWpWYVVqbnne", "--retailer", "hm", "--no-tag",
                        "--save-raw", str(raw_path), "--show", "0"])
    assert fake.paths("POST") == []  # no new (paid) run
    assert fake.paths() == ["/datasets/uYlbnLWpWYVVqbnne/items"]
    assert summary["saved"] == {"hm": 4} and summary["datasets"] == ["uYlbnLWpWYVVqbnne"]
    saved_raw = tmp_path / "raw" / "hm_recovered.json.gz"
    assert summary["raw_files"] == [str(saved_raw)] and json.loads(gzip.decompress(saved_raw.read_bytes())) == HM
    from app.store import store
    assert len(store.list("products")) == 4  # not a dry run: saved
    assert json.loads(capsys.readouterr().out)["saved"] == {"hm": 4}


def test_cli_from_dataset_needs_retailer_and_token(cli, monkeypatch):
    with pytest.raises(SystemExit):
        cli.main(["--from-dataset", "ds1"])
    with pytest.raises(SystemExit):
        cli.main(["--from-dataset", "ds1", "--from-file", "x.json", "--retailer", "hm"])
    monkeypatch.setenv("APIFY_TOKEN", "")
    with pytest.raises(SystemExit):
        cli.main(["--from-dataset", "ds1", "--retailer", "hm"])


@pytest.mark.parametrize("flag, sent", [([], {"maxTotalChargeUsd": 2.0}), (["--max-charge", "1.25"],
                                         {"maxTotalChargeUsd": 1.25}), (["--max-charge", "0"], {})])
def test_cli_live_run_is_capped(cli, monkeypatch, flag, sent):
    fake = FakeApify(["RUNNING", "SUCCEEDED"], HM)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    summary = cli.main(["--hm", "mens polos", "--uniqlo", "", "--per", "5", "--no-tag", "--dry-run",
                        "--show", "0", *flag])
    assert summary["saved"] == {"hm": 4}
    assert [(c[0], c[2]) for c in fake.calls if c[0] == "POST"] == [("POST", sent)]


def test_cli_failed_run_keeps_earlier_paid_pull(cli, monkeypatch, tmp_path):
    hm_run, uq_run = ingest.HM_ACTOR.replace("/", "~"), ingest.UNIQLO_ACTOR.replace("/", "~")
    fake = FakeApify({hm_run: ["SUCCEEDED"], uq_run: ["RUNNING", "FAILED"]}, HM)
    monkeypatch.setattr(ingest.httpx, "request", fake)
    with pytest.raises(SystemExit) as e:
        cli.main(["--hm", "mens polos", "--uniqlo", "men polos", "--no-tag",
                  "--save-raw", str(tmp_path / "{retailer}.json")])
    assert "FAILED" in str(e.value) and f"--from-dataset ds-{uq_run}" in str(e.value)
    assert json.loads((tmp_path / "hm.json").read_text()) == HM  # H&M was saved before Uniqlo failed
    assert not (tmp_path / "uniqlo.json").exists()
