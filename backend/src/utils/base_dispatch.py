"""
backend/src/utils/base_dispatch.py

Post-Phase-7 compatibility shim.

`import base` now resolves to the C++ pybind11 extension directly.
This module re-exports `base` as `NativeExt` for any callers that
imported from here, and provides a module-level __getattr__ so that
`from base_dispatch import foo` also works.

The dual-module dispatch logic (batch vs base fallback) was removed in
Phase 7 when the Rust base module was retired to archive/base_rust/.
"""

from __future__ import annotations
from typing import Any

import base as _base  # C++ pybind11 extension (Phase 7+)


class NativeExt:
    """Thin namespace alias for `base`. All attribute lookups delegate to it."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_base, name)

    load_image_batch               = staticmethod(lambda *a, **kw: _base.image.load_image_batch(*a, **kw))
    scan_files                     = staticmethod(lambda *a, **kw: _base.image.scan_files(*a, **kw))
    extract_video_thumbnails_batch = staticmethod(lambda *a, **kw: _base.video.extract_video_thumbnails_batch(*a, **kw))
    insert_listing_secure          = staticmethod(lambda *a, **kw: _base.secret.insert_listing_secure(*a, **kw))
    hybrid_search_secure           = staticmethod(lambda *a, **kw: _base.secret.hybrid_search_secure(*a, **kw))
    fetch_all_listings_secure      = staticmethod(lambda *a, **kw: _base.secret.fetch_all_listings_secure(*a, **kw))
    delete_listing_secure          = staticmethod(lambda *a, **kw: _base.secret.delete_listing_secure(*a, **kw))
    fetch_listings_as_arrow_pointers = staticmethod(lambda *a, **kw: _base.secret.fetch_listings_as_arrow_pointers(*a, **kw))
    run_web_requests_sequence      = staticmethod(lambda *a, **kw: _base.web.run_web_requests_sequence(*a, **kw))


def __getattr__(name: str) -> Any:
    return getattr(_base, name)
