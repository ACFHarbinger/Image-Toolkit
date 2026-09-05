"""Opt-in runtime-shell assembly for MainWindow (#515)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from gui.src.components.navigation.shell_manager import ShellLayoutManager
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


__all__ = ["RUNTIME_SHELL_PREFERENCE", "_RuntimeShellMixin"]
