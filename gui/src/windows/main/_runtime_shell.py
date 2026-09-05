"""Opt-in runtime-shell assembly for MainWindow (#536)."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from gui.src.components.navigation.shell_manager import ShellLayoutManager
from gui.src.modules import (
    LIBRARY_DATABASE_SERVICE,
    EventHub,
    LibraryDatabaseService,
    ModuleContext,
    ModuleRuntime,
    ModuleServices,
    build_application_catalog,
    runtime_shell_enabled,
)
from gui.src.preferences import PreferenceStore


class _RuntimeShellMixin:
    """Own the experimental shell without changing the legacy shell path."""

    def _runtime_shell_enabled(self) -> bool:
        return runtime_shell_enabled(PreferenceStore.instance())

    def _create_runtime_shell(self, *, dropdown: bool, enable_manager: bool) -> QWidget:
        preference_store = PreferenceStore.instance()
        self.module_event_hub = EventHub(self)
        self.module_services = ModuleServices()
        self.module_services.register("vault_manager", self.vault_manager)
        self.library_database_service = LibraryDatabaseService(self.vault_manager)
        self.module_services.register(LIBRARY_DATABASE_SERVICE, self.library_database_service)
        self.module_catalog = build_application_catalog(
            dropdown=dropdown,
            enable_manager=enable_manager,
            preference_store=preference_store,
        )
        self.module_context = ModuleContext(
            event_hub=self.module_event_hub,
            services=self.module_services,
            preference_store=preference_store,
            account_id=self.cached_creds.get("account_name"),
        )
        self.module_runtime = ModuleRuntime(self.module_catalog, self.module_context)
        self.runtime_shell_container = QWidget(self)
        self.shell_layout_manager = ShellLayoutManager(
            self.module_runtime, self.runtime_shell_container
        )
        # Codex #538 combined review (HIGH): calling activate_module() here ran
        # synchronously during __init__, before the container was even added to
        # MainWindow's layout — the exact "construction creates a descriptor
        # handle" defect the #533/#538 zero-factory-at-construction contract
        # exists to prevent. Defer the single approved first activation to the
        # next event-loop turn (after __init__ returns and the widget is part
        # of a shown window), not from inside construction itself.
        QTimer.singleShot(0, self._activate_initial_runtime_module)
        return self.runtime_shell_container

    def _activate_initial_runtime_module(self) -> None:
        """Deferred first activation — runs after construction, not during it."""
        manager = getattr(self, "shell_layout_manager", None)
        if manager is not None:
            manager.activate_module("system.convert")

    def _dispose_runtime_shell(self) -> None:
        manager = getattr(self, "shell_layout_manager", None)
        if manager is not None:
            manager.clear_mounted()
        runtime = getattr(self, "module_runtime", None)
        if runtime is not None:
            runtime.dispose()


__all__ = ["_RuntimeShellMixin"]
