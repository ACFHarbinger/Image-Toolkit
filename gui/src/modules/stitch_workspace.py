"""gui/src/modules/stitch_workspace.py
====================================
Feature-flagged Image Stitching workspace registration (§2.36, #533, #535).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middleware.src.shell.catalog import shell_catalog

from gui.src.preferences import PreferenceStore, PrefKeys

from .catalog import ModuleCatalog, RouteDescriptor, WorkspaceDescriptor
from .runtime import ModuleHandle

if TYPE_CHECKING:
    from .context import ModuleContext

STITCH_WORKSPACE_ID = "stitch"
# module_id, route_key, title, StitchTab panel attribute
STITCH_ROUTES = (
    ("stitch.stitch", "stitch", "Stitch", "stitch_panel"),
    ("stitch.graph", "graph", "Graph", "graph_panel"),
    ("stitch.adjust", "adjust", "Adjust", "adjust_panel"),
    ("stitch.canvas", "canvas", "Canvas", "canvas_panel"),
    ("stitch.statistics", "statistics", "Statistics", "stats_panel"),
    ("stitch.sequence-builder", "sequence-builder", "Sequence Builder", "seq_builder_panel"),
    ("stitch.hybrid", "hybrid", "Hybrid Stitch", "hybrid_stitch_panel"),
    ("stitch.animation-clusters", "animation-clusters", "Animation Clusters", "anim_clusters_panel"),
)
_ROUTE_PANELS = {route_key: panel_attr for _id, route_key, _title, panel_attr in STITCH_ROUTES}


def stitch_workspace_enabled(preference_store: PreferenceStore | None = None) -> bool:
    """Return whether this account enables the experimental workspace."""
    store = preference_store or PreferenceStore.instance()
    return bool(store.get(PrefKeys.EXPERIMENTAL_STITCH_WORKSPACE))


class StitchWorkspaceHandle(ModuleHandle):
    """One StitchTab host whose named panels select catalog routes."""

    def __init__(self, stitch_tab: Any) -> None:
        self._stitch_tab = stitch_tab
        self._disposed = False

    @property
    def widget(self) -> Any:
        return self._stitch_tab

    def activate(self, route_key: str | None = None) -> None:
        if route_key is None or self._disposed:
            return
        panel_attr = _ROUTE_PANELS.get(route_key)
        if panel_attr is None:
            raise LookupError(f"Unknown Stitch workspace route: {route_key}")
        panel = getattr(self._stitch_tab, panel_attr, None)
        tabs = getattr(self._stitch_tab, "_tab_widget", None)
        if panel is None or tabs is None:
            raise LookupError(f"Stitch workspace is missing panel {panel_attr!r}")
        index = tabs.indexOf(panel)
        if index < 0:
            raise LookupError(f"Stitch panel {panel_attr!r} is not on the workspace tab widget")
        tabs.setCurrentIndex(index)

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        tab = self._stitch_tab
        self._stitch_tab = None
        dispose = getattr(tab, "deleteLater", None)
        if callable(dispose):
            dispose()


def create_stitch_workspace(_context: ModuleContext) -> StitchWorkspaceHandle:
    """Construct the existing shared StitchTab only when first activated."""
    from asp_gui.elements import StitchTab

    return StitchWorkspaceHandle(StitchTab())


def register_stitch_workspace(
    catalog: ModuleCatalog,
    *,
    enabled: bool | None = None,
    preference_store: PreferenceStore | None = None,
) -> bool:
    """Register the one host and eight routes when the experiment is enabled."""
    if enabled is None:
        enabled = stitch_workspace_enabled(preference_store)
    if not enabled:
        return False

    host = shell_catalog().require(STITCH_WORKSPACE_ID)
    catalog.register(
        WorkspaceDescriptor(
            module_id=host.id,
            title=host.title,
            category=host.category,
            factory=create_stitch_workspace,
            icon_name=host.icon_name,
            search_terms=host.search_terms,
            capability_flags=frozenset(host.capability_flags),
        )
    )
    for module_id, route_key, _title, _panel_attr in STITCH_ROUTES:
        entry = shell_catalog().require(module_id)
        catalog.register(
            RouteDescriptor(
                module_id=entry.id,
                workspace_id=STITCH_WORKSPACE_ID,
                route_key=route_key,
                title=entry.title,
                category=entry.category,
                icon_name=entry.icon_name,
                search_terms=entry.search_terms,
                capability_flags=frozenset(entry.capability_flags),
                order_index=entry.order_index,
            )
        )
    return True


__all__ = [
    "STITCH_ROUTES",
    "STITCH_WORKSPACE_ID",
    "StitchWorkspaceHandle",
    "create_stitch_workspace",
    "register_stitch_workspace",
    "stitch_workspace_enabled",
]
