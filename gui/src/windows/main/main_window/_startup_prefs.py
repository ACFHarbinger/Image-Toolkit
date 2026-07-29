"""Vault-preference application to gallery tabs at startup (GUI/UX §2.16).

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import copy
import inspect
from pathlib import Path
from typing import Any

from backend.src.constants import LOCAL_SOURCE_PATH

from ....utils.lru_image_cache import LRUImageCache


class _StartupPrefsMixin:
    """Applies vault-stored preferences (thumbnail size, caches, dirs, ...) to every tab."""

    def _sanitize_config_if_needed(self, config_data: dict) -> dict:
        """Removes local directory/file path fields from tab configurations if restore_last_dir is False."""
        if not config_data or not isinstance(config_data, dict):
            return config_data
        if not self.cached_creds:
            return config_data
        prefs = self.cached_creds.get("preferences", {})
        if prefs.get("restore_last_dir", True):
            return config_data

        sanitized = copy.deepcopy(config_data)

        # Clear or reset fields representing local directories or paths
        keys_to_clear = [
            "scan_directory",
            "source_directory",
            "reference_path",
            "extraction_directory",
            "download_dir",
            "screenshot_dir",
            "local_path",
            "input_path",
            "output_path",
            "scan_dir",
            "lora_path",
            "checkpoint_path",
            "image_path",
        ]
        for key in keys_to_clear:
            if key in sanitized:
                sanitized[key] = ""
        if "video_path" in sanitized:
            sanitized["video_path"] = ""
        if "active_videos_config" in sanitized:
            sanitized["active_videos_config"] = {}

        return sanitized

    def _apply_active_tab_configs(self) -> None:
        """Applies the active configuration for each tab dynamically."""
        active_configs = self.cached_creds.get("active_tab_configs", {})
        saved_tab_configs = self.cached_creds.get("tab_configurations", {})

        for _category, tabs_in_category in self.all_tabs.items():
            for tab_instance in tabs_in_category.values():
                tab_class_name = type(tab_instance).__name__

                if tab_class_name in active_configs:
                    config_name = active_configs[tab_class_name]

                    if tab_class_name in saved_tab_configs and config_name in saved_tab_configs[tab_class_name]:
                        config_data = saved_tab_configs[tab_class_name][config_name]
                        config_data = self._sanitize_config_if_needed(config_data)

                        if hasattr(tab_instance, "set_config") and callable(tab_instance.set_config):
                            try:
                                sig = inspect.signature(tab_instance.set_config)
                                if "quiet" in sig.parameters:
                                    tab_instance.set_config(config_data, quiet=True)  # pyrefly: ignore [unexpected-keyword]
                                else:
                                    tab_instance.set_config(config_data)
                                print(f"Applied active config '{config_name}' to {tab_class_name}")
                            except Exception as e:
                                print(f"Error applying config to {tab_class_name}: {e}")

    def _apply_startup_preferences(self) -> None:  # noqa: C901
        """Apply vault-stored preferences to gallery tabs at startup (GUI/UX §2.16 A/B/C/E)."""
        prefs = self.cached_creds.get("preferences", {})
        if not prefs:
            return

        # §2.16A — thumbnail size and page size
        thumb_size = int(prefs.get("thumbnail_size", 180))
        page_size = int(prefs.get("page_size", 100))
        # §2.16B — LRU cache sizes
        found_cache = int(prefs.get("found_cache_maxsize", 300))
        selected_cache = int(prefs.get("selected_cache_maxsize", 200))
        initial_cache = int(prefs.get("initial_cache_maxsize", 300))

        # NEW: Extractor seek interval and recent extractions count
        extractor_seek_ms = int(prefs.get("extractor_seek_ms", 100))
        recent_extractions_count = int(prefs.get("recent_extractions_count", 10))
        extractor_time_format = prefs.get("extractor_time_format", "m:s:ms")

        # §2.9G — recent (browsed) directories MRU limit
        recent_dirs_count = int(prefs.get("recent_dirs_count", 10))

        restore_last_dir = prefs.get("restore_last_dir", True)

        default_dir = prefs.get("default_open_dir", "").strip() or LOCAL_SOURCE_PATH
        if default_dir and "Downloads/data" in default_dir:
            default_dir = default_dir.replace("Downloads/data", "Downloads/Data")

        for cat_tabs in self.all_tabs.values():
            for tab in cat_tabs.values():
                # Thumbnail and page size (§2.16A)
                if hasattr(tab, "thumbnail_size"):
                    tab.thumbnail_size = thumb_size  # pyrefly: ignore [missing-attribute]
                    if hasattr(tab, "padding_width"):
                        tab.approx_item_width = thumb_size + tab.padding_width + 20  # pyrefly: ignore [missing-attribute]
                for attr in ("found_page_size", "selected_page_size", "page_size"):
                    if hasattr(tab, attr):
                        setattr(tab, attr, page_size)
                # LRU caches (§2.16B)
                if hasattr(tab, "_found_pixmap_cache"):
                    tab._found_pixmap_cache = LRUImageCache(maxsize=found_cache)  # pyrefly: ignore [missing-attribute]
                if hasattr(tab, "_selected_pixmap_cache"):
                    tab._selected_pixmap_cache = LRUImageCache(maxsize=selected_cache)  # pyrefly: ignore [missing-attribute]
                if hasattr(tab, "_initial_pixmap_cache"):
                    tab._initial_pixmap_cache = LRUImageCache(maxsize=initial_cache)  # pyrefly: ignore [missing-attribute]

                # Recent (browsed) directories MRU limit (§2.9G) — every gallery
                # tab/subtab inherits AbstractGalleryBase.recent_dirs_limit,
                # consumed by _add_recent_dir() as its default max_entries.
                # ConvertTab is a plain QWidget wrapper around FormatSubTab /
                # CodecSubTab / SamplerSubTab, so those nested subtabs (the
                # actual _add_recent_dir callers) must be reached explicitly.
                for _rd_obj in (
                    tab,
                    getattr(tab, "format_subtab", None),
                    getattr(tab, "codec_subtab", None),
                    getattr(tab, "sampler_subtab", None),
                ):
                    if _rd_obj is not None and hasattr(_rd_obj, "recent_dirs_limit"):
                        _rd_obj.recent_dirs_limit = recent_dirs_count  # pyrefly: ignore [missing-attribute]

                # Update directory configuration for the tab
                for obj in (tab, getattr(tab, "format_tab", None)):
                    if obj is not None:
                        obj_any: Any = obj
                        if hasattr(obj_any, "last_browsed_scan_dir"):
                            if hasattr(obj_any, "_load_last_dir"):
                                obj_any.last_browsed_scan_dir = obj_any._load_last_dir(default_dir, main_win=self)
                            elif (
                                not restore_last_dir
                                or getattr(obj_any, "last_browsed_scan_dir", "") == LOCAL_SOURCE_PATH
                                or not getattr(obj_any, "last_browsed_scan_dir", "")
                            ):
                                obj_any.last_browsed_scan_dir = default_dir
                            if obj_any.last_browsed_scan_dir and "Downloads/data" in obj_any.last_browsed_scan_dir:
                                obj_any.last_browsed_scan_dir = obj_any.last_browsed_scan_dir.replace(
                                    "Downloads/data", "Downloads/Data"
                                )
                        if hasattr(obj_any, "last_browsed_dir"):
                            if hasattr(obj_any, "_load_last_dir"):
                                obj_any.last_browsed_dir = obj_any._load_last_dir(default_dir, main_win=self)
                            elif (
                                not restore_last_dir
                                or getattr(obj_any, "last_browsed_dir", "") == LOCAL_SOURCE_PATH
                                or not getattr(obj_any, "last_browsed_dir", "")
                            ):
                                obj_any.last_browsed_dir = default_dir
                            if obj_any.last_browsed_dir and "Downloads/data" in obj_any.last_browsed_dir:
                                obj_any.last_browsed_dir = obj_any.last_browsed_dir.replace(
                                    "Downloads/data", "Downloads/Data"
                                )

                # ExtractorTab specific directory update
                if type(tab).__name__ == "ExtractorTab":
                    tab_any: Any = tab
                    tab_any.extraction_dir = Path(default_dir) / "Frames"
                    tab_any.extraction_dir.mkdir(parents=True, exist_ok=True)
                    tab_any.last_browsed_extraction_dir = tab_any._load_last_extraction_dir(str(tab_any.extraction_dir))
                    if tab_any.last_browsed_extraction_dir and "Downloads/data" in tab_any.last_browsed_extraction_dir:
                        tab_any.last_browsed_extraction_dir = tab_any.last_browsed_extraction_dir.replace(
                            "Downloads/data", "Downloads/Data"
                        )

                # Apply Extractor seek interval
                if hasattr(tab, "wheel_seek_ms"):
                    tab.wheel_seek_ms = extractor_seek_ms  # pyrefly: ignore [missing-attribute]

                # Apply Extractor recent limit
                if hasattr(tab, "recent_extractions_limit"):
                    tab.recent_extractions_limit = recent_extractions_count  # pyrefly: ignore [missing-attribute]
                    if hasattr(tab, "_apply_new_extractions_limit") and callable(tab._apply_new_extractions_limit):
                        tab._apply_new_extractions_limit()

                # Apply Extractor queue setting
                if hasattr(tab, "extraction_queue_enabled"):
                    tab.extraction_queue_enabled = prefs.get(  # pyrefly: ignore [missing-attribute]
                        "enable_extraction_queue", False
                    )
                    if hasattr(tab, "_on_queue_toggle_changed") and callable(tab._on_queue_toggle_changed):
                        tab._on_queue_toggle_changed()

                # Apply Extractor time display format
                if hasattr(tab, "time_display_format"):
                    tab.time_display_format = extractor_time_format  # pyrefly: ignore [missing-attribute]
                    if hasattr(tab, "refresh_time_display") and callable(tab.refresh_time_display):
                        tab.refresh_time_display()

        # §2.16C — startup category
        startup_cat = prefs.get("startup_category", "")
        if startup_cat and startup_cat in self.all_tabs:
            self.command_combo.setCurrentText(startup_cat)

        # §2.16E — slideshow defaults to WallpaperTab
        if hasattr(self, "wallpaper_tab"):
            wt = self.wallpaper_tab
            try:
                wt.interval_min_spinbox.setValue(  # pyrefly: ignore [missing-attribute]
                    int(prefs.get("slideshow_interval_min", 5))
                )
                wt.interval_sec_spinbox.setValue(  # pyrefly: ignore [missing-attribute]
                    int(prefs.get("slideshow_interval_sec", 0))
                )
                order = prefs.get("slideshow_order", "Sequential")
                wt.playback_order_combo.setCurrentText(order)  # pyrefly: ignore [missing-attribute]
            except Exception:
                pass

        # §2.16F — logging preferences (GUI/UX §2.9F, issue #48). Local import:
        # backend.src.app imports from gui.src.windows.main, so a module-level
        # import here would be circular.
        try:
            from backend.src.app import _reconfigure_logging
            _reconfigure_logging(
                prefs.get("log_level", "INFO"),
                bool(prefs.get("file_logging_enabled", False)),
            )
        except Exception:
            pass


__all__ = ["_StartupPrefsMixin"]
