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

    # Phase 9: web extensions
    run_board_crawler              = staticmethod(lambda *a, **kw: _base.web.run_board_crawler(*a, **kw))
    run_sync                       = staticmethod(lambda *a, **kw: _base.web.run_sync(*a, **kw))
    run_reverse_image_search       = staticmethod(lambda *a, **kw: _base.web.run_reverse_image_search(*a, **kw))
    run_image_crawler              = staticmethod(lambda *a, **kw: _base.web.run_image_crawler(*a, **kw))

    # Phase 8: core
    convert_single_image           = staticmethod(lambda *a, **kw: _base.core.convert_single_image(*a, **kw))
    convert_image_batch            = staticmethod(lambda *a, **kw: _base.core.convert_image_batch(*a, **kw))
    convert_video                  = staticmethod(lambda *a, **kw: _base.core.convert_video(*a, **kw))
    get_files_by_extension         = staticmethod(lambda *a, **kw: _base.core.get_files_by_extension(*a, **kw))
    delete_files_by_extensions     = staticmethod(lambda *a, **kw: _base.core.delete_files_by_extensions(*a, **kw))
    delete_path                    = staticmethod(lambda *a, **kw: _base.core.delete_path(*a, **kw))
    find_duplicate_images          = staticmethod(lambda *a, **kw: _base.core.find_duplicate_images(*a, **kw))
    find_similar_images_phash      = staticmethod(lambda *a, **kw: _base.core.find_similar_images_phash(*a, **kw))
    merge_images_horizontal        = staticmethod(lambda *a, **kw: _base.core.merge_images_horizontal(*a, **kw))
    merge_images_vertical          = staticmethod(lambda *a, **kw: _base.core.merge_images_vertical(*a, **kw))
    merge_images_grid              = staticmethod(lambda *a, **kw: _base.core.merge_images_grid(*a, **kw))
    set_wallpaper_gnome            = staticmethod(lambda *a, **kw: _base.core.set_wallpaper_gnome(*a, **kw))
    evaluate_kde_script            = staticmethod(lambda *a, **kw: _base.core.evaluate_kde_script(*a, **kw))

    # Phase 10: utils
    run_legacy_migration           = staticmethod(lambda *a, **kw: _base.utils.run_legacy_migration(*a, **kw))
    run_slideshow_daemon           = staticmethod(lambda *a, **kw: _base.utils.run_slideshow_daemon(*a, **kw))

    # Phase 11: math (submodule pass-through)
    @staticmethod
    def math_distance():   return _base.math.distance
    @staticmethod
    def math_stats():      return _base.math.stats
    @staticmethod
    def math_information(): return _base.math.information
    @staticmethod
    def math_graph():      return _base.math.graph
    @staticmethod
    def math_linalg():     return _base.math.linalg
    @staticmethod
    def math_dim_reduce(): return _base.math.dim_reduce


def __getattr__(name: str) -> Any:
    return getattr(_base, name)
