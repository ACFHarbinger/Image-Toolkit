"""Tests for ContextInspectorPanel (§2.38, #539)."""

from __future__ import annotations

import pytest
from gui.src.components.inspector import ContextInspectorPanel
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.events import (
    EventHub,
    FilterByTagIntent,
    InspectImageIntent,
    NavigateIntent,
    SelectionChangedFact,
    ToggleInspectorIntent,
)

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
        assert not panel.isVisible()

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
        hub = EventHub(q_app)
        panel = ContextInspectorPanel(event_hub=hub)

        # 1. InspectImageIntent
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
        assert panel.exif_table.rowCount() == 1

        # 2. ToggleInspectorIntent
        hub.publish(ToggleInspectorIntent(origin="test", visible=False))
        assert not panel.isVisible()
        hub.publish(ToggleInspectorIntent(origin="test", visible=True))
        assert panel.isVisible()
        hub.publish(ToggleInspectorIntent(origin="test", visible=None))
        assert not panel.isVisible()

        # 3. SelectionChangedFact
        hub.publish(
            SelectionChangedFact(
                origin="test",
                paths=("/tmp/miku.png",),
                active_path="/tmp/miku.png",
                resolution=(1000, 1000),
            )
        )
        assert panel.filename_label.text() == "miku.png"
        assert panel.res_badge.text() == "1000 × 1000"

        # Empty selection clears context
        hub.publish(SelectionChangedFact(origin="test", paths=(), active_path=None))
        assert panel.filename_label.text() == "--"

        # 4. Tag click publishes FilterByTagIntent and NavigateIntent
        filter_intents: list[FilterByTagIntent] = []
        nav_intents: list[NavigateIntent] = []
        hub.subscribe(FilterByTagIntent, filter_intents.append)
        hub.subscribe(NavigateIntent, nav_intents.append)

        panel.set_image_context("/tmp/art.png", tags={"character": ["Miku"]})
        panel._on_tag_chip_clicked("Miku")

        assert len(filter_intents) == 1
        assert filter_intents[0].module_id == "library.search"
        assert filter_intents[0].tag_name == "Miku"

        assert len(nav_intents) == 1
        assert nav_intents[0].module_id == "library.search"

    def test_module_context_binding(self, q_app):
        hub = EventHub(q_app)
        ctx = ModuleContext(event_hub=hub, services=ModuleServices())
        panel = ContextInspectorPanel(context=ctx)

        hub.publish(
            InspectImageIntent(
                origin="test",
                file_path="/tmp/ctx_art.webp",
                resolution=(800, 600),
            )
        )
        assert panel.filename_label.text() == "ctx_art.webp"
        assert panel.fmt_badge.text() == "WEBP"

    def test_close_button_publishes_intent(self, q_app):
        hub = EventHub(q_app)
        panel = ContextInspectorPanel(event_hub=hub)
        panel.show()
        assert panel.isVisible()

        toggle_intents: list[ToggleInspectorIntent] = []
        hub.subscribe(ToggleInspectorIntent, toggle_intents.append)

        panel.close_btn.click()
        assert not panel.isVisible()
        assert len(toggle_intents) == 1
        assert toggle_intents[0].visible is False
