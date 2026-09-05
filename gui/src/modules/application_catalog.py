"""The production module catalog used by MainWindow's runtime-shell experiment."""

from __future__ import annotations

from collections.abc import Callable

from .catalog import ModuleCatalog, PageDescriptor
from .context import ModuleContext
from .descriptor import ModuleCategory
from .library_service import LIBRARY_DATABASE_SERVICE
from .runtime import WidgetHandle
from .stitch_workspace import register_stitch_workspace


def _widget_factory(factory: Callable[[ModuleContext], object]):
    def create(context: ModuleContext) -> WidgetHandle:
        return WidgetHandle(factory(context))

    return create


def build_application_catalog(*, dropdown: bool, enable_manager: bool) -> ModuleCatalog:
    """Build all production descriptors without constructing their widgets."""
    catalog = ModuleCatalog()

    def tab(name: str, **kwargs):
        def create(_context: ModuleContext):
            from gui.src import tabs

            return getattr(tabs, name)(**kwargs)

        return create

    def database_tab(context: ModuleContext):
        from gui.src.tabs import DatabaseTab

        return DatabaseTab(
            context.services.require("vault_manager"),
            database_service=context.services.require(LIBRARY_DATABASE_SERVICE),
            event_hub=context.event_hub,
        )

    def vault_tab(name: str):
        def create(context: ModuleContext):
            from gui.src import tabs

            return getattr(tabs, name)(context.services.require("vault_manager"))

        return create

    def search_tab(context: ModuleContext):
        from gui.src.tabs import SearchTab

        return SearchTab(
            context.services.require(LIBRARY_DATABASE_SERVICE), context.event_hub, dropdown=dropdown
        )

    def scan_tab(context: ModuleContext):
        from gui.src.tabs import ScanMetadataTab

        return ScanMetadataTab(context.services.require(LIBRARY_DATABASE_SERVICE), context.event_hub)

    def wallpaper_tab(context: ModuleContext):
        from gui.src.tabs import WallpaperTab

        return WallpaperTab(context.services.require(LIBRARY_DATABASE_SERVICE), context.event_hub)

    def listings_tab(context: ModuleContext):
        from gui.src.tabs.database import ListingsTab

        return ListingsTab(
            vault_manager=context.services.require("vault_manager"), event_hub=context.event_hub
        )

    pages = (
        ("system.convert", "Convert", ModuleCategory.SYSTEM, tab("ConvertTab", dropdown=dropdown)),
        ("system.merge", "Merge", ModuleCategory.SYSTEM, tab("MergeTab")),
        ("system.similarity", "Similarity", ModuleCategory.SYSTEM, tab("SimilarityTab", dropdown=dropdown)),
        ("system.extractor", "Extractor", ModuleCategory.SYSTEM, tab("ExtractorTab")),
        ("system.wallpaper", "Wallpaper", ModuleCategory.SYSTEM, wallpaper_tab),
        ("library.listings", "Listings", ModuleCategory.LIBRARY, listings_tab),
        ("library.search", "Image Search", ModuleCategory.LIBRARY, search_tab),
        ("library.scan", "Scan and Tag", ModuleCategory.LIBRARY, scan_tab),
        ("library.management", "Management", ModuleCategory.LIBRARY, database_tab),
        ("library.data-browser", "Data Browser", ModuleCategory.LIBRARY, vault_tab("DataBrowserTab")),
        ("web.crawler", "Crawler", ModuleCategory.WEB, tab("ImageCrawlTab")),
        ("web.requests", "Requests", ModuleCategory.WEB, tab("WebRequestsTab")),
        ("web.drive-sync", "Cloud Synchronization", ModuleCategory.WEB, vault_tab("DriveSyncTab")),
        ("web.media-loader", "Media Loader", ModuleCategory.WEB, tab("MediaLoaderTab")),
        ("web.reverse-search", "Reverse Search", ModuleCategory.WEB, tab("ReverseImageSearchTab")),
        ("web.entity-recon", "Entity Reconnaissance", ModuleCategory.WEB, tab("EntityReconTab")),
        ("ml.training", "Training", ModuleCategory.DEEP_LEARNING, tab("UnifiedTrainTab")),
        ("ml.generation", "Generation", ModuleCategory.DEEP_LEARNING, tab("UnifiedGenerateTab")),
        ("ml.evaluation", "Evaluation", ModuleCategory.DEEP_LEARNING, tab("R3GANEvaluateTab")),
        ("ml.inference", "Inference", ModuleCategory.DEEP_LEARNING, tab("MetaCLIPInferenceTab")),
        ("ml.comfyui", "ComfyUI", ModuleCategory.DEEP_LEARNING, tab("ComfyUITab", enable_manager=enable_manager)),
        ("manga.colorization", "Colorization", ModuleCategory.MANGA, tab("MangaColorizationTab")),
        ("manga.animation", "Animation", ModuleCategory.MANGA, tab("MangaAnimationTab")),
        ("manga.puppeteering", "Puppeteering", ModuleCategory.MANGA, tab("MangaPuppeteeringTab")),
        ("editor.hybrid", "Hybrid Editor", ModuleCategory.EDITOR, tab("HieEditorTab")),
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

    # The MainWindow experiment is its own feature boundary.  Stitch's old
    # standalone flag remains useful for isolated registration tests, but all
    # production routes must be present whenever this shell is enabled.
    register_stitch_workspace(catalog, enabled=True)
    return catalog


__all__ = ["build_application_catalog"]
