"""gui/src/modules/stitch_workspace.py
====================================
Feature-flagged Image Stitching workspace registration (§2.36, #533, #535).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from gui.src.preferences import PreferenceStore

from .catalog import ModuleCatalog, RouteDescriptor, WorkspaceDescriptor
from .descriptor import ModuleCategory
from .runtime import ModuleHandle

if TYPE_CHECKING:
    from .context import ModuleContext

STITCH_WORKSPACE_FLAG = "IMAGE_TOOLKIT_STITCH_WORKSPACE"
STITCH_WORKSPACE_ID = "stitch"
STITCH_ROUTES = (
    ("stitch.stitch", "stitch", "Stitch"),
    ("stitch.graph", "graph", "Graph"),
    ("stitch.adjust", "adjust", "Adjust"),
    ("stitch.canvas", "canvas", "Canvas"),
    ("stitch.statistics", "statistics", "Statistics"),
    ("stitch.sequence-builder", "sequence-builder", "Sequence Builder"),
    ("stitch.hybrid", "hybrid", "Hybrid Stitch"),
    ("stitch.animation-clusters", "animation-clusters", "Animation Clusters"),
)
_ROUTE_INDEX = {route_key: index for index, (_module_id, route_key, _title) in enumerate(STITCH_ROUTES)}


def stitch_workspace_enabled(preference_store: PreferenceStore | None = None) -> bool:
    """Return whether the unmounted workspace experiment is enabled."""
    store = preference_store or PreferenceStore.instance()
    val = store.get("experimental.stitch_workspace", None)
    if val is not None:
        return bool(val)
    return os.environ.get(STITCH_WORKSPACE_FLAG, "0") == "1"


class StitchWorkspaceHandle(ModuleHandle):
    """One StitchTab host whose internal tab widget selects catalog routes."""

    def __init__(self, stitch_tab: Any) -> None:
        self._stitch_tab = stitch_tab

    @property
    def widget(self) -> Any:
        return self._stitch_tab

    def activate(self, route_key: str | None = None) -> None:
        if route_key is None:
            return
        try:
            index = _ROUTE_INDEX[route_key]
        except KeyError as exc:
            raise LookupError(f"Unknown Stitch workspace route: {route_key}") from exc
        self._stitch_tab._tab_widget.setCurrentIndex(index)


def create_stitch_workspace(_context: ModuleContext) -> StitchWorkspaceHandle:
    """Construct the existing shared StitchTab only when first activated."""
    from asp_gui.elements import StitchTab

    return StitchWorkspaceHandle(StitchTab())


def register_stitch_workspace(catalog: ModuleCatalog, *, enabled: bool | None = None) -> bool:
    """Register the one host and eight routes when the experiment is enabled."""
    if enabled is None:
        enabled = stitch_workspace_enabled()
    if not enabled:
        return False

    catalog.register(
        WorkspaceDescriptor(
            module_id=STITCH_WORKSPACE_ID,
            title="Image Stitching",
            category=ModuleCategory.STITCHING,
            factory=create_stitch_workspace,
            icon_name="layers",
            search_terms=("stitch", "panorama", "anime"),
            capability_flags=frozenset({"experimental"}),
        )
    )
    for order_index, (module_id, route_key, title) in enumerate(STITCH_ROUTES):
        catalog.register(
            RouteDescriptor(
                module_id=module_id,
                workspace_id=STITCH_WORKSPACE_ID,
                route_key=route_key,
                title=title,
                category=ModuleCategory.STITCHING,
                icon_name="layers",
                search_terms=("stitch", route_key),
                capability_flags=frozenset({"experimental"}),
                order_index=order_index,
            )
        )
    return True


__all__ = [
    "STITCH_ROUTES",
    "STITCH_WORKSPACE_FLAG",
    "STITCH_WORKSPACE_ID",
    "StitchWorkspaceHandle",
    "create_stitch_workspace",
    "register_stitch_workspace",
    "stitch_workspace_enabled",
]
