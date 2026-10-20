"""gui/src/modules/application_catalog.py
======================================
The production module catalog registering all 33 legacy inventory routes (§2.36, #533).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from middleware.src.shell.catalog import shell_catalog

from gui.src.preferences import PreferenceStore

from .catalog import ModuleCatalog, PageDescriptor
from .dl_workspace import DL_PAGE_IDS, register_dl_workspace
from .runtime import ModuleHandle, WidgetHandle
from .stitch_workspace import register_stitch_workspace
from .tab_factory import build_tab

if TYPE_CHECKING:
    from .context import ModuleContext


def _widget_factory(
    module_id: str, *, dropdown: bool, enable_manager: bool
) -> Callable[[ModuleContext], ModuleHandle]:
    def create(context: ModuleContext) -> ModuleHandle:
        configured_context = replace(
            context, dropdown=dropdown, enable_manager=enable_manager
        )
        return WidgetHandle(build_tab(module_id, configured_context))

    return create


def build_application_catalog(
    *,
    dropdown: bool = True,
    enable_manager: bool = False,
    enable_stitch: bool | None = None,
    enable_dl: bool | None = None,
    preference_store: PreferenceStore | None = None,
) -> ModuleCatalog:
    """Build production descriptors without constructing widgets.

    ``enable_stitch`` / ``enable_dl`` are explicit test/rollout overrides;
    production uses the account-owned preference when they are omitted.
    """
    catalog = ModuleCatalog()
    dl_enabled = enable_dl
    if dl_enabled is None:
        from .dl_workspace import dl_workspace_enabled

        dl_enabled = dl_workspace_enabled(preference_store)

    for entry in shell_catalog().pages():
        if "qt" not in entry.surfaces:
            continue
        if dl_enabled and entry.id in DL_PAGE_IDS:
            continue
        catalog.register(
            PageDescriptor(
                module_id=entry.id,
                title=entry.title,
                category=entry.category,
                factory=_widget_factory(
                    entry.id, dropdown=dropdown, enable_manager=enable_manager
                ),
                icon_name=entry.icon_name,
                capability_flags=frozenset(entry.capability_flags),
                order_index=entry.order_index,
            )
        )

    register_stitch_workspace(
        catalog,
        enabled=enable_stitch,
        preference_store=preference_store,
    )
    register_dl_workspace(
        catalog,
        enabled=dl_enabled,
        preference_store=preference_store,
    )
    return catalog


__all__ = ["build_application_catalog"]
