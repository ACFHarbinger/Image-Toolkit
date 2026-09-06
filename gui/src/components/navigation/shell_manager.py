"""Shell layout manager: rail/ribbon chrome + ModuleRuntime host (#536)."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from gui.src.components.inspector import ContextInspectorPanel
from gui.src.modules.catalog import RouteDescriptor, WorkspaceDescriptor
from gui.src.modules.events import NavigateIntent
from gui.src.modules.runtime import ModuleRuntime

from .navigation_rail import NavigationRailWidget
from .segmented_ribbon import TopSegmentedRibbonWidget

log = logging.getLogger(__name__)


class ShellNavMode(str, Enum):
    RAIL = "rail"
    TOP_BAR = "top_bar"


class ShellLayoutManager(QObject):
    """Child controller owning rail/ribbon + viewport stack.

    Construction paints navigation only — no module is activated until
    ``activate_module`` (or a ``NavigateIntent``) runs explicitly.
    Widgets are mounted into the stack *before* ``ModuleRuntime.activate``
    so ``ModuleActivated`` is published after the host selects them.
    """

    module_changed = Signal(str)
    nav_mode_changed = Signal(str)
    navigation_rejected = Signal(str, str)  # (module_id, reason)

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
        self.inspector = ContextInspectorPanel(event_hub=self.context.event_hub)
        self.inspector.hide()

        self.rail.module_selected.connect(self.activate_module)
        self.ribbon.module_selected.connect(self.activate_module)

        self._nav_sub = self.context.event_hub.subscribe(
            NavigateIntent, self._on_navigate_intent, owner=self
        )

        self._build_layout()

        self._init_accents_timer = QTimer(self)
        self._init_accents_timer.setSingleShot(True)
        self._init_accents_timer.timeout.connect(self._apply_initial_category_accents)
        self._init_accents_timer.start(0)

    def _build_layout(self) -> None:
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.root_layout.addWidget(self.ribbon)

        self.body_widget = QWidget()
        self.body_layout = QHBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        self.body_layout.addWidget(self.rail)
        self.body_layout.addWidget(self.stack, 1)
        self.body_layout.addWidget(self.inspector)

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
        if self.nav_mode == mode:
            return
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

    def toggle_inspector(self, visible: Optional[bool] = None) -> None:
        """Toggle or set inspector panel visibility."""
        if visible is None:
            self.inspector.setVisible(self.inspector.isHidden())
        else:
            self.inspector.setVisible(visible)

    def apply_category_accents(self, overrides: dict[str, str]) -> None:
        """Apply category-specific accent overrides to rail and ribbon (§2.41, #518)."""
        self.rail.apply_category_accents(overrides)
        self.ribbon.apply_category_accents(overrides)

    def _apply_initial_category_accents(self) -> None:
        from gui.src.preferences.definitions import PrefKeys

        accents = self.context.preference_store.get(PrefKeys.CATEGORY_ACCENTS)
        if accents and isinstance(accents, dict):
            self.apply_category_accents(accents)

    def activate_module(self, module_id: str) -> None:
        """Mount (if needed), select, then activate — ModuleActivated after mount."""
        if module_id == self._active_module_id and self.runtime.is_created(module_id):
            return

        handle = self.runtime.handle_for(module_id)
        widget = handle.widget

        if widget not in self._mounted_widgets:
            self._mounted_widgets.add(widget)
            self.stack.addWidget(widget)

        self.stack.setCurrentWidget(widget)

        self.runtime.activate(module_id)
        self._active_module_id = module_id

        self.rail.blockSignals(True)
        self.rail.set_active_module(module_id)
        self.rail.blockSignals(False)

        self.ribbon.blockSignals(True)
        self.ribbon.set_active_module(module_id)
        self.ribbon.blockSignals(False)

        self.module_changed.emit(module_id)

    def resolve_navigate_target(self, intent: NavigateIntent) -> str:
        """Map ``NavigateIntent`` to a catalog module/route id."""
        if not intent.route_key:
            return intent.module_id

        desc = self.catalog.get(intent.module_id)
        if isinstance(desc, RouteDescriptor):
            return intent.module_id

        candidate = f"{intent.module_id}.{intent.route_key}"
        if self.catalog.get(candidate) is not None:
            return candidate

        if isinstance(desc, WorkspaceDescriptor):
            for route in self.catalog.navigable_by_category(desc.category):
                if (
                    isinstance(route, RouteDescriptor)
                    and route.workspace_id == desc.module_id
                    and route.route_key == intent.route_key
                ):
                    return route.module_id

        return intent.module_id

    def _on_navigate_intent(self, intent: NavigateIntent) -> None:
        if intent.state:
            # Codex #538 combined re-review (MEDIUM): a warning log is
            # visibility, not preservation or a deliberate rejection --
            # activate_module(module_id) has no channel to carry
            # NavigateIntent.state through, and no consumer of restoration/
            # deep-link state exists on this path yet. Rather than silently
            # navigate to a partially specified target, reject the intent
            # outright via a defined, observable failure signal. Real state
            # threading is future work once a consumer actually needs it.
            reason = f"state not supported ({len(intent.state)} pair(s) dropped)"
            log.warning("NavigateIntent to %s rejected: %s", intent.module_id, reason)
            self.navigation_rejected.emit(intent.module_id, reason)
            return
        self.activate_module(self.resolve_navigate_target(intent))

    def clear_mounted(self) -> None:
        """Remove host-stack widgets before ``ModuleRuntime.dispose()``."""
        timer = getattr(self, "_init_accents_timer", None)
        if timer is not None:
            timer.stop()
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        self._mounted_widgets.clear()
        self._active_module_id = None

    @property
    def active_module_id(self) -> Optional[str]:
        return self._active_module_id


__all__ = ["ShellNavMode", "ShellLayoutManager"]
