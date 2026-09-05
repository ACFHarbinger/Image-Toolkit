"""Opt-in runtime-shell assembly for MainWindow (#515)."""

from __future__ import annotations

import json

from PySide6.QtWidgets import QWidget

from gui.src.components.navigation.shell_manager import ShellLayoutManager, ShellNavMode
from gui.src.modules import (
    LIBRARY_DATABASE_SERVICE,
    EventHub,
    LibraryDatabaseService,
    ModuleContext,
    ModuleRuntime,
    ModuleServices,
)
from gui.src.modules.application_catalog import build_application_catalog

RUNTIME_SHELL_PREFERENCE = "experimental_runtime_shell"
RUNTIME_SHELL_SESSION_KEY = "runtime_shell"


class _RuntimeShellMixin:
    """Own the experimental shell without changing the legacy shell path."""

    def _runtime_shell_enabled(self) -> bool:
        preferences = self.cached_creds.get("preferences", {})
        return preferences.get(RUNTIME_SHELL_PREFERENCE, False) is True

    def _create_runtime_shell(self, *, dropdown: bool, enable_manager: bool) -> QWidget:
        self.module_event_hub = EventHub(self)
        self.module_services = ModuleServices()
        self.module_services.register("vault_manager", self.vault_manager)
        self.library_database_service = LibraryDatabaseService(self.vault_manager)
        self.module_services.register(LIBRARY_DATABASE_SERVICE, self.library_database_service)
        self.module_catalog = build_application_catalog(
            dropdown=dropdown, enable_manager=enable_manager
        )
        self.module_context = ModuleContext(
            event_hub=self.module_event_hub,
            services=self.module_services,
            account_id=self.cached_creds.get("account_name"),
        )
        self.module_runtime = ModuleRuntime(self.module_catalog, self.module_context)
        self.runtime_shell_container = QWidget(self)
        self.shell_layout_manager = ShellLayoutManager(
            self.module_runtime, self.runtime_shell_container
        )
        self.shell_layout_manager.activate_module("system.convert")
        return self.runtime_shell_container

    def _restore_runtime_shell_session(self) -> None:
        """Restore the experimental shell's active route and layout mode."""
        preferences = self.cached_creds.get("preferences", {})
        if not preferences.get("restore_last_tab", False):
            return
        saved = self.cached_creds.get("session_recovery_data", {}).get(RUNTIME_SHELL_SESSION_KEY, {})
        module_id = saved.get("active_module_id")
        if not isinstance(module_id, str) or self.module_catalog.get(module_id) is None:
            return
        mode = saved.get("nav_mode")
        if mode in (ShellNavMode.RAIL.value, ShellNavMode.TOP_BAR.value):
            self.shell_layout_manager.set_nav_mode(ShellNavMode(mode))
        self.shell_layout_manager.activate_module(module_id)

    def _save_runtime_shell_session(self) -> None:
        """Persist only shell state; individual modules continue to own their data."""
        if self.vault_manager is None or getattr(self.vault_manager, "is_guest", False) is True:
            return
        preferences = self.cached_creds.get("preferences", {})
        if not (
            preferences.get("restore_last_tab", False)
            or preferences.get("session_recovery_level", "None") != "None"
        ):
            return
        try:
            credentials = self.vault_manager.load_account_credentials()
            recovery = dict(credentials.get("session_recovery_data", {}))
            recovery[RUNTIME_SHELL_SESSION_KEY] = {
                "active_module_id": self.module_runtime.active_module_id,
                "nav_mode": self.shell_layout_manager.nav_mode.value,
            }
            credentials["session_recovery_data"] = recovery
            self.vault_manager.save_data(json.dumps(credentials))
            self.cached_creds = credentials
        except Exception as exc:
            print(f"Warning: Failed to save runtime shell session: {exc}")


__all__ = ["RUNTIME_SHELL_PREFERENCE", "RUNTIME_SHELL_SESSION_KEY", "_RuntimeShellMixin"]
