"""Tests for §5.14C -- AppConfig (gui/src/utils/app_config.py).

Verifies the unified snapshot merges ASP env-var state and GUI QSettings
state correctly, that known static GUI keys are excluded from
gui_dynamic_keys (not double-listed), and that __str__ produces an
introspectable dump.
"""

import pytest

pytestmark = pytest.mark.gui


class TestAppConfigCapture:
    def test_capture_includes_every_asp_schema_key(self, q_app, monkeypatch):
        from backend.src.animation.core.config import asp_schema
        from gui.src.utils.app_config import AppConfig

        monkeypatch.setenv("ASP_HOLD_THRESHOLD", "0.05")
        config = AppConfig.capture()

        assert set(config.asp.keys()) == set(asp_schema().keys())
        assert config.asp["ASP_HOLD_THRESHOLD"] == "0.05"

    def test_capture_includes_known_gui_fields(self, q_app, monkeypatch):
        from gui.src.utils.app_config import AppConfig
        from gui.src.windows.settings.app_settings import AppSettings

        monkeypatch.setattr(AppSettings, "recursive_scan", classmethod(lambda cls: False))
        monkeypatch.setattr(AppSettings, "favourite_directories", classmethod(lambda cls: ["/a", "/b"]))
        monkeypatch.setattr(AppSettings, "mal_fetch_method", classmethod(lambda cls: "scrape"))
        monkeypatch.setattr(AppSettings, "mainwindow_geometry", classmethod(lambda cls: None))
        monkeypatch.setattr(AppSettings, "all_keys", classmethod(lambda cls: []))

        config = AppConfig.capture()

        assert config.gui["recursive_scan"] is False
        assert config.gui["favourite_directories"] == ["/a", "/b"]
        assert config.gui["mal_fetch_method"] == "scrape"

    def test_known_static_keys_excluded_from_dynamic_keys(self, q_app, monkeypatch):
        from gui.src.utils.app_config import AppConfig
        from gui.src.windows.settings.app_settings import AppSettings

        monkeypatch.setattr(
            AppSettings,
            "all_keys",
            classmethod(
                lambda cls: [
                    "mainwindow/geometry",
                    "preferences/recursive_scan",
                    "session/WallpaperTab/last_dir",
                    "labels/foo.png",
                ]
            ),
        )

        config = AppConfig.capture()

        assert config.gui_dynamic_keys == ("labels/foo.png", "session/WallpaperTab/last_dir")

    def test_str_lists_all_sections(self, q_app, monkeypatch):
        from gui.src.utils.app_config import AppConfig
        from gui.src.windows.settings.app_settings import AppSettings

        monkeypatch.setattr(AppSettings, "all_keys", classmethod(lambda cls: ["session/Foo/bar"]))

        text = str(AppConfig.capture())

        assert "AppConfig snapshot:" in text
        assert "ASP pipeline (" in text
        assert "GUI static preferences (" in text
        assert "session/Foo/bar" in text
