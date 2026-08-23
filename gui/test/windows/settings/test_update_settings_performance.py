"""Regression tests: updating settings must not freeze or re-scan unchanged tabs.

Bug: when clicking "Update settings", the application froze for several seconds because:
  1. _apply_active_tab_configs() unconditionally called set_config() on every tab
     in the application, triggering synchronous directory scans, video probing,
     and media reloads across all tabs.
  2. _apply_startup_preferences() unconditionally purges/re-instantiates LRU
     caches and re-scanned ExtractorTab's extraction directory from scratch.

Fix:
  1. _apply_active_tab_configs() accepts previous_configs and skips tabs whose
     active config name has not changed.
  2. _apply_startup_preferences() resizes LRU caches in-place (preserving cached
     pixmaps) and only updates ExtractorTab's extraction directory if it changed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from gui.src.utils.cache.lru_image_cache import LRUImageCache
from gui.src.windows.main._startup_prefs import _StartupPrefsMixin

pytestmark = pytest.mark.gui


class DummyTab:
    def __init__(self, name: str):
        self.name = name
        self.set_config_mock = MagicMock()
        self._found_pixmap_cache = LRUImageCache(maxsize=100)
        self._selected_pixmap_cache = LRUImageCache(maxsize=100)
        self._initial_pixmap_cache = LRUImageCache(maxsize=100)
        self.thumbnail_size = 180
        self.found_page_size = 100

    def set_config(self, config: dict, quiet: bool = False):
        self.set_config_mock(config, quiet=quiet)



class FormatSubTab(DummyTab):
    pass


class CodecSubTab(DummyTab):
    pass


class DummyExtractorTab(DummyTab):
    def __init__(self):
        super().__init__("ExtractorTab")
        self.extraction_dir = Path("/mock/frames")
        self.line_edit_extract_dir = MagicMock()
        self._refresh_extracted_stems_cache = MagicMock()
        self._load_existing_output_images = MagicMock()
        self._load_last_extraction_dir = MagicMock(return_value="/mock/frames")


class DummyMainWindow(_StartupPrefsMixin):
    def __init__(self):
        self.cached_creds = {
            "preferences": {
                "thumbnail_size": 200,
                "page_size": 50,
                "found_cache_maxsize": 400,
                "selected_cache_maxsize": 300,
                "initial_cache_maxsize": 400,
                "default_open_dir": "/mock/frames",
                "restore_last_dir": True,
            },
            "active_tab_configs": {
                "FormatSubTab": "Default",
                "CodecSubTab": "HighQuality",
            },
            "tab_configurations": {
                "FormatSubTab": {"Default": {"opt": 1}},
                "CodecSubTab": {"HighQuality": {"opt": 2}, "LowQuality": {"opt": 3}},
            },
        }
        self.format_tab = FormatSubTab("FormatSubTab")
        self.codec_tab = CodecSubTab("CodecSubTab")
        self.extractor_tab = DummyExtractorTab()
        self.all_tabs = {
            "Convert": {
                "Format": self.format_tab,
                "Codec": self.codec_tab,
            },
            "Extract": {
                "Extractor": self.extractor_tab,
            },
        }



class TestApplyActiveTabConfigsOptimization:
    def test_skips_unchanged_tab_configs(self, q_app):
        mw = DummyMainWindow()
        previous_configs = {
            "FormatSubTab": "Default",
            "CodecSubTab": "HighQuality",
        }

        # Apply with same previous configs -> no set_config calls
        mw._apply_active_tab_configs(previous_configs=previous_configs)
        mw.format_tab.set_config_mock.assert_not_called()
        mw.codec_tab.set_config_mock.assert_not_called()

    def test_applies_only_changed_tab_configs(self, q_app):
        mw = DummyMainWindow()
        mw.cached_creds["active_tab_configs"]["CodecSubTab"] = "LowQuality"
        previous_configs = {
            "FormatSubTab": "Default",
            "CodecSubTab": "HighQuality",
        }

        mw._apply_active_tab_configs(previous_configs=previous_configs)
        mw.format_tab.set_config_mock.assert_not_called()
        mw.codec_tab.set_config_mock.assert_called_once_with({"opt": 3}, quiet=True)

    def test_applies_all_when_previous_configs_is_none(self, q_app):
        mw = DummyMainWindow()
        mw._apply_active_tab_configs(previous_configs=None)
        mw.format_tab.set_config_mock.assert_called_once_with({"opt": 1}, quiet=True)
        mw.codec_tab.set_config_mock.assert_called_once_with({"opt": 2}, quiet=True)



class TestApplyStartupPreferencesOptimization:
    def test_resizes_lru_caches_in_place(self, q_app):
        mw = DummyMainWindow()
        orig_cache = mw.format_tab._found_pixmap_cache
        orig_cache["key1"] = "val1"

        mw._apply_startup_preferences()

        # Cache object should be the SAME instance, resized to 400, preserving existing entries
        assert mw.format_tab._found_pixmap_cache is orig_cache
        assert mw.format_tab._found_pixmap_cache.maxsize == 400
        assert "key1" in mw.format_tab._found_pixmap_cache

    def test_does_not_rescan_extractor_tab_if_dir_unchanged(self, q_app):
        mw = DummyMainWindow()
        with patch.object(Path, "exists", return_value=True):
            mw._apply_startup_preferences()

        mw.extractor_tab._refresh_extracted_stems_cache.assert_not_called()
        mw.extractor_tab._load_existing_output_images.assert_not_called()
