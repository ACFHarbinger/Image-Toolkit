"""Regression test for #534: MainBackend's second construction path must
wire the shared EventHub into ListingsTab, not just _tab_registry.py's.

Codex's cross-review found `MainBackend` builds `self.module_event_hub`
but constructs `ListingsTab` without passing it, so a management-tab
`FilterByTagIntent(..., module_id="library.listings")` published on the
shared hub never reaches Listings -- it silently no-ops instead of
switching tabs and filtering.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gui.src.modules.events import FilterByTagIntent

pytestmark = pytest.mark.gui


def _make_main_backend(q_app):
    """Construct MainBackend with every *other* tab mocked out -- this test
    is about the ListingsTab/EventHub wiring specifically, not a full
    integration smoke test of all ~15 tabs."""
    vault_manager = MagicMock()
    vault_manager.is_guest = False
    vault_manager.load_account_credentials.return_value = {"account_name": "tester"}

    mocked_tab_names = (
        "ConvertTab",
        "DatabaseTab",
        "DriveSyncTab",
        "EntityReconTab",
        "ExtractorTab",
        "ImageCrawlTab",
        "MergeTab",
        "MetaCLIPInferenceTab",
        "R3GANEvaluateTab",
        "ReverseImageSearchTab",
        "ScanMetadataTab",
        "SearchTab",
        "SimilarityTab",
        "UnifiedGenerateTab",
        "UnifiedTrainTab",
        "WallpaperTab",
        "WebRequestsTab",
    )
    patches = [
        patch(f"gui.src.main_backend.{name}", return_value=MagicMock())
        for name in mocked_tab_names
    ]
    patches += [
        patch("gui.src.main_backend.StitchTabBackend", return_value=MagicMock()),
        patch("gui.src.main_backend.SettingsBackend", return_value=MagicMock()),
        patch("gui.src.main_backend.LogBackend", return_value=MagicMock()),
        patch("gui.src.main_backend.SlideshowBackend", return_value=MagicMock()),
    ]
    for p in patches:
        p.start()

    from gui.src.main_backend import MainBackend

    backend = MainBackend(vault_manager)

    for p in patches:
        p.stop()

    return backend


class TestMainBackendListingsWiring:
    def test_listings_tab_receives_the_shared_event_hub(self, q_app):
        backend = _make_main_backend(q_app)
        assert backend._listings_tab.vault_manager is backend.vault_manager

        # The real ListingsTab constructor only subscribes to
        # FilterByTagIntent when an event_hub is actually passed in -- if
        # MainBackend regresses back to omitting it, publishing on the
        # shared hub simply does nothing and this assertion fails.
        backend.module_event_hub.publish(
            FilterByTagIntent(
                origin="library.management",
                module_id="library.listings",
                tag_name="sky",
            )
        )

        assert (
            backend._listings_tab.tab_widget.currentWidget()
            is backend._listings_tab.series_listings
        )
        assert backend._listings_tab.series_listings.search_box.text() == "sky"
