"""Tests for ContextInspectorPanel (§2.38)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.components.inspector import ContextInspectorPanel

pytestmark = pytest.mark.gui


class TestContextInspectorPanel:
    def test_initial_state_and_clear(self, q_app):
        panel = ContextInspectorPanel()
        assert "INSPECTOR" in panel.title_label.text()
        assert "--" in panel.filename_label.text()

        collapsed = []
        panel.collapse_requested.connect(lambda: collapsed.append(True))
        panel.close_btn.click()
        assert collapsed == [True]

    def test_set_image_context(self, q_app):
        panel = ContextInspectorPanel()

        tags = {
            "character": ["Rem", "Ram"],
            "artist": ["ArtistA"],
        }
        meta = {
            "Camera": "Virtual",
            "Model": "SDXL Anime",
        }

        panel.set_image_context(
            file_path="/tmp/sample_anime.png",
            resolution=(3840, 2160),
            tags=tags,
            metadata=meta,
        )

        assert panel.filename_label.text() == "sample_anime.png"
        assert panel.res_badge.text() == "3840 × 2160"
        assert panel.fmt_badge.text() == "PNG"
        assert panel.exif_table.rowCount() == 2

        # Clear
        panel.clear_context()
        assert panel.filename_label.text() == "--"
        assert panel.exif_table.rowCount() == 0
