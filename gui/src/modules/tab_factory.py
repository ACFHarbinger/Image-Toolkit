"""Single construction path for classic-shell and runtime-shell tabs."""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any

from .context import ModuleContext
from .library_service import LIBRARY_DATABASE_SERVICE

logger = logging.getLogger(__name__)

# Leaf modules — importing these still runs the parent package ``__init__``
# (so a category that shares a package pays that cost once). Stitch/manga/HIE
# stay on ``gui.src.tabs`` so ``asp_gui``/``csg_gui``/``hie_tab`` remain lazy.
_TAB_LEAVES: dict[str, tuple[str, str]] = {
    "system.convert": ("gui.src.tabs.core.convert_tab", "ConvertTab"),
    "system.merge": ("gui.src.tabs.core.merge_tab", "MergeTab"),
    "system.similarity": ("gui.src.tabs.core.similarity_tab", "SimilarityTab"),
    "system.extractor": ("gui.src.tabs.core.extractor_tab", "ExtractorTab"),
    "system.wallpaper": ("gui.src.tabs.core.wallpaper_tab", "WallpaperTab"),
    "library.listings": ("gui.src.tabs.database.listings_tab", "ListingsTab"),
    "library.search": ("gui.src.tabs.database.search_tab", "SearchTab"),
    "library.scan": ("gui.src.tabs.database.scan_metadata_tab", "ScanMetadataTab"),
    "library.management": ("gui.src.tabs.database.database_tab", "DatabaseTab"),
    "library.data-browser": ("gui.src.tabs.database.data_browser_tab", "DataBrowserTab"),
    "web.crawler": ("gui.src.tabs.web.image_crawler_tab", "ImageCrawlTab"),
    "web.requests": ("gui.src.tabs.web.web_requests_tab", "WebRequestsTab"),
    "web.drive-sync": ("gui.src.tabs.web.drive_sync_tab", "DriveSyncTab"),
    "web.media-loader": ("gui.src.tabs.web.media_loader_tab", "MediaLoaderTab"),
    "web.reverse-search": ("gui.src.tabs.web.reverse_search_tab", "ReverseImageSearchTab"),
    "web.entity-recon": ("gui.src.tabs.web.entity_recon_tab", "EntityReconTab"),
    "ml.training": ("gui.src.tabs.models.train_tab", "UnifiedTrainTab"),
    "ml.generation": ("gui.src.tabs.models.generate_tab", "UnifiedGenerateTab"),
    "ml.evaluation": ("gui.src.tabs.models.r3gan_evaluate_tab", "R3GANEvaluateTab"),
    "ml.inference": ("gui.src.tabs.models.meta_clip_inference_tab", "MetaCLIPInferenceTab"),
    "ml.comfyui": ("gui.src.tabs.models.gen.comfy_generate_tab", "ComfyUITab"),
    "manga.colorization": ("gui.src.tabs", "MangaColorizationTab"),
    "manga.animation": ("gui.src.tabs", "MangaAnimationTab"),
    "manga.puppeteering": ("gui.src.tabs", "MangaPuppeteeringTab"),
    "editor.hybrid": ("gui.src.tabs", "HieEditorTab"),
    "stitch.workspace": ("gui.src.tabs", "StitchTab"),
}


def _load_tab_class(module_id: str) -> type:
    try:
        module_name, class_name = _TAB_LEAVES[module_id]
    except KeyError as exc:
        raise LookupError(f"No tab factory registered for {module_id!r}") from exc
    return getattr(importlib.import_module(module_name), class_name)


def build_tab(module_id: str, context: ModuleContext) -> Any:
    """Construct a legacy tab from its stable module identifier.

    The concrete tab class is imported only at activation time. Both shells
    use this function, so constructor changes have one call site.
    """
    started = time.perf_counter()
    cls = _load_tab_class(module_id)
    vault_manager = context.services.get("vault_manager")
    database_service = context.services.get(LIBRARY_DATABASE_SERVICE)
    event_hub = context.event_hub

    if module_id == "library.listings":
        widget = cls(vault_manager=vault_manager, event_hub=event_hub)
    elif module_id in ("system.convert", "system.similarity"):
        widget = cls(dropdown=context.dropdown)
    elif module_id == "system.wallpaper":
        widget = cls(database_service, event_hub)
    elif module_id == "library.search":
        widget = cls(database_service, event_hub, dropdown=context.dropdown)
    elif module_id == "library.scan":
        widget = cls(database_service, event_hub)
    elif module_id == "library.management":
        widget = cls(vault_manager, database_service=database_service, event_hub=event_hub)
    elif module_id in ("library.data-browser", "web.drive-sync"):
        widget = cls(vault_manager)
    elif module_id == "ml.comfyui":
        widget = cls(enable_manager=context.enable_manager)
    else:
        widget = cls()

    elapsed = time.perf_counter() - started
    logger.info("build_tab %s in %.3fs", module_id, elapsed)
    return widget


__all__ = ["build_tab"]
