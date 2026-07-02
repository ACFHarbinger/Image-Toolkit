"""§4.6 Cross-directory perceptual-hash deduplication.

Provides :func:`compute_phash` (image path → signed 64-bit int) and
:class:`PhashDeduplicator`, a high-level wrapper that indexes phashes into
``PgvectorImageDatabase`` and queries for near-duplicate candidates across all
directories.

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
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}

# Default Hamming-distance threshold.  Two 64-bit pHashes with ≤10 different
# bits are almost certainly the same image (different format, small crop, minor
# compression artefact).  Raise to 20 for thumbnails or aggressive compression.
DEFAULT_PHASH_THRESHOLD = 10


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
    """High-level API for cross-directory phash deduplication backed by PostgreSQL.

    Wraps :class:`~backend.src.database.image_database.PgvectorImageDatabase`
    and adds convenience methods for batch indexing and near-duplicate queries.

    Parameters
    ----------
    db : ``PgvectorImageDatabase`` instance, or ``None`` to construct a default one.
    threshold : default Hamming-distance threshold for near-duplicate queries.
    """

    def __init__(
        self,
        db=None,
        threshold: int = DEFAULT_PHASH_THRESHOLD,
    ) -> None:
        if db is None:
            from backend.src.database.image_database import PgvectorImageDatabase
            db = PgvectorImageDatabase()
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
            if not p.is_file() or p.suffix.lower() not in _IMG_EXTS:
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

        # Fetch all images that have a phash
        with self._db.conn.cursor() as cur:
            cur.execute(
                "SELECT id, file_path, filename, group_name, subgroup_name, phash "
                "FROM images WHERE phash IS NOT NULL ORDER BY id ASC"
            )
            all_rows = cur.fetchall()

        for row in all_rows:
            img_id, file_path, filename, group_name, subgroup_name, phash = row
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
