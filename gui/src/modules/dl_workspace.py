"""gui/src/modules/dl_workspace.py
================================
Feature-flagged Deep Learning workspace registration (#730).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gui.src.preferences import PreferenceStore, PrefKeys

from .catalog import ModuleCatalog, RouteDescriptor, WorkspaceDescriptor
from .descriptor import ModuleCategory
from .runtime import ModuleHandle

if TYPE_CHECKING:
    from .context import ModuleContext

DL_WORKSPACE_ID = "dl"
# module_id, route_key, title
DL_ROUTES = (
    ("dl.train", "train", "Train"),
    ("dl.generate", "generate", "Generate"),
    ("dl.review", "review", "Review"),
    ("dl.runs", "runs", "Runs"),
)
# Classic five-tab ids → destination. Evaluation/Inference are Review tools;
# ComfyUI is Generate (Guided|Graph lands in Gate C).
DL_CLASSIC_ALIASES = {
    "ml.training": "dl.train",
    "ml.generation": "dl.generate",
    "ml.evaluation": "dl.review",
    "ml.inference": "dl.review",
    "ml.comfyui": "dl.generate",
}
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
        dispose = getattr(host, "deleteLater", None)
        if callable(dispose):
            dispose()


def create_dl_workspace(context: ModuleContext | None) -> DeepLearningWorkspaceHandle:
    """Construct the shared host only when first activated."""
    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost

    event_hub = getattr(context, "event_hub", None)
    pref_store = getattr(context, "preference_store", None)
    try:
        host = DeepLearningWorkspaceHost(event_hub=event_hub, preference_store=pref_store)
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

    catalog.register(
        WorkspaceDescriptor(
            module_id=DL_WORKSPACE_ID,
            title="Deep Learning",
            category=ModuleCategory.DEEP_LEARNING,
            factory=create_dl_workspace,
            icon_name="cpu",
            search_terms=("train", "lora", "comfy", "generate"),
            capability_flags=frozenset({"experimental"}),
        )
    )
    for order_index, (module_id, route_key, title) in enumerate(DL_ROUTES):
        catalog.register(
            RouteDescriptor(
                module_id=module_id,
                workspace_id=DL_WORKSPACE_ID,
                route_key=route_key,
                title=title,
                category=ModuleCategory.DEEP_LEARNING,
                icon_name="cpu",
                search_terms=("deep learning", route_key),
                capability_flags=frozenset({"experimental"}),
                order_index=order_index,
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
