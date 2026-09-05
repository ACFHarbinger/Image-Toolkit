"""Lifecycle handles and lazy runtime for an app-owned module catalog."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from .catalog import PageDescriptor, RouteDescriptor, WorkspaceDescriptor
from .events import ModuleActivated, ModuleDeactivated

if TYPE_CHECKING:
    from .catalog import ModuleCatalog
    from .context import ModuleContext


class ModuleHandle(ABC):
    """A mounted page or workspace with an explicit lifecycle."""

    @property
    @abstractmethod
    def widget(self) -> QWidget:
        """Widget mounted by the shell."""

    def activate(self, route_key: str | None = None) -> None:
        """Make this handle active; workspace handles may select a route."""
        return None

    def deactivate(self) -> None:
        """Release active-only resources while retaining cached state."""
        return None

    def dispose(self) -> None:
        """Release resources permanently, such as at account-session end."""
        return None


class WidgetHandle(ModuleHandle):
    """Default lifecycle wrapper for a single QWidget page."""

    def __init__(self, widget: QWidget) -> None:
        self._widget = widget
        self._disposed = False

    @property
    def widget(self) -> QWidget:
        return self._widget

    def dispose(self) -> None:
        if not self._disposed:
            self._widget.deleteLater()
            self._disposed = True


class ModuleRuntime:
    """Lazy app/session runtime; the shell owns mounting and cache policy."""

    def __init__(self, catalog: ModuleCatalog, context: ModuleContext) -> None:
        self.catalog = catalog
        self.context = context
        self._handles: dict[str, ModuleHandle] = {}
        self._active_module_id: str | None = None
        self._active_handle_id: str | None = None

    @property
    def active_module_id(self) -> str | None:
        return self._active_module_id

    def handle_for(self, module_id: str) -> ModuleHandle:
        descriptor = self.catalog.require(module_id)
        if isinstance(descriptor, RouteDescriptor):
            workspace = self.catalog.require_workspace(descriptor.workspace_id)
            return self._get_or_create(workspace)
        return self._get_or_create(descriptor)

    def activate(self, module_id: str) -> ModuleHandle:
        descriptor = self.catalog.require(module_id)
        route_key = descriptor.route_key if isinstance(descriptor, RouteDescriptor) else None
        handle_id = descriptor.workspace_id if isinstance(descriptor, RouteDescriptor) else module_id
        handle = self.handle_for(module_id)

        if self._active_handle_id != handle_id:
            self._deactivate_active()
        handle.activate(route_key)
        self._active_module_id = module_id
        self._active_handle_id = handle_id
        self.context.event_hub.publish(
            ModuleActivated(origin="module-runtime", module_id=module_id, route_key=route_key)
        )
        return handle

    def dispose(self) -> None:
        self._deactivate_active()
        for handle in self._handles.values():
            handle.dispose()
        self._handles.clear()
        self._active_module_id = None
        self._active_handle_id = None

    def _get_or_create(self, descriptor: PageDescriptor | WorkspaceDescriptor) -> ModuleHandle:
        handle = self._handles.get(descriptor.module_id)
        if handle is None:
            handle = descriptor.factory(self.context)
            if not isinstance(handle, ModuleHandle):
                raise TypeError(f"Module factory for {descriptor.module_id!r} must return ModuleHandle")
            self._handles[descriptor.module_id] = handle
        return handle

    def _deactivate_active(self) -> None:
        if self._active_handle_id is None:
            return
        handle = self._handles[self._active_handle_id]
        handle.deactivate()
        self.context.event_hub.publish(
            ModuleDeactivated(origin="module-runtime", module_id=self._active_module_id or self._active_handle_id)
        )
        self._active_handle_id = None


__all__ = ["ModuleHandle", "ModuleRuntime", "WidgetHandle"]
