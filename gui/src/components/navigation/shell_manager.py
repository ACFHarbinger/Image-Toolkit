"""Shell layout manager coordinating Rail vs. Top Bar navigation and ModuleRuntime (§2.36, #513)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from gui.src.modules.events import NavigateIntent
from gui.src.modules.runtime import ModuleRuntime

from .navigation_rail import NavigationRailWidget
from .segmented_ribbon import TopSegmentedRibbonWidget


class ShellNavMode(str, Enum):
    RAIL = "rail"
    TOP_BAR = "top_bar"


class ShellLayoutManager(QObject):
    """Coordinates dynamic shell navigation, lazy viewport mounting, and runtime activation."""

    module_changed = Signal(str)  # active module_id
    nav_mode_changed = Signal(str)  # new mode value

    def __init__(
        self,
        runtime: ModuleRuntime,
        container_widget: QWidget,
        default_mode: ShellNavMode = ShellNavMode.RAIL,
    ) -> None:
        super().__init__(container_widget)
        self.runtime = runtime
        self.catalog = runtime.catalog
        self.context = runtime.context
        self.container = container_widget
        self.nav_mode = default_mode
        self._active_module_id: Optional[str] = None
        self._mounted_widgets: set[QWidget] = set()

        self.stack = QStackedWidget()
        self.rail = NavigationRailWidget(self.catalog)
        self.ribbon = TopSegmentedRibbonWidget(self.catalog)

        self.rail.module_selected.connect(self.activate_module)
        self.ribbon.module_selected.connect(self.activate_module)

        # Subscribe to NavigateIntent on the event hub
        self._nav_sub = self.context.event_hub.subscribe(
            NavigateIntent, self._on_navigate_intent, owner=self
        )

        self._build_layout()

    def _build_layout(self) -> None:
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Top ribbon container
        self.root_layout.addWidget(self.ribbon)

        # Main center layout (Rail + Stack)
        self.body_widget = QWidget()
        self.body_layout = QHBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        self.body_layout.addWidget(self.rail)
        self.body_layout.addWidget(self.stack, 1)

        self.root_layout.addWidget(self.body_widget, 1)

        self._apply_nav_mode_visibility()

    def _apply_nav_mode_visibility(self) -> None:
        if self.nav_mode == ShellNavMode.RAIL:
            self.ribbon.hide()
            self.rail.show()
        else:
            self.rail.hide()
            self.ribbon.show()

    def set_nav_mode(self, mode: ShellNavMode) -> None:
        if self.nav_mode != mode:
            self.nav_mode = mode
            self._apply_nav_mode_visibility()
            if self._active_module_id:
                if mode == ShellNavMode.RAIL:
                    self.rail.set_active_module(self._active_module_id)
                else:
                    self.ribbon.set_active_module(self._active_module_id)
            self.nav_mode_changed.emit(mode.value)

    def toggle_nav_mode(self) -> None:
        new_mode = ShellNavMode.TOP_BAR if self.nav_mode == ShellNavMode.RAIL else ShellNavMode.RAIL
        self.set_nav_mode(new_mode)

    def activate_module(self, module_id: str) -> None:
        handle = self.runtime.activate(module_id)
        widget = handle.widget

        if widget not in self._mounted_widgets:
            self._mounted_widgets.add(widget)
            self.stack.addWidget(widget)

        target_idx = self.stack.indexOf(widget)
        try:
            from gui.src.styles.motion_kit import MotionKit
            MotionKit.animate_stacked_switch(self.stack, target_idx, duration_ms=MotionKit.FAST_MS)
        except Exception:
            self.stack.setCurrentWidget(widget)

        self._active_module_id = module_id

        # Sync both navigation widgets
        self.rail.blockSignals(True)
        self.rail.set_active_module(module_id)
        self.rail.blockSignals(False)

        self.ribbon.blockSignals(True)
        self.ribbon.set_active_module(module_id)
        self.ribbon.blockSignals(False)

        self.module_changed.emit(module_id)

    def _on_navigate_intent(self, intent: NavigateIntent) -> None:
        self.activate_module(intent.module_id)

    @property
    def active_module_id(self) -> Optional[str]:
        return self._active_module_id


__all__ = ["ShellNavMode", "ShellLayoutManager"]
