"""JsonStore read cache: never stale after another process/thread writes, and callers can't corrupt it."""
import json
import os
import subprocess
import sys
import threading

import pytest


def _store(root):  # imported late: importing app.store at collection would fix DATA_DIR for test_ai
    from app.store import JsonStore
    return JsonStore(root)


@pytest.fixture
def s(tmp_path):
    return _store(tmp_path)


def _disk(s, col: str) -> dict:
    return json.loads(s._path(col).read_text())


def test_put_get_list_delete_match_disk(s):
    s.put("c", "a", {"id": "a", "n": 1, "tag": "x"})
    s.put("c", "b", {"id": "b", "n": 2, "tag": "y"})
    s.put("c", "a", {"id": "a", "n": 3, "tag": "x"})  # overwrite keeps its place
    assert s.get("c", "a") == {"id": "a", "n": 3, "tag": "x"}
    assert s.list("c") == [{"id": "a", "n": 3, "tag": "x"}, {"id": "b", "n": 2, "tag": "y"}]
    assert s.list("c", tag="y") == [{"id": "b", "n": 2, "tag": "y"}]
    assert s._load("c") == _disk(s, "c")
    assert s.delete("c", "a") is True
    assert s.delete("c", "a") is False
    assert s.get("c", "a") is None
    assert s.list("c") == [{"id": "b", "n": 2, "tag": "y"}] == list(_disk(s, "c").values())
    assert s.get("missing", "x") is None and s.list("missing") == [] and s._load("missing") == {}


def test_cached_value_is_what_a_fresh_read_gives(s):
    s.put("c", "a", {"id": "a", "t": (1, 2), "k": {1: "one"}})  # JSON turns tuples into lists, keys into str
    assert s.get("c", "a") == _store(s.root).get("c", "a") == {"id": "a", "t": [1, 2], "k": {"1": "one"}}
    s.put("c", 7, {"id": 7})  # a non-str id is stored under "7", like before
    assert s.get("c", "7") == {"id": 7} and s.get("c", 7) is None


def test_sees_write_by_another_store_instance(s):
    other = _store(s.root)  # same files, separate cache: another process
    s.put("c", "a", {"v": 1})
    assert s.get("c", "a") == {"v": 1}
    other.put("c", "a", {"v": 2})
    other.put("c", "b", {"v": 3})
    assert s.get("c", "a") == {"v": 2}
    assert s.list("c") == [{"v": 2}, {"v": 3}]
    s.put("c", "d", {"v": 4})  # put re-reads inside the lock: other's docs survive
    assert other.list("c") == [{"v": 2}, {"v": 3}, {"v": 4}]


def test_sees_in_place_rewrite_of_same_size(s):
    s.put("c", "a", {"v": "aaaa"})
    assert s.get("c", "a") == {"v": "aaaa"}
    p = s._path("c")
    before = os.stat(p)
    text = p.read_text().replace("aaaa", "bbbb")  # same size, same inode
    p.write_text(text)
    os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))  # make sure mtime moved
    assert os.stat(p).st_size == before.st_size
    assert s.get("c", "a") == {"v": "bbbb"}


def test_sees_write_by_another_process(s):
    s.put("c", "a", {"v": 1})
    assert s.list("c") == [{"v": 1}]
    code = ("import json, os, sys; p = sys.argv[1]; t = p + '.tmp'; "
            "open(t, 'w').write(json.dumps({'a': {'v': 9}, 'z': {'v': 10}})); os.replace(t, p)")
    subprocess.run([sys.executable, "-c", code, str(s._path("c"))], check=True)
    assert s.get("c", "a") == {"v": 9}
    assert s.list("c") == [{"v": 9}, {"v": 10}]


def test_file_removed_or_emptied_outside(s):
    s.put("c", "a", {"v": 1})
    s._path("c").write_text("")
    assert s.list("c") == [] and s.get("c", "a") is None
    s._path("c").unlink()
    assert s.list("c") == [] and s.get("c", "a") is None
    s.put("c", "b", {"v": 2})
    assert s._load("c") == {"b": {"v": 2}}


def test_callers_cannot_corrupt_the_cache(s):
    doc = {"id": "a", "likes": ["u1"], "meta": {"n": 1}}
    s.put("c", "a", doc)
    doc["likes"].append("put-then-mutate")  # the caller's object is not the cached one
    got = s.get("c", "a")
    got["likes"].append("u2")
    got["meta"]["n"] = 99
    got["new"] = True
    listed = s.list("c")[0]
    listed["id"] = "changed"
    listed["extra"] = 1
    loaded = s._load("c")
    loaded["a"]["likes"].clear()
    loaded["zzz"] = {}
    assert s.get("c", "a") == {"id": "a", "likes": ["u1"], "meta": {"n": 1}} == _disk(s, "c")["a"]
    assert s.list("c") == [{"id": "a", "likes": ["u1"], "meta": {"n": 1}}]


def test_external_write_helper_is_not_served_stale(s):
    s.put("c", "a", {"v": 1})
    s._write("c", {"b": {"v": 2}})  # scripts/rebuild_db.py writes whole collections this way
    assert s._load("c") == {"b": {"v": 2}}


def test_threads_writing_and_reading(s):
    other = _store(s.root)
    errors = []

    def writer(store, prefix):
        try:
            for i in range(40):
                store.put("c", f"{prefix}{i}", {"id": f"{prefix}{i}", "i": i})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def reader():
        try:
            for _ in range(200):
                for d in s.list("c"):
                    assert d["id"].rstrip("0123456789") in {"a", "b", "c", "o"}
                s.get("c", "a1")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(s, p)) for p in "abc"]
    threads += [threading.Thread(target=reader) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    ids = {d["id"] for d in s.list("c")}
    assert ids == {f"{p}{i}" for p in "abc" for i in range(40)}  # one store's lock: no lost updates
    assert s._load("c") == _disk(s, "c") == other._load("c")
