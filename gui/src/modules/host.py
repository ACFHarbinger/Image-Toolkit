"""gui/src/modules/host.py
=======================
ModuleHost container managing module lifecycle, mounting, and route switching (§1.3, #527).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedLayout, QWidget

from .descriptor import ConstructionPolicy, ModuleDescriptor
from .registry import ModuleRegistry


class ModuleHostWidget(QWidget):
    """Host container managing lifecycle, lazy mounting, and route navigation for modules."""

    module_navigated = Signal(str, str)  # (module_id, full_route)
    module_changed = Signal(str)        # (module_id)

    def __init__(self, registry: Optional[ModuleRegistry] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._registry = registry or ModuleRegistry()
        self._mounted_widgets: dict[str, QWidget] = {}
        self._active_module_id: Optional[str] = None
        self._active_route: Optional[str] = None

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

    @property
    def registry(self) -> ModuleRegistry:
        return self._registry

    @property
    def active_module_id(self) -> Optional[str]:
        return self._active_module_id

    @property
    def active_route(self) -> Optional[str]:
        return self._active_route

    def register_module(self, descriptor: ModuleDescriptor) -> None:
        """Register a module with the host registry. Eager modules are mounted immediately."""
        self._registry.register(descriptor)
        if descriptor.construction_policy == ConstructionPolicy.EAGER:
            self._mount_module(descriptor)

    def _mount_module(self, descriptor: ModuleDescriptor) -> QWidget:
        """Mount module's widget into the internal stack if not already mounted."""
        if descriptor.id in self._mounted_widgets:
            return self._mounted_widgets[descriptor.id]

        widget = descriptor.get_widget()
        self._stack.addWidget(widget)
        self._mounted_widgets[descriptor.id] = widget
        return widget

    def navigate_to(self, route: str) -> Optional[QWidget]:
        """Navigate to a module or child route. Lazily mounts the widget if needed."""
        descriptor, child_route = self._registry.resolve_route(route)
        if descriptor is None:
            return None

        widget = self._mount_module(descriptor)
        self._stack.setCurrentWidget(widget)

        prev_module_id = self._active_module_id
        self._active_module_id = descriptor.id
        self._active_route = route

        if prev_module_id != descriptor.id:
            self.module_changed.emit(descriptor.id)

        self.module_navigated.emit(descriptor.id, route)
        return widget

    def get_mounted_widget(self, module_id: str) -> Optional[QWidget]:
        """Return mounted widget for a module if already constructed."""
        return self._mounted_widgets.get(module_id)

    def is_mounted(self, module_id: str) -> bool:
        """Check if a module has already been mounted in the UI."""
        return module_id in self._mounted_widgets


__all__ = ["ModuleHostWidget"]
