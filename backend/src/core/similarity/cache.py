"""SQLite persistence for the Similarity Finder incremental scan.

Schema (one row per file):
    filepath | modified_timestamp | file_size | xxh64 |
    hash_size | phash | dhash | whash | embed_model | embedding

A file is re-hashed only when its (mtime, size) changed or when the requested
hash_size differs from the cached one; embeddings are recomputed only when the
model name changes or the file changed.

This cache is a *local per-machine artifact* (like thumbnails), intentionally
kept out of the PostgreSQL image database.
"""

import os
import sqlite3
import threading
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_index (
    filepath            TEXT PRIMARY KEY,
    modified_timestamp  REAL NOT NULL,
    file_size           INTEGER NOT NULL,
    xxh64               TEXT,
    hash_size           INTEGER,
    phash               TEXT,
    dhash               TEXT,
    whash               TEXT,
    embed_model         TEXT,
    embedding           BLOB
);
CREATE INDEX IF NOT EXISTS idx_file_index_xxh64 ON file_index (xxh64);
"""


class SimilarityCache:
    """Thread-safe (one connection per thread) SQLite scan cache."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._local = threading.local()
        with self._conn() as con:
            con.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
            self._local.con = con
        return con

    def close(self):
        con = getattr(self._local, "con", None)
        if con is not None:
            con.close()
            self._local.con = None

    # ------------------------------------------------------------------
    # Incremental-scan queries
    # ------------------------------------------------------------------

    @staticmethod
    def _stat(path: str) -> Optional[Tuple[float, int]]:
        try:
            st = os.stat(path)
            return (st.st_mtime, st.st_size)
        except OSError:
            return None

    def partition_stale(
        self, paths: List[str], hash_size: int
    ) -> Tuple[Dict[str, sqlite3.Row], List[str]]:
        """Split *paths* into (fresh rows keyed by path, stale paths to rehash).

        A row is fresh when mtime+size match the filesystem and the cached
        hash_size matches the requested one.
        """
        fresh: Dict[str, sqlite3.Row] = {}
        stale: List[str] = []
        con = self._conn()
        for chunk_start in range(0, len(paths), 500):
            chunk = paths[chunk_start : chunk_start + 500]
            marks = ",".join("?" * len(chunk))
            rows = {
                r["filepath"]: r
                for r in con.execute(
                    f"SELECT * FROM file_index WHERE filepath IN ({marks})", chunk
                )
            }
            for p in chunk:
                st = self._stat(p)
                if st is None:
                    continue  # vanished mid-scan
                row = rows.get(p)
                if (
                    row is not None
                    and abs(row["modified_timestamp"] - st[0]) < 1e-6
                    and row["file_size"] == st[1]
                    and row["hash_size"] == hash_size
                    and row["phash"]
                ):
                    fresh[p] = row
                else:
                    stale.append(p)
        return fresh, stale

    def upsert_hashes(self, records: Iterable[dict], hash_size: int):
        """Store hash records as returned by ``base.similarity.compute_hashes``.

        Preserves an existing embedding only when the file content is
        unchanged (same mtime/size); here we already know the file changed or
        was missing, so the embedding is reset.
        """
        con = self._conn()
        rows = []
        for r in records:
            if not r.get("ok"):
                continue
            st = self._stat(r["path"])
            if st is None:
                continue
            rows.append(
                (r["path"], st[0], st[1], r["xxh64"], hash_size,
                 r["phash"], r["dhash"], r["whash"])
            )
        with con:
            con.executemany(
                """
                INSERT INTO file_index
                    (filepath, modified_timestamp, file_size, xxh64,
                     hash_size, phash, dhash, whash, embed_model, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                ON CONFLICT(filepath) DO UPDATE SET
                    modified_timestamp = excluded.modified_timestamp,
                    file_size          = excluded.file_size,
                    xxh64              = excluded.xxh64,
                    hash_size          = excluded.hash_size,
                    phash              = excluded.phash,
                    dhash              = excluded.dhash,
                    whash              = excluded.whash,
                    embed_model        = NULL,
                    embedding          = NULL
                """,
                rows,
            )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def get_embeddings(
        self, paths: List[str], model: str
    ) -> Tuple[Dict[str, np.ndarray], List[str]]:
        """Return (cached embeddings keyed by path, paths still needing one)."""
        have: Dict[str, np.ndarray] = {}
        missing: List[str] = []
        con = self._conn()
        for chunk_start in range(0, len(paths), 500):
            chunk = paths[chunk_start : chunk_start + 500]
            marks = ",".join("?" * len(chunk))
            rows = {
                r["filepath"]: r
                for r in con.execute(
                    f"SELECT filepath, embed_model, embedding FROM file_index "
                    f"WHERE filepath IN ({marks})",
                    chunk,
                )
            }
            for p in chunk:
                row = rows.get(p)
                if row is not None and row["embed_model"] == model and row["embedding"]:
                    have[p] = np.frombuffer(row["embedding"], dtype=np.float32)
                else:
                    missing.append(p)
        return have, missing

    def upsert_embeddings(self, embeddings: Dict[str, np.ndarray], model: str):
        con = self._conn()
        with con:
            con.executemany(
                "UPDATE file_index SET embed_model = ?, embedding = ? "
                "WHERE filepath = ?",
                [
                    (model, np.asarray(v, dtype=np.float32).tobytes(), p)
                    for p, v in embeddings.items()
                ],
            )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def prune_missing(self) -> int:
        """Drop rows whose file no longer exists. Returns rows removed."""
        con = self._conn()
        gone = [
            (r["filepath"],)
            for r in con.execute("SELECT filepath FROM file_index")
            if not os.path.exists(r["filepath"])
        ]
        with con:
            con.executemany("DELETE FROM file_index WHERE filepath = ?", gone)
        return len(gone)

    def row_count(self) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
