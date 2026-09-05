"""Tests for ContextInspectorPanel (§2.38)."""

from __future__ import annotations

import pytest
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

    def test_event_hub_integration(self, q_app):
        from gui.src.modules.events import (
            EventHub,
            InspectImageIntent,
            NavigateIntent,
            SelectionChangedFact,
            ToggleInspectorIntent,
        )

        hub = EventHub(q_app)
        panel = ContextInspectorPanel(event_hub=hub)

        # InspectImageIntent
        hub.publish(
            InspectImageIntent(
                origin="gallery",
                file_path="/tmp/art.png",
                resolution=(1920, 1080),
                tags=(("character", ("Hatsune Miku",)),),
                metadata=(("Rating", "Safe"),),
            )
        )
        assert panel.filename_label.text() == "art.png"
        assert panel.res_badge.text() == "1920 × 1080"
        assert panel.fmt_badge.text() == "PNG"

        # ToggleInspectorIntent
        hub.publish(ToggleInspectorIntent(origin="test", visible=False))
        assert not panel.isVisible()
        hub.publish(ToggleInspectorIntent(origin="test", visible=True))
        assert panel.isVisible()

        # SelectionChangedFact
        hub.publish(SelectionChangedFact(origin="test", paths=("/tmp/miku.png",), active_path="/tmp/miku.png"))
        assert panel.filename_label.text() == "miku.png"

        # Tag click publishes NavigateIntent
        nav_intents = []
        hub.subscribe(NavigateIntent, nav_intents.append)

        panel.set_image_context("/tmp/art.png", tags={"character": ["Miku"]})
        panel._on_tag_chip_clicked("Miku")
        assert len(nav_intents) == 1
        assert nav_intents[0].module_id == "lib.search"
        assert nav_intents[0].state == (("query", "Miku"),)
