"""Regression: _apply_startup_preferences must respect the user's saved
extraction directory instead of blindly forcing the default. Previously the
GIF/PNG files were written to ~/Downloads/Data/Media/Frames while the user's
chosen output dir stayed empty (they appeared in the gallery but not in the
actual output directory).
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from backend.src.constants import LOCAL_SOURCE_PATH

pytestmark = pytest.mark.gui


class _Harness:
    """Minimal stand-in for MainWindow exposing what
    _apply_startup_preferences touches for the ExtractorTab block."""

    def __init__(self, tab, prefs):
        self.cached_creds = {"preferences": prefs}
        self.all_tabs = {"Core": {"ExtractorTab": tab}}
        # _sanitize_config_if_needed is used only by recovery, not prefs
        self.command_combo = SimpleNamespace(currentText=lambda: "Core")
        self.tabs = SimpleNamespace(
            currentIndex=lambda: 0,
            tabText=lambda i: "ExtractorTab",
        )


class TestStartupExtractionDir:
    def _make_tab(self, tmp_path):
        from gui.src.elements.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.elements.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.elements.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
        return tab

    def test_uses_saved_extraction_dir_when_present(self, q_app, tmp_path, monkeypatch):
        """With a previously-browsed extraction dir saved in the session, the
        startup prefs must point extraction_dir at it (not the default)."""
        from gui.src.windows.main._startup_prefs import _StartupPrefsMixin

        tab = self._make_tab(tmp_path)
        saved_dir = tmp_path / "MyGifs"
        saved_dir.mkdir(parents=True, exist_ok=True)
        tab._save_last_extraction_dir(str(saved_dir))

        harness = _Harness(tab, {"thumbnail_size": 180})
        mixin = _StartupPrefsMixin()
        mixin.__dict__.update(harness.__dict__)

        mixin._apply_startup_preferences()

        assert tab.extraction_dir == saved_dir
        assert tab.line_edit_extract_dir.text() == str(saved_dir)

    def test_falls_back_to_default_when_no_saved_dir(self, q_app, tmp_path, monkeypatch):
        from gui.src.windows.main._startup_prefs import _StartupPrefsMixin

        tab = self._make_tab(tmp_path)
        # Ensure no stale saved dir from a previous test leaks in.
        tab.last_browsed_extraction_dir = ""
        monkeypatch.setattr(tab, "_load_last_extraction_dir", lambda *a, **k: "")

        harness = _Harness(tab, {"thumbnail_size": 180})
        mixin = _StartupPrefsMixin()
        mixin.__dict__.update(harness.__dict__)

        mixin._apply_startup_preferences()

        default = Path(LOCAL_SOURCE_PATH) / "Frames"
        assert tab.extraction_dir == default
