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
        self._runtime_shell_disposed = False
        # Codex #538 combined review (HIGH, then re-review): calling
        # activate_module() here ran synchronously during __init__, before
        # the container was even added to MainWindow's layout -- the exact
        # "construction creates a descriptor handle" defect the #533/#538
        # zero-factory-at-construction contract exists to prevent. Defer the
        # single approved first activation to the next event-loop turn.
        #
        # A bare QTimer.singleShot(0, ...) isn't retained or cancelable: if
        # the shell is disposed before that turn runs (a close/tray-Quit
        # during startup), the queued callback still fires and would
        # recreate Convert *after* clear_mounted()/ModuleRuntime.dispose().
        # Retain a real, stoppable QTimer *and* guard the callback with an
        # explicit disposed flag -- belt-and-suspenders, matching the
        # weakref+destroyed double-guard pattern WindowManager (#528) uses
        # for the same class of "did this already go away" race.
        self._initial_activation_timer = QTimer(self)
        self._initial_activation_timer.setSingleShot(True)
        self._initial_activation_timer.timeout.connect(self._activate_initial_runtime_module)
        self._initial_activation_timer.start(0)
        return self.runtime_shell_container

    def _activate_initial_runtime_module(self) -> None:
        """Deferred first activation — runs after construction, not during it."""
        if getattr(self, "_runtime_shell_disposed", False):
            return
        manager = getattr(self, "shell_layout_manager", None)
        if manager is not None:
            manager.activate_module("system.convert")

    def _dispose_runtime_shell(self) -> None:
        self._runtime_shell_disposed = True
        timer = getattr(self, "_initial_activation_timer", None)
        if timer is not None:
            timer.stop()
        manager = getattr(self, "shell_layout_manager", None)
        if manager is not None:
            manager.clear_mounted()
        runtime = getattr(self, "module_runtime", None)
        if runtime is not None:
            runtime.dispose()

    def _toggle_context_inspector(self) -> None:
        """Publish ToggleInspectorIntent across EventHub."""
        hub = getattr(self, "module_event_hub", None)
        if hub is not None:
            from gui.src.modules.events import ToggleInspectorIntent

            hub.publish(ToggleInspectorIntent(origin="main_window"))


__all__ = ["_RuntimeShellMixin"]
