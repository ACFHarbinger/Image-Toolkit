"""§4.6 Cross-directory perceptual-hash deduplication.

Provides :func:`compute_phash` (image path → signed 64-bit int) and
:class:`PhashDeduplicator`, a high-level wrapper that indexes phashes into
the unified library store (``UnifiedImageDatabase`` / DB.6) and queries for
near-duplicate candidates across all directories.

Re-pointed at the unified store 2026-07-27 (DB.6 P3b) — this previously
wrapped the retired ``PgvectorImageDatabase`` (Postgres), which required a
running Postgres server and is no longer how the app stores its library.

Usage
-----
::

    from backend.src.core.phash_deduplicator import PhashDeduplicator

    with PhashDeduplicator() as ded:
        ded.index_directory("/mnt/images/collection_a")
        ded.index_directory("/mnt/images/collection_b")
        dupes = ded.find_duplicates_for("/mnt/images/collection_a/img_001.png", threshold=10)
        for d in dupes:
            print(d["file_path"], "hamming =", d["hamming_dist"])

Requires an already-open unified library session (the app opens one at
login via ``session.open_session()``); pass an explicit ``db`` (any object
exposing ``UnifiedImageDatabase``'s method surface — a fake/mock is fine
for tests) to use outside of a running app.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.constants.core import CORE__IMG_EXTS, DEFAULT_PHASH_THRESHOLD

logger = logging.getLogger(__name__)


# Default Hamming-distance threshold.  Two 64-bit pHashes with ≤10 different
# bits are almost certainly the same image (different format, small crop, minor
# compression artefact).  Raise to 20 for thumbnails or aggressive compression.


def compute_phash(path: str) -> Optional[int]:
    """Compute the 64-bit perceptual hash of *path* and return a signed int.

    Uses ``imagehash.phash`` (8×8 DCT-based hash, 64 bits).  The raw hash is a
    non-negative 64-bit value; we convert to a *signed* BIGINT so PostgreSQL can
    store it without truncation (Python ``int`` is arbitrary-precision; psycopg2
    maps Python int to PostgreSQL BIGINT).

    Returns ``None`` if the file cannot be opened or ``imagehash`` is unavailable.
    """
    try:
        import imagehash
        from PIL import Image

        img = Image.open(path)
        hash_obj = imagehash.phash(img)
        raw = int(str(hash_obj), 16)
        # Convert unsigned 64-bit to signed BIGINT (two's complement).
        if raw >= (1 << 63):
            raw -= 1 << 64
        return raw
    except ImportError:
        logger.warning("imagehash not installed — phash unavailable")
        return None
    except Exception as exc:
        logger.debug("compute_phash failed for %s: %s", path, exc)
        return None


class PhashDeduplicator:
    """High-level API for cross-directory phash deduplication over the
    unified library store (``UnifiedImageDatabase`` / DB.6).

    Parameters
    ----------
    db : ``UnifiedImageDatabase``-compatible instance, or ``None`` to wrap
         the app's already-open unified session (raises if none is open —
         call ``session.open_session()`` after vault unlock first).
    threshold : default Hamming-distance threshold for near-duplicate queries.
    """

    def __init__(
        self,
        db=None,
        threshold: int = DEFAULT_PHASH_THRESHOLD,
    ) -> None:
        if db is None:
            from backend.src.database.unified import session
            from backend.src.database.unified.facade import UnifiedImageDatabase
            db = UnifiedImageDatabase(session.get_session())
        self._db = db
        self.threshold = threshold

    # ── Indexing ────────────────────────────────────────────────────────────────

    def index_image(self, image_id: int, path: str) -> bool:
        """Compute and store the phash for a single image already in the DB.

        Returns ``True`` if the hash was successfully written.
        """
        phash = compute_phash(path)
        if phash is None:
            return False
        try:
            self._db.update_phash(image_id, phash)
            return True
        except Exception as exc:
            logger.warning("Failed to store phash for %s (id=%d): %s", path, image_id, exc)
            return False

    def index_directory(
        self,
        directory: str,
        recursive: bool = False,
        skip_indexed: bool = True,
    ) -> Dict[str, int]:
        """Compute and store phashes for all images in *directory*.

        Parameters
        ----------
        recursive    : also descend into sub-directories.
        skip_indexed : skip images whose ``phash`` column is already populated
                       (avoids redundant work on re-runs).

        Returns
        -------
        dict with keys ``"indexed"``, ``"skipped"``, ``"failed"``.
        """
        stats: Dict[str, int] = {"indexed": 0, "skipped": 0, "failed": 0}
        root = Path(directory)
        pattern = "**/*" if recursive else "*"

        for p in sorted(root.glob(pattern)):
            if not p.is_file() or p.suffix.lower() not in CORE__IMG_EXTS:
                continue
            path_str = str(p.absolute())

            img_row = self._db.get_image_by_path(path_str)
            if img_row is None:
                stats["skipped"] += 1
                continue
            if skip_indexed and img_row.get("phash") is not None:
                stats["skipped"] += 1
                continue

            ok = self.index_image(img_row["id"], path_str)
            if ok:
                stats["indexed"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            "[PhashDedup] %s — indexed=%d skipped=%d failed=%d",
            directory,
            stats["indexed"],
            stats["skipped"],
            stats["failed"],
        )
        return stats

    # ── Querying ────────────────────────────────────────────────────────────────

    def find_duplicates_for(
        self,
        path: str,
        threshold: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return near-duplicate images for a given file path.

        Computes the phash of *path* on the fly and queries the DB index.  The
        result includes the query image itself (Hamming distance 0) when it is
        already indexed.

        Parameters
        ----------
        path      : absolute path to the query image (need not be in the DB).
        threshold : override for the default Hamming threshold.
        limit     : maximum results to return.
        """
        phash = compute_phash(path)
        if phash is None:
            return []
        return self._db.find_near_duplicates_by_phash(
            phash,
            threshold=threshold if threshold is not None else self.threshold,
            limit=limit,
        )

    def find_all_duplicate_groups(
        self,
        threshold: Optional[int] = None,
        limit_per_image: int = 20,
    ) -> List[List[Dict[str, Any]]]:
        """Cluster all indexed images into near-duplicate groups.

        Uses a greedy sweep: iterates all images with phashes, queries
        near-duplicates for each, and groups them by connected component.

        Returns a list of groups; each group is a list of image dicts (with
        ``hamming_dist`` relative to the group representative).  Only groups
        with more than one member are returned.
        """
        thr = threshold if threshold is not None else self.threshold
        visited_ids: set = set()
        groups: List[List[Dict[str, Any]]] = []

        # Fetch all images that have a phash, via the facade's own accessor
        # (previously a raw psycopg2 cursor — the unified store has no such
        # DB-API cursor, and file_path/filename/group_name/subgroup_name
        # were unpacked here but never actually used below).
        all_rows = self._db.get_all_phashes()

        for img_id, _file_path, phash in sorted(all_rows, key=lambda r: r[0]):
            if img_id in visited_ids:
                continue
            near = self._db.find_near_duplicates_by_phash(
                phash, threshold=thr, limit=limit_per_image
            )
            if len(near) <= 1:
                visited_ids.add(img_id)
                continue
            group_ids = {d["id"] for d in near}
            visited_ids.update(group_ids)
            groups.append(near)

        return groups

    # ── Context manager ─────────────────────────────────────────────────────────

    def __enter__(self) -> "PhashDeduplicator":
        return self

    def __exit__(self, *_) -> None:
        self._db.close()


__all__ = ["compute_phash", "PhashDeduplicator", "DEFAULT_PHASH_THRESHOLD"]
