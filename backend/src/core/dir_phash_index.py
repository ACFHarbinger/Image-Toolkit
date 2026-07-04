"""§7.6 Directory-tree perceptual-hash index for the browser-extension bridge.

Unlike :class:`~backend.src.core.phash_deduplicator.PhashDeduplicator` (which
requires the PostgreSQL image database), this index is fully self-contained:
it scans a configured root directory (and optionally its subdirectories),
caches 64-bit pHashes in a small SQLite file keyed by (path, mtime, size),
and answers Hamming-distance queries with a linear popcount sweep — fast in
pure Python up to hundreds of thousands of entries thanks to
``int.bit_count()``.

Usage
-----
::

    idx = DirPhashIndex("/mnt/images", recursive=True)
    stats = idx.refresh()                     # incremental: only new/changed files
    matches = idx.query_bytes(image_bytes)    # [{"path": ..., "hamming": ...}, ...]
"""

from __future__ import annotations

import io
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.constants import IMAGE_TOOLKIT_DIR

logger = logging.getLogger(__name__)

_IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif")

DEFAULT_THRESHOLD = 10

BRIDGE_DIR = IMAGE_TOOLKIT_DIR / "extension-bridge"
DEFAULT_DB_PATH = BRIDGE_DIR / "phash_index.db"

_U64 = 0xFFFFFFFFFFFFFFFF


def _to_signed64(v: int) -> int:
    """Two's-complement fold so the hash fits SQLite's signed INTEGER."""
    return v - (1 << 64) if v >= (1 << 63) else v


def _hamming64(a: int, b: int) -> int:
    """Hamming distance of two 64-bit hashes regardless of sign encoding."""
    return ((a ^ b) & _U64).bit_count()


def compute_phash_bytes(data: bytes) -> Optional[int]:
    """Compute the unsigned 64-bit pHash of raw image bytes, or None on failure."""
    try:
        import imagehash
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        return int(str(imagehash.phash(img)), 16)
    except Exception as exc:
        logger.debug("compute_phash_bytes failed: %s", exc)
        return None


def compute_phash_file(path: str) -> Optional[int]:
    """Compute the unsigned 64-bit pHash of an image file, or None on failure."""
    try:
        import imagehash
        from PIL import Image

        with Image.open(path) as img:
            return int(str(imagehash.phash(img)), 16)
    except Exception as exc:
        logger.debug("compute_phash_file failed for %s: %s", path, exc)
        return None


def _scan_tree(root: str, recursive: bool) -> List[str]:
    """List image files under *root* (C++ scanner when available)."""
    try:
        import base  # C++ fast path

        return list(base.scan_files_multi([root], list(_IMG_EXTS), recursive))
    except Exception:
        pass

    results: List[str] = []
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.lower().endswith(_IMG_EXTS):
                    results.append(os.path.join(dirpath, name))
    else:
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if entry.is_file() and entry.name.lower().endswith(_IMG_EXTS):
                        results.append(entry.path)
        except OSError as exc:
            logger.warning("scan failed for %s: %s", root, exc)
    return sorted(results)


class DirPhashIndex:
    """SQLite-cached pHash index over a directory tree."""

    def __init__(
        self,
        root: str,
        db_path: Optional[str] = None,
        recursive: bool = True,
    ) -> None:
        self.root = str(Path(root).expanduser())
        self.recursive = recursive
        if db_path is None:
            BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
            db_path = str(DEFAULT_DB_PATH)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS files ("
            " path  TEXT PRIMARY KEY,"
            " mtime REAL NOT NULL,"
            " size  INTEGER NOT NULL,"
            " phash INTEGER"  # NULL = decode failed; row kept to avoid re-tries
            ")"
        )
        self._conn.commit()

    # ── Indexing ─────────────────────────────────────────────────────────────

    def refresh(self) -> Dict[str, Any]:
        """Incrementally sync the index with the directory tree.

        New or modified files (by mtime+size) get their pHash (re)computed;
        rows whose file vanished are dropped. Returns stats including
        ``cold_scan`` (True when the index started empty).
        """
        t0 = time.time()
        cur = self._conn.execute("SELECT path, mtime, size FROM files")
        known = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        cold_scan = len(known) == 0

        on_disk = _scan_tree(self.root, self.recursive)
        on_disk_set = set(on_disk)

        stats = {"computed": 0, "unchanged": 0, "removed": 0, "failed": 0}

        # Drop rows for deleted files
        stale = [p for p in known if p not in on_disk_set]
        if stale:
            self._conn.executemany(
                "DELETE FROM files WHERE path = ?", [(p,) for p in stale]
            )
            stats["removed"] = len(stale)

        for path in on_disk:
            try:
                st = os.stat(path)
            except OSError:
                continue
            prev = known.get(path)
            if prev is not None and prev == (st.st_mtime, st.st_size):
                stats["unchanged"] += 1
                continue
            phash = compute_phash_file(path)
            if phash is None:
                stats["failed"] += 1
            else:
                stats["computed"] += 1
            self._conn.execute(
                "INSERT OR REPLACE INTO files (path, mtime, size, phash)"
                " VALUES (?, ?, ?, ?)",
                (
                    path,
                    st.st_mtime,
                    st.st_size,
                    _to_signed64(phash) if phash is not None else None,
                ),
            )
        self._conn.commit()

        stats["total"] = len(on_disk)
        stats["cold_scan"] = cold_scan
        stats["elapsed_s"] = round(time.time() - t0, 3)
        logger.info("[DirPhashIndex] %s — %s", self.root, stats)
        return stats

    # ── Querying ─────────────────────────────────────────────────────────────

    def query(
        self,
        phash: int,
        threshold: int = DEFAULT_THRESHOLD,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return files whose pHash is within *threshold* Hamming bits."""
        cur = self._conn.execute(
            "SELECT path, phash FROM files WHERE phash IS NOT NULL"
        )
        matches: List[Dict[str, Any]] = []
        for path, stored in cur.fetchall():
            dist = _hamming64(phash, stored)
            if dist <= threshold:
                matches.append({"path": path, "hamming": dist})
        matches.sort(key=lambda m: m["hamming"])
        return matches[:limit]

    def query_bytes(
        self,
        data: bytes,
        threshold: int = DEFAULT_THRESHOLD,
        limit: int = 50,
    ) -> Optional[List[Dict[str, Any]]]:
        """Query with raw image bytes. Returns None if the bytes don't decode."""
        phash = compute_phash_bytes(data)
        if phash is None:
            return None
        return self.query(phash, threshold=threshold, limit=limit)

    def count(self) -> int:
        """Number of indexed files (including failed-decode placeholders)."""
        return self._conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DirPhashIndex":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = [
    "DirPhashIndex",
    "compute_phash_bytes",
    "compute_phash_file",
    "DEFAULT_THRESHOLD",
    "BRIDGE_DIR",
]
