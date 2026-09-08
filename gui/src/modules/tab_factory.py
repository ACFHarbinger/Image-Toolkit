"""Single construction path for classic-shell and runtime-shell tabs."""

from __future__ import annotations

from typing import Any

from .context import ModuleContext
from .library_service import LIBRARY_DATABASE_SERVICE


def build_tab(module_id: str, context: ModuleContext) -> Any:
    """Construct a legacy tab from its stable module identifier.

    This intentionally imports the concrete tab only at activation time.  Both
    shells use this function, so constructor changes have one call site.
    """
    from gui.src import tabs
    vault_manager = context.services.get("vault_manager")
    database_service = context.services.get(LIBRARY_DATABASE_SERVICE)
    event_hub = context.event_hub

    if module_id == "library.listings":
        from gui.src.tabs.database import ListingsTab

        return ListingsTab(vault_manager=vault_manager, event_hub=event_hub)
    if module_id == "system.convert":
        return tabs.ConvertTab(dropdown=context.dropdown)
    if module_id == "system.similarity":
        return tabs.SimilarityTab(dropdown=context.dropdown)
    if module_id == "system.wallpaper":
        return tabs.WallpaperTab(database_service, event_hub)
    if module_id == "library.search":
        return tabs.SearchTab(database_service, event_hub, dropdown=context.dropdown)
    if module_id == "library.scan":
        return tabs.ScanMetadataTab(database_service, event_hub)
    if module_id == "library.management":
        return tabs.DatabaseTab(vault_manager, database_service=database_service, event_hub=event_hub)
    if module_id == "library.data-browser":
        return tabs.DataBrowserTab(vault_manager)
    if module_id == "web.drive-sync":
        return tabs.DriveSyncTab(vault_manager)
    if module_id == "ml.comfyui":
        return tabs.ComfyUITab(enable_manager=context.enable_manager)

    tab_classes = {
        "system.merge": "MergeTab",
        "system.extractor": "ExtractorTab",
        "web.crawler": "ImageCrawlTab",
        "web.requests": "WebRequestsTab",
        "web.media-loader": "MediaLoaderTab",
        "web.reverse-search": "ReverseImageSearchTab",
        "web.entity-recon": "EntityReconTab",
        "ml.training": "UnifiedTrainTab",
        "ml.generation": "UnifiedGenerateTab",
        "ml.evaluation": "R3GANEvaluateTab",
        "ml.inference": "MetaCLIPInferenceTab",
        "manga.colorization": "MangaColorizationTab",
        "manga.animation": "MangaAnimationTab",
        "manga.puppeteering": "MangaPuppeteeringTab",
        "editor.hybrid": "HieEditorTab",
        "stitch.workspace": "StitchTab",
    }
    try:
        return getattr(tabs, tab_classes[module_id])()
    except KeyError as exc:
        raise LookupError(f"No tab factory registered for {module_id!r}") from exc


__all__ = ["build_tab"]
