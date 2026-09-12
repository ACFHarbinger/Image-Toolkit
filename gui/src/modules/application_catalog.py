"""gui/src/modules/application_catalog.py
======================================
The production module catalog registering all 33 legacy inventory routes (§2.36, #533).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from gui.src.preferences import PreferenceStore

from .catalog import ModuleCatalog, PageDescriptor
from .descriptor import ModuleCategory
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
    preference_store: PreferenceStore | None = None,
) -> ModuleCatalog:
    """Build production descriptors without constructing widgets.

    ``enable_stitch`` is an explicit test/rollout override; production uses
    the account-owned preference when it is omitted.
    """
    catalog = ModuleCatalog()

    pages = (
        ("system.convert", "Convert", ModuleCategory.SYSTEM),
        ("system.merge", "Merge", ModuleCategory.SYSTEM),
        ("system.similarity", "Similarity", ModuleCategory.SYSTEM),
        ("system.extractor", "Extractor", ModuleCategory.SYSTEM),
        ("system.wallpaper", "Wallpaper", ModuleCategory.SYSTEM),
        ("library.listings", "Listings", ModuleCategory.LIBRARY),
        ("library.search", "Image Search", ModuleCategory.LIBRARY),
        ("library.scan", "Scan and Tag", ModuleCategory.LIBRARY),
        ("library.management", "Management", ModuleCategory.LIBRARY),
        ("library.data-browser", "Data Browser", ModuleCategory.LIBRARY),
        ("web.crawler", "Crawler", ModuleCategory.WEB),
        ("web.requests", "Requests", ModuleCategory.WEB),
        ("web.drive-sync", "Cloud Synchronization", ModuleCategory.WEB),
        ("web.media-loader", "Media Loader", ModuleCategory.WEB),
        ("web.reverse-search", "Reverse Search", ModuleCategory.WEB),
        ("web.entity-recon", "Entity Reconnaissance", ModuleCategory.WEB),
        ("ml.training", "Training", ModuleCategory.DEEP_LEARNING),
        ("ml.generation", "Generation", ModuleCategory.DEEP_LEARNING),
        ("ml.evaluation", "Evaluation", ModuleCategory.DEEP_LEARNING),
        ("ml.inference", "Inference", ModuleCategory.DEEP_LEARNING),
        ("ml.comfyui", "ComfyUI", ModuleCategory.DEEP_LEARNING),
        ("manga.colorization", "Colorization", ModuleCategory.MANGA),
        ("manga.animation", "Animation", ModuleCategory.MANGA),
        ("manga.puppeteering", "Puppeteering", ModuleCategory.MANGA),
        ("editor.hybrid", "Hybrid Editor", ModuleCategory.EDITOR),
    )
    for order_index, (module_id, title, category) in enumerate(pages):
        catalog.register(
            PageDescriptor(
                module_id=module_id,
                title=title,
                category=category,
                factory=_widget_factory(
                    module_id, dropdown=dropdown, enable_manager=enable_manager
                ),
                order_index=order_index,
            )
        )

    register_stitch_workspace(
        catalog,
        enabled=enable_stitch,
        preference_store=preference_store,
    )
    return catalog


__all__ = ["build_application_catalog"]
