"""Tiny data store.

Default: JSON files under backend/data/ (works offline, zero setup).
Set USE_FIRESTORE=1 (+ GOOGLE_APPLICATION_CREDENTIALS) to use Firestore with
the same collection names: products, closet_items, users, swipes, tryon_cache.
Nabil can swap in his own product source — get/list/put/delete are all that's used.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))


class JsonStore:
    def __init__(self, root: Path = DATA_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, collection: str) -> Path:
        return self.root / f"{collection}.json"

    def _load(self, collection: str) -> dict[str, dict]:
        p = self._path(collection)
        if not p.exists():
            return {}
        return json.loads(p.read_text() or "{}")

    def get(self, collection: str, doc_id: str) -> dict | None:
        return self._load(collection).get(doc_id)

    def list(self, collection: str, **where: Any) -> list[dict]:
        docs = self._load(collection).values()
        return [d for d in docs if all(d.get(k) == v for k, v in where.items())]

    def _write(self, collection: str, data: dict) -> None:
        # temp file + rename: a reader (another request, another process) never sees a half-written
        # file. Writing in place let a concurrent get() read "" and reset e.g. the AI usage counter.
        path = self._path(collection)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)

    def put(self, collection: str, doc_id: str, doc: dict) -> None:
        with self._lock:
            data = self._load(collection)
            data[doc_id] = doc
            self._write(collection, data)

    def delete(self, collection: str, doc_id: str) -> bool:
        with self._lock:
            data = self._load(collection)
            if data.pop(doc_id, None) is None:
                return False
            self._write(collection, data)
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
