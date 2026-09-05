"""gui/src/modules/application_catalog.py
======================================
The production module catalog registering all 33 legacy inventory routes (§2.36, #533).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from gui.src.preferences import PreferenceStore

from .catalog import ModuleCatalog, PageDescriptor
from .descriptor import ModuleCategory
from .library_service import LIBRARY_DATABASE_SERVICE
from .runtime import ModuleHandle, WidgetHandle
from .stitch_workspace import register_stitch_workspace

if TYPE_CHECKING:
    from .context import ModuleContext


def _widget_factory(factory: Callable[[ModuleContext], Any]) -> Callable[[ModuleContext], ModuleHandle]:
    def create(context: ModuleContext) -> ModuleHandle:
        widget = factory(context)
        return WidgetHandle(widget)

    return create


def _create_database_tab(context: ModuleContext) -> Any:
    from gui.src.tabs import DatabaseTab

    vault = context.services.get("vault_manager", None)
    db_svc = context.services.get(LIBRARY_DATABASE_SERVICE, None)
    try:
        return DatabaseTab(
            vault,
            database_service=db_svc,
            event_hub=context.event_hub,
        )
    except TypeError:
        return DatabaseTab(vault)


def _create_search_tab(context: ModuleContext, dropdown: bool) -> Any:
    from gui.src.tabs import SearchTab

    db_svc = context.services.get(LIBRARY_DATABASE_SERVICE, None)
    try:
        return SearchTab(
            db_svc,
            context.event_hub,
            dropdown=dropdown,
        )
    except TypeError:
        return SearchTab(dropdown=dropdown)


def _create_scan_tab(context: ModuleContext) -> Any:
    from gui.src.tabs import ScanMetadataTab

    db_svc = context.services.get(LIBRARY_DATABASE_SERVICE, None)
    try:
        return ScanMetadataTab(db_svc, context.event_hub)
    except TypeError:
        return ScanMetadataTab()


def _create_wallpaper_tab(context: ModuleContext) -> Any:
    from gui.src.tabs import WallpaperTab

    db_svc = context.services.get(LIBRARY_DATABASE_SERVICE, None)
    try:
        return WallpaperTab(db_svc, context.event_hub)
    except TypeError:
        return WallpaperTab()


def _create_listings_tab(context: ModuleContext) -> Any:
    from gui.src.tabs.database import ListingsTab

    vault = context.services.get("vault_manager", None)
    try:
        return ListingsTab(vault_manager=vault, event_hub=context.event_hub)
    except TypeError:
        return ListingsTab(vault_manager=vault)


def _tab(name: str, **kwargs: Any) -> Callable[[ModuleContext], Any]:
    def create(_context: ModuleContext) -> Any:
        from gui.src import tabs

        return getattr(tabs, name)(**kwargs)

    return create


def _vault_tab(name: str) -> Callable[[ModuleContext], Any]:
    def create(context: ModuleContext) -> Any:
        from gui.src import tabs

        return getattr(tabs, name)(context.services.get("vault_manager", None))

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
        ("system.convert", "Convert", ModuleCategory.SYSTEM, _tab("ConvertTab", dropdown=dropdown)),
        ("system.merge", "Merge", ModuleCategory.SYSTEM, _tab("MergeTab")),
        ("system.similarity", "Similarity", ModuleCategory.SYSTEM, _tab("SimilarityTab", dropdown=dropdown)),
        ("system.extractor", "Extractor", ModuleCategory.SYSTEM, _tab("ExtractorTab")),
        ("system.wallpaper", "Wallpaper", ModuleCategory.SYSTEM, _create_wallpaper_tab),
        ("library.listings", "Listings", ModuleCategory.LIBRARY, _create_listings_tab),
        ("library.search", "Image Search", ModuleCategory.LIBRARY, lambda ctx: _create_search_tab(ctx, dropdown)),
        ("library.scan", "Scan and Tag", ModuleCategory.LIBRARY, _create_scan_tab),
        ("library.management", "Management", ModuleCategory.LIBRARY, _create_database_tab),
        ("library.data-browser", "Data Browser", ModuleCategory.LIBRARY, _vault_tab("DataBrowserTab")),
        ("web.crawler", "Crawler", ModuleCategory.WEB, _tab("ImageCrawlTab")),
        ("web.requests", "Requests", ModuleCategory.WEB, _tab("WebRequestsTab")),
        ("web.drive-sync", "Cloud Synchronization", ModuleCategory.WEB, _vault_tab("DriveSyncTab")),
        ("web.media-loader", "Media Loader", ModuleCategory.WEB, _tab("MediaLoaderTab")),
        ("web.reverse-search", "Reverse Search", ModuleCategory.WEB, _tab("ReverseImageSearchTab")),
        ("web.entity-recon", "Entity Reconnaissance", ModuleCategory.WEB, _tab("EntityReconTab")),
        ("ml.training", "Training", ModuleCategory.DEEP_LEARNING, _tab("UnifiedTrainTab")),
        ("ml.generation", "Generation", ModuleCategory.DEEP_LEARNING, _tab("UnifiedGenerateTab")),
        ("ml.evaluation", "Evaluation", ModuleCategory.DEEP_LEARNING, _tab("R3GANEvaluateTab")),
        ("ml.inference", "Inference", ModuleCategory.DEEP_LEARNING, _tab("MetaCLIPInferenceTab")),
        ("ml.comfyui", "ComfyUI", ModuleCategory.DEEP_LEARNING, _tab("ComfyUITab", enable_manager=enable_manager)),
        ("manga.colorization", "Colorization", ModuleCategory.MANGA, _tab("MangaColorizationTab")),
        ("manga.animation", "Animation", ModuleCategory.MANGA, _tab("MangaAnimationTab")),
        ("manga.puppeteering", "Puppeteering", ModuleCategory.MANGA, _tab("MangaPuppeteeringTab")),
        ("editor.hybrid", "Hybrid Editor", ModuleCategory.EDITOR, _tab("HieEditorTab")),
    )
    for order_index, (module_id, title, category, factory) in enumerate(pages):
        catalog.register(
            PageDescriptor(
                module_id=module_id,
                title=title,
                category=category,
                factory=_widget_factory(factory),
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
