"""gui/src/modules/pilots/log_panel_module.py
============================================
Log Panel pilot implementation for ModuleDescriptor + ModuleHost contract (§1.3, #527).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from ..descriptor import (
    ConstructionPolicy,
    ModuleCategory,
    ModuleDescriptor,
    ModuleRoute,
)


def create_log_panel_descriptor(
    tab_name: str = "Application Log",
    custom_parent: Optional[QWidget] = None,
) -> ModuleDescriptor:
    """Construct the ModuleDescriptor for the Log Panel pilot."""

    def _factory() -> QWidget:
        from gui.src.windows.logging.log_window import LogWindow

        # Construct LogWindow as an embedded panel (parent=None or custom_parent, not a popup window)
        window = LogWindow(tab_name=tab_name, parent=custom_parent)
        return window

    return ModuleDescriptor(
        id="log_panel",
        title=tab_name,
        category=ModuleCategory.DEVELOPER,
        japanese_subtext="システムログ",
        icon_name="terminal",
        construction_policy=ConstructionPolicy.LAZY,
        view_factory=_factory,
        child_routes=[
            ModuleRoute(route_id="all", title="All Messages", description="Full application log stream"),
            ModuleRoute(route_id="system", title="System", description="Core runtime events"),
            ModuleRoute(route_id="crawlers", title="Crawlers", description="Web crawler diagnostics"),
            ModuleRoute(route_id="workers", title="Workers", description="Background task logs"),
        ],
        singleton=True,
        order_index=90,
    )


__all__ = ["create_log_panel_descriptor"]
