"""
Dispatch shim that routes base-module calls to the C++ batch extension
when available, falling back to the Rust base module otherwise.

Routing flags are set once at import time; runtime overhead is a single
attribute lookup per call (same as a direct module reference).

Phase 2–5 of the Rust → C++ migration.
See moon/roadmaps/rust_to_cpp_migration.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Attempt to import the C++ batch extension and check which submodules exist
# ---------------------------------------------------------------------------

_batch = None
_HAS_IMAGE  = False
_HAS_VIDEO  = False
_HAS_SECRET = False
_HAS_WEB    = False

try:
    import batch as _batch_cpp  # type: ignore[import]
    _batch      = _batch_cpp
    _HAS_IMAGE  = hasattr(_batch_cpp, "image")
    _HAS_VIDEO  = hasattr(_batch_cpp, "video")
    _HAS_SECRET = hasattr(_batch_cpp, "secret")
    _HAS_WEB    = hasattr(_batch_cpp, "web")
except ImportError:
    pass

# Rust base module — imported lazily to avoid mandatory Rust ABI at startup
def _base():
    import base as _b  # type: ignore[import]
    return _b


# ---------------------------------------------------------------------------
# NativeExt — static-method dispatch class
# ---------------------------------------------------------------------------

class NativeExt:
    """Routes each function to the C++ batch extension or the Rust base module."""

    # ------------------------------------------------------------------
    # Phase 2 — image I/O + filesystem
    # ------------------------------------------------------------------

    @staticmethod
    def load_image_batch(paths, target_size: int = 256):
        """Load image thumbnails in parallel.

        C++ signature: load_image_batch(paths, thumb_w, thumb_h, keep_aspect=True)
        Rust signature: load_image_batch(paths, target_size)  (single int, square)
        """
        if _HAS_IMAGE:
            try:
                return _batch.image.load_image_batch(
                    paths, target_size, target_size, keep_aspect=True)
            except Exception:
                pass
        return _base().load_image_batch(paths, target_size)

    @staticmethod
    def scan_files(root_dir: str, extensions=None, recursive: bool = True):
        """Recursively scan a directory for files matching the given extensions."""
        if _HAS_IMAGE:
            try:
                exts = extensions or []
                return _batch.image.scan_files(root_dir, exts, recursive)
            except Exception:
                pass
        return _base().scan_files(root_dir, extensions, recursive)

    # ------------------------------------------------------------------
    # Phase 3 — video thumbnails
    # ------------------------------------------------------------------

    @staticmethod
    def extract_video_thumbnails_batch(paths, timestamps_sec=None,
                                       thumb_w: int = 256, thumb_h: int = 256):
        """Extract video frame thumbnails in parallel."""
        if _HAS_VIDEO:
            try:
                ts = timestamps_sec or [0.0]
                return _batch.video.extract_video_thumbnails_batch(
                    paths, ts, thumb_w, thumb_h)
            except Exception:
                pass
        return _base().extract_video_thumbnails_batch(
            paths, timestamps_sec, thumb_w, thumb_h)

    # ------------------------------------------------------------------
    # Phase 4 — secure vector database
    # ------------------------------------------------------------------

    @staticmethod
    def insert_listing_secure(db_path: str, password: str, listing_id: str,
                              embedding, metadata_json: str = "{}"):
        if _HAS_SECRET:
            try:
                return _batch.secret.insert_listing_secure(
                    db_path, password, listing_id, embedding, metadata_json)
            except TypeError:
                pass  # stub raises TypeError when HAVE_SQLCIPHER not defined
        return _base().insert_listing_secure(
            db_path, password, listing_id, embedding, metadata_json)

    @staticmethod
    def hybrid_search_secure(db_path: str, password: str, query_embedding,
                             bm25_query: str = "", top_k: int = 10):
        if _HAS_SECRET:
            try:
                return _batch.secret.hybrid_search_secure(
                    db_path, password, query_embedding, bm25_query, top_k)
            except TypeError:
                pass
        return _base().hybrid_search_secure(
            db_path, password, query_embedding, bm25_query, top_k)

    @staticmethod
    def fetch_all_listings_secure(db_path: str, password: str):
        if _HAS_SECRET:
            try:
                return _batch.secret.fetch_all_listings_secure(db_path, password)
            except TypeError:
                pass
        return _base().fetch_all_listings_secure(db_path, password)

    @staticmethod
    def delete_listing_secure(db_path: str, password: str, listing_id: str) -> bool:
        if _HAS_SECRET:
            try:
                return _batch.secret.delete_listing_secure(
                    db_path, password, listing_id)
            except TypeError:
                pass
        return _base().delete_listing_secure(db_path, password, listing_id)

    @staticmethod
    def fetch_listings_as_arrow_pointers(db_path: str, password: str):
        if _HAS_SECRET:
            try:
                return _batch.secret.fetch_listings_as_arrow_pointers(
                    db_path, password)
            except TypeError:
                pass
        return _base().fetch_listings_as_arrow_pointers(db_path, password)

    # ------------------------------------------------------------------
    # Phase 5 — HTTP request sequencing
    # ------------------------------------------------------------------

    @staticmethod
    def run_web_requests_sequence(config_json: str, callback_obj) -> str:
        if _HAS_WEB:
            try:
                return _batch.web.run_web_requests_sequence(
                    config_json, callback_obj)
            except Exception:
                pass
        return _base().run_web_requests_sequence(config_json, callback_obj)


# ---------------------------------------------------------------------------
# Module-level __getattr__ — proxies any name not defined here to Rust base
# ---------------------------------------------------------------------------

def __getattr__(name: str):
    return getattr(_base(), name)
