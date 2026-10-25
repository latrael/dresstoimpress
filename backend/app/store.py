"""Tiny data store.

Default: JSON files under backend/data/ (works offline, zero setup).
Set USE_FIRESTORE=1 (+ GOOGLE_APPLICATION_CREDENTIALS) to use Firestore with
the same collection names: products, closet_items, users, swipes, tryon_cache.
Nabil can swap in his own product source — get/list/put/delete are all that's used.
"""
from __future__ import annotations

import json
import marshal
import os
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))


def _copy(doc: Any) -> Any:
    """Deep copy of JSON data (dict/list/str/number/bool/None), done in C: a round trip through marshal."""
    return marshal.loads(marshal.dumps(doc))


class JsonStore:
    """One JSON file per collection: {doc_id: doc}.

    Reads are cached in memory per file and checked against the file's (inode, mtime_ns, size) on every
    call, so a write by another process (a script running while the server is up) shows up on the next
    read. Every write replaces the file (temp file + rename), which gives it a new inode.
    Cached data is never handed out: get() and _load() return deep copies, list() a shallow copy of each
    doc (callers build new dicts with {**doc}; none change a listed doc's nested lists in place).
    """

    def __init__(self, root: Path = DATA_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: dict[Path, tuple[tuple, dict]] = {}  # path -> (file key, parsed data); never mutated

    def _path(self, collection: str) -> Path:
        return self.root / f"{collection}.json"

    @staticmethod
    def _key(st: os.stat_result) -> tuple:
        return (st.st_ino, st.st_mtime_ns, st.st_size)

    def _cached(self, collection: str) -> dict[str, dict]:
        """The collection as it is on disk now. Shared with the cache: read it, never mutate it."""
        p = self._path(collection)
        try:
            key = self._key(os.stat(p))
        except FileNotFoundError:
            self._cache.pop(p, None)
            return {}
        hit = self._cache.get(p)
        if hit is not None and hit[0] == key:
            return hit[1]
        try:
            with open(p, "rb") as f:
                key = self._key(os.fstat(f.fileno()))  # the stat of exactly the file we read
                data = json.loads(f.read() or b"{}")
        except FileNotFoundError:  # deleted between stat and open
            self._cache.pop(p, None)
            return {}
        self._cache[p] = (key, data)
        return data

    def _load(self, collection: str) -> dict[str, dict]:
        return _copy(self._cached(collection))

    def get(self, collection: str, doc_id: str) -> dict | None:
        doc = self._cached(collection).get(doc_id)
        return None if doc is None else _copy(doc)

    def list(self, collection: str, **where: Any) -> list[dict]:
        docs = self._cached(collection).values()
        return [dict(d) if isinstance(d, dict) else _copy(d)
                for d in docs if all(d.get(k) == v for k, v in where.items())]

    def _write(self, collection: str, data: dict, parsed: dict | None = None) -> None:
        # temp file + rename: a reader (another request, another process) never sees a half-written
        # file. Writing in place let a concurrent get() read "" and reset e.g. the AI usage counter.
        # `parsed`: exactly what reading the new file back would give, cached as is (None: re-read it).
        path = self._path(collection)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        key = self._key(os.stat(tmp))  # the rename keeps inode, mtime and size
        self._cache.pop(path, None)
        os.replace(tmp, path)
        if parsed is not None:
            self._cache[path] = (key, parsed)

    def put(self, collection: str, doc_id: str, doc: dict) -> None:
        with self._lock:
            data = dict(self._cached(collection))  # checked against the file inside the lock
            data[doc_id] = doc
            parsed = None
            if isinstance(doc_id, str):  # a non-str id is a different key once in JSON: re-read instead
                parsed = dict(data)
                parsed[doc_id] = json.loads(json.dumps(doc))  # what the file holds, not the caller's object
            self._write(collection, data, parsed)

    def delete(self, collection: str, doc_id: str) -> bool:
        with self._lock:
            data = dict(self._cached(collection))
            if data.pop(doc_id, None) is None:
                return False
            self._write(collection, data, data)
            return True


class FirestoreStore:
    def __init__(self):
        from google.cloud import firestore  # optional dependency

        self.db = firestore.Client()

    def get(self, collection: str, doc_id: str) -> dict | None:
        snap = self.db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def list(self, collection: str, **where: Any) -> list[dict]:
        q = self.db.collection(collection)
        for k, v in where.items():
            q = q.where(k, "==", v)
        return [s.to_dict() for s in q.stream()]

    def put(self, collection: str, doc_id: str, doc: dict) -> None:
        self.db.collection(collection).document(doc_id).set(doc)

    def delete(self, collection: str, doc_id: str) -> bool:
        ref = self.db.collection(collection).document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


store = FirestoreStore() if os.getenv("USE_FIRESTORE") == "1" else JsonStore()
