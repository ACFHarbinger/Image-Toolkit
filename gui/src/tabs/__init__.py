"""Tab classes — lazily re-exported (issues #530, #549, #573, R3.6)."""

from __future__ import annotations

import importlib

# Public contract checked by gui/test/modules/test_tabs_init_lazy.py (#549):
# the submodule-GUI subset of _LAZY_EXPORTS, kept as its own name so a
# caller can enumerate just the lazy submodule boundary without depending
# on _LAZY_EXPORTS' full shape.
_LAZY_SUBMODULE_EXPORTS = {
    "StitchTab": "asp_gui.tabs",
    "StitchTabBackend": "asp_gui.tabs",
    "MangaAnimationTab": "csg_gui.tabs",
    "MangaColorizationTab": "csg_gui.tabs",
    "MangaPuppeteeringTab": "csg_gui.tabs",
    "HieEditorTab": "hie_tab",
}

_LAZY_EXPORTS = {
    # Submodules (ui-arch-27/#549) — kept as literal entries, not
    # `**_LAZY_SUBMODULE_EXPORTS`: check_init_boundaries.py's AST checker
    # requires every _LAZY_EXPORTS key to be a plain string constant, and a
    # dict-unpack key isn't one.
    "StitchTab": "asp_gui.tabs",
    "StitchTabBackend": "asp_gui.tabs",
    "MangaAnimationTab": "csg_gui.tabs",
    "MangaColorizationTab": "csg_gui.tabs",
    "MangaPuppeteeringTab": "csg_gui.tabs",
    "HieEditorTab": "hie_tab",
    # Core tabs
    "ConvertTab": ".core.convert_tab",
    "ExtractorTab": ".core.extractor_tab",
    "MergeTab": ".core.merge_tab",
    "SimilarityTab": ".core.similarity_tab",
    "WallpaperTab": ".core.wallpaper_tab",
    "codec_subtab": ".core",
    "convert_tab": ".core",
    "extractor_tab": ".core",
    "format_subtab": ".core",
    "image_extractor_subtab": ".core",
    "merge_tab": ".core",
    "sampler_subtab": ".core",
    "similarity_tab": ".core",
    "wallpaper_tab": ".core",
    # Database tabs
    "DatabaseTab": ".database.database_tab",
    "DataBrowserTab": ".database.data_browser_tab",
    "ScanMetadataTab": ".database.scan_metadata_tab",
    "SearchTab": ".database.search_tab",
    "database_tab": ".database",
    "data_browser_tab": ".database",
    "scan_metadata_tab": ".database",
    "search_tab": ".database",
    # Models tabs
    "CBIRTrainTab": ".models.cbir_train_tab",
    "ComfyUITab": ".models.comfyui_tab",
    "MetaCLIPInferenceTab": ".models.meta_clip_inference_tab",
    "R3GANEvaluateTab": ".models.r3gan_evaluate_tab",
    "UnifiedGenerateTab": ".models.unified_generate_tab",
    "UnifiedTrainTab": ".models.unified_train_tab",
    "cbir_train_tab": ".models",
    "comfyui_tab": ".models",
    "meta_clip_inference_tab": ".models",
    "r3gan_evaluate_tab": ".models",
    "unified_generate_tab": ".models",
    "unified_train_tab": ".models",
    # Web tabs
    "DriveSyncTab": ".web.drive_sync_tab",
    "EntityReconTab": ".web.entity_recon_tab",
    "ImageCrawlTab": ".web.image_crawler_tab",
    "MediaLoaderTab": ".web.media_loader_tab",
    "ReverseImageSearchTab": ".web.reverse_search_tab",
    "WebRequestsTab": ".web.web_requests_tab",
    "drive_sync_tab": ".web",
    "entity_recon_tab": ".web",
    "image_crawler_tab": ".web",
    "media_loader_tab": ".web",
    "reverse_search_tab": ".web",
    "web_requests_tab": ".web",
    # Subpackages
    "core": ".core",
    "database": ".database",
    "models": ".models",
    "web": ".web",
}

__all__ = [
    "ConvertTab",
    "ExtractorTab",
    "MergeTab",
    "SimilarityTab",
    "WallpaperTab",
    "codec_subtab",
    "convert_tab",
    "extractor_tab",
    "format_subtab",
    "image_extractor_subtab",
    "merge_tab",
    "sampler_subtab",
    "similarity_tab",
    "wallpaper_tab",
    "DatabaseTab",
    "DataBrowserTab",
    "ScanMetadataTab",
    "SearchTab",
    "database_tab",
    "data_browser_tab",
    "scan_metadata_tab",
    "search_tab",
    "CBIRTrainTab",
    "ComfyUITab",
    "MetaCLIPInferenceTab",
    "R3GANEvaluateTab",
    "UnifiedGenerateTab",
    "UnifiedTrainTab",
    "cbir_train_tab",
    "comfyui_tab",
    "meta_clip_inference_tab",
    "r3gan_evaluate_tab",
    "unified_generate_tab",
    "unified_train_tab",
    "DriveSyncTab",
    "EntityReconTab",
    "ImageCrawlTab",
    "MediaLoaderTab",
    "ReverseImageSearchTab",
    "WebRequestsTab",
    "drive_sync_tab",
    "entity_recon_tab",
    "image_crawler_tab",
    "media_loader_tab",
    "reverse_search_tab",
    "web_requests_tab",
    "StitchTab",
    "StitchTabBackend",
    "MangaAnimationTab",
    "MangaColorizationTab",
    "MangaPuppeteeringTab",
    "HieEditorTab",
    "core",
    "database",
    "models",
    "web",
]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        target = _LAZY_EXPORTS[name]
        if target.startswith("."):
            module = importlib.import_module(target, __name__)
            value = getattr(module, name) if target.count(".") > 1 else module
        else:
            module = importlib.import_module(target)
            value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
