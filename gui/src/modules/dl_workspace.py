"""gui/src/modules/dl_workspace.py
================================
Feature-flagged Deep Learning workspace registration (#730).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middleware.src.shell.catalog import shell_catalog
from PySide6.QtCore import QTimer

from gui.src.preferences import PreferenceStore, PrefKeys

from .catalog import ModuleCatalog, RouteDescriptor, WorkspaceDescriptor
from .runtime import ModuleHandle

if TYPE_CHECKING:
    from .context import ModuleContext

_pending_disposals: dict[int, tuple[Any, QTimer]] = {}

DL_WORKSPACE_ID = "dl"
# module_id, route_key, title — titles come from the shared catalog.
DL_ROUTES = tuple(
    (entry.id, entry.route_key, entry.title)
    for entry in shell_catalog().entries
    if entry.workspace_id == DL_WORKSPACE_ID and entry.route_key is not None
)
# Classic five-tab ids → destination. Evaluation/Inference are Review tools;
# ComfyUI is Generate (Guided|Graph lands in Gate C).
DL_CLASSIC_ALIASES = shell_catalog().alias_map("experimental-dl")
DL_PAGE_IDS = frozenset(DL_CLASSIC_ALIASES)


def dl_workspace_enabled(preference_store: PreferenceStore | None = None) -> bool:
    """Return whether this account enables the experimental workspace."""
    store = preference_store or PreferenceStore.instance()
    return bool(store.get(PrefKeys.EXPERIMENTAL_DL_WORKSPACE))


class DeepLearningWorkspaceHandle(ModuleHandle):
    """One host whose stacked destinations select catalog routes."""

    def __init__(self, host: Any) -> None:
        self._host = host
        self._disposed = False

    @property
    def widget(self) -> Any:
        return self._host

    def activate(self, route_key: str | None = None) -> None:
        if route_key is None or self._disposed:
            return
        activate = getattr(self._host, "activate_route", None)
        if not callable(activate):
            raise LookupError("Deep Learning workspace host is missing activate_route")
        activate(route_key)

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        host = self._host
        self._host = None
        if host is None:
            return
        prepare = getattr(host, "prepare_dispose", None)
        if callable(prepare):
            prepare()
        dispose = getattr(host, "deleteLater", None)
        ready = getattr(host, "disposal_ready", None)
        if callable(dispose) and callable(ready) and not ready():
            # Training still emits through widgets owned by this host.
            timer = QTimer()
            timer.setInterval(25)
            key = id(host)

            def finish_disposal() -> None:
                if not ready():
                    return
                timer.stop()
                _pending_disposals.pop(key, None)
                dispose()
                timer.deleteLater()

            timer.timeout.connect(finish_disposal)
            _pending_disposals[key] = (host, timer)
            host.hide()
            timer.start()
        elif callable(dispose):
            dispose()


def create_dl_workspace(context: ModuleContext | None) -> DeepLearningWorkspaceHandle:
    """Construct the shared host only when first activated."""
    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost

    event_hub = getattr(context, "event_hub", None)
    pref_store = getattr(context, "preference_store", None)
    try:
        host = DeepLearningWorkspaceHost(event_hub=event_hub, preference_store=pref_store,
                                         vault_manager=getattr(context, "services", {}).get("vault_manager"))
    except TypeError:
        host = DeepLearningWorkspaceHost(event_hub=event_hub)
    return DeepLearningWorkspaceHandle(host)




def register_dl_workspace(
    catalog: ModuleCatalog,
    *,
    enabled: bool | None = None,
    preference_store: PreferenceStore | None = None,
) -> bool:
    """Register the one host and four routes when the experiment is enabled."""
    if enabled is None:
        enabled = dl_workspace_enabled(preference_store)
    if not enabled:
        return False

    host = shell_catalog().require(DL_WORKSPACE_ID)
    catalog.register(
        WorkspaceDescriptor(
            module_id=host.id,
            title=host.title,
            category=host.category,
            factory=create_dl_workspace,
            icon_name=host.icon_name,
            search_terms=host.search_terms,
            capability_flags=frozenset(host.capability_flags),
        )
    )
    for module_id, route_key, title in DL_ROUTES:
        entry = shell_catalog().require(module_id)
        catalog.register(
            RouteDescriptor(
                module_id=entry.id,
                workspace_id=DL_WORKSPACE_ID,
                route_key=route_key or "",
                title=title,
                category=entry.category,
                icon_name=entry.icon_name,
                search_terms=entry.search_terms,
                capability_flags=frozenset(entry.capability_flags),
                order_index=entry.order_index,
            )
        )
    for alias_id, target_id in DL_CLASSIC_ALIASES.items():
        catalog.register_alias(alias_id, target_id)
    return True


__all__ = [
    "DL_CLASSIC_ALIASES",
    "DL_PAGE_IDS",
    "DL_ROUTES",
    "DL_WORKSPACE_ID",
    "DeepLearningWorkspaceHandle",
    "create_dl_workspace",
    "dl_workspace_enabled",
    "register_dl_workspace",
]
