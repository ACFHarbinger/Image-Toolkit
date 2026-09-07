"""Settings-facing contract tests for the secondary-window service (#558)."""

from __future__ import annotations

from gui.src.windows.window_service import WindowService
from PySide6.QtCore import QByteArray


class _ExtractionTab:
    def __init__(self) -> None:
        self.history_reloaded = 0
        self.recent_updated = 0

    def _load_extraction_history(self) -> None:
        self.history_reloaded += 1

    def _update_recent_extractions_ui(self) -> None:
        self.recent_updated += 1


class _ApplicationWindow:
    def __init__(self) -> None:
        self.cached_creds = {
            "preferences": {"app_zoom": 0},
            "active_tab_configs": {"Convert": "existing"},
        }
        self.all_tabs = {"Video": {"Extractor": _ExtractionTab()}}
        self.calls: list[tuple] = []
        self.vault_manager = object()

    def zoom_in(self) -> None:
        self.cached_creds["preferences"]["app_zoom"] = 10

    def set_minimize_to_tray(self, enabled: bool) -> None:
        self.calls.append(("tray", enabled))

    def set_application_theme(self, theme: str) -> None:
        self.calls.append(("theme", theme))

    def _apply_startup_preferences(self) -> None:
        self.calls.append(("startup",))

    def _apply_active_tab_configs(self, *, previous_configs: dict) -> None:
        self.calls.append(("tabs", previous_configs))

    def saveGeometry(self) -> QByteArray:
        return QByteArray(b"geometry")


def test_settings_service_updates_application_without_exposing_window(q_app):
    window = _ApplicationWindow()
    service = WindowService(window)

    assert service.vault_manager is window.vault_manager
    assert service.zoom_in() == 10

    credentials = {"preferences": {"app_zoom": 10}, "active_tab_configs": {"Convert": "new"}}
    service.update_settings(credentials, minimize_to_tray=True, theme="light")

    assert window.cached_creds is credentials
    assert window.calls == [
        ("tray", True),
        ("theme", "light"),
        ("startup",),
        ("tabs", {"Convert": "existing"}),
    ]


def test_settings_service_handles_geometry_and_history_tabs(q_app):
    window = _ApplicationWindow()
    service = WindowService(window)

    assert bytes(service.save_geometry()) == b"geometry"
    service.reload_extraction_history()

    tab = window.all_tabs["Video"]["Extractor"]
    assert (tab.history_reloaded, tab.recent_updated) == (1, 1)


def test_settings_service_is_safe_without_application_window(q_app):
    service = WindowService()

    assert service.available is False
    assert service.vault_manager is None
    assert service.all_tabs() == {}
    assert service.zoom_in() is None
    service.reload_extraction_history()
