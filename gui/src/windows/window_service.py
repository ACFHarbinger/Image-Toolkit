"""Narrow application-window operations used by secondary windows.

Secondary windows should not retain or inspect ``MainWindow`` directly.  This
adapter centralizes the small set of application operations they require and
also gives headless settings tests a safe no-op implementation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QByteArray


class WindowService:
    """Expose application-window behavior without coupling callers to its class."""

    def __init__(self, application_window: Any | None = None) -> None:
        self._application_window = application_window

    @property
    def vault_manager(self) -> Any | None:
        return getattr(self._application_window, "vault_manager", None)

    @property
    def available(self) -> bool:
        return self._application_window is not None

    def zoom_in(self) -> int | None:
        return self._zoom("zoom_in")

    def zoom_out(self) -> int | None:
        return self._zoom("zoom_out")

    def _zoom(self, method_name: str) -> int | None:
        method = getattr(self._application_window, method_name, None)
        if not callable(method):
            return None
        method()
        return self.preferences().get("app_zoom")

    def preferences(self) -> dict[str, Any]:
        credentials = getattr(self._application_window, "cached_creds", {}) or {}
        preferences = credentials.get("preferences", {}) if isinstance(credentials, Mapping) else {}
        return dict(preferences) if isinstance(preferences, Mapping) else {}

    def preview_appearance(self, theme: str, preferences: dict[str, Any]) -> None:
        window = self._application_window
        if window is None:
            return
        credentials = getattr(window, "cached_creds", None)
        if not isinstance(credentials, dict):
            credentials = {}
            window.cached_creds = credentials
        credentials["preferences"] = dict(preferences)
        self._call("set_application_theme", theme)
        self._call("update")

    def update_settings(
        self, credentials: dict[str, Any], *, minimize_to_tray: bool, theme: str
    ) -> None:
        window = self._application_window
        if window is None:
            return
        cached = getattr(window, "cached_creds", {}) or {}
        previous: Any = {}
        if isinstance(cached, Mapping):
            previous = cached.get("active_tab_configs", {})
        # #548: install the new snapshot through _refresh_account_credentials
        # (attach_vault_credentials() + cached_creds in one step) rather than
        # writing cached_creds directly -- a direct write here would race a
        # stale VaultPreferenceAdapter snapshot the same way #548 fixed for
        # Settings' own save path.
        refresh = getattr(window, "_refresh_account_credentials", None)
        if callable(refresh):
            refresh(credentials)
        else:
            window.cached_creds = credentials
        self._call("set_minimize_to_tray", minimize_to_tray)
        self._call("set_application_theme", theme)
        self._call("_apply_startup_preferences")
        self._call("_apply_active_tab_configs", previous_configs=dict(previous or {}))

    def restart_application(self) -> bool:
        method = getattr(self._application_window, "restart_application", None)
        if not callable(method):
            return False
        method()
        return True

    def update_header(self) -> None:
        self._call("update_header")

    def save_geometry(self) -> QByteArray | None:
        result = self._call("saveGeometry")
        return result if isinstance(result, QByteArray) else None

    def restore_geometry(self, geometry: QByteArray) -> bool:
        return self._call("restoreGeometry", geometry)

    def all_tabs(self) -> dict[str, dict[str, Any]]:
        tabs = getattr(self._application_window, "all_tabs", {})
        return tabs if isinstance(tabs, dict) else {}

    def reload_extraction_history(self) -> None:
        for category in self.all_tabs().values():
            for tab in category.values():
                reload_history = getattr(tab, "_load_extraction_history", None)
                if callable(reload_history):
                    reload_history()
                update_recent = getattr(tab, "_update_recent_extractions_ui", None)
                if callable(update_recent):
                    update_recent()

    def apply_theme_pack(self, pack: Any) -> None:
        self._call("apply_theme_pack", pack)

    def _call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self._application_window, method_name, None)
        return method(*args, **kwargs) if callable(method) else None


__all__ = ["WindowService"]
