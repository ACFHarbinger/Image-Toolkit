"""Worker and helper implementations — lazily re-exported (issues #530, #573, R3.6)."""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    "CodecConversionWorker": ".core.codec_conversion_worker",
    "ConversionWorker": ".core.conversion_worker",
    "DeletionWorker": ".core.deletion_worker",
    "DirectoryScanWorker": ".core.directory_scan_worker",
    "DuplicateScanWorker": ".core.duplicate_scan_worker",
    "MergeWorker": ".core.merge_worker",
    "SamplerWorker": ".core.sampler_worker",
    "SimilarityScanWorker": ".core.similarity_scan_worker",
    "ScrollVideoExportWorker": ".core.video_export_worker",
    "WallpaperWorker": ".core.wallpaper_worker",
    "ImageEmbeddingWorker": ".database.embedding_worker",
    "ListingsEmbeddingWorker": ".database.listings_embedding_worker",
    "ListingsSemanticSearchWorker": ".database.listings_semantic_search_worker",
    "SearchWorker": ".database.search_worker",
    "SemanticSearchWorker": ".database.semantic_search_worker",
    "UpsertWorker": ".database.upsert_worker",
    "BatchImageLoaderWorker": ".image.batch_image_loader_worker",
    "ImageLoaderWorker": ".image.image_loader_worker",
    "ImageScannerWorker": ".image.image_scan_worker",
    "BatchVideoLoaderWorker": ".video.batch_video_loader_worker",
    "CodecScanWorker": ".video.codec_scan_worker",
    "FrameExtractionWorker": ".video.frame_extractor_worker",
    "GifCreationWorker": ".video.gif_extractor_worker",
    "VideoExtractionWorker": ".video.video_extractor_worker",
    "VideoLoaderWorker": ".video.video_loader_worker",
    "VideoScannerWorker": ".video.video_scan_worker",
    "CloudDriveSyncWorker": ".web",
    "LocalDirSyncWorker": ".web",
    "ImageCrawlWorker": ".web.image_crawl_worker",
    "MediaLoaderWorker": ".web.media_loader_worker",
    "ReverseSearchWorker": ".web.reverse_search_worker",
    "WebRequestsWorker": ".web.web_requests_worker",
}

__all__ = [
    "CodecConversionWorker",
    "ConversionWorker",
    "DeletionWorker",
    "DirectoryScanWorker",
    "DuplicateScanWorker",
    "MergeWorker",
    "SamplerWorker",
    "SimilarityScanWorker",
    "ScrollVideoExportWorker",
    "WallpaperWorker",
    "ImageEmbeddingWorker",
    "ListingsEmbeddingWorker",
    "ListingsSemanticSearchWorker",
    "SearchWorker",
    "SemanticSearchWorker",
    "UpsertWorker",
    "BatchImageLoaderWorker",
    "ImageLoaderWorker",
    "ImageScannerWorker",
    "BatchVideoLoaderWorker",
    "CodecScanWorker",
    "FrameExtractionWorker",
    "GifCreationWorker",
    "VideoExtractionWorker",
    "VideoLoaderWorker",
    "VideoScannerWorker",
    "CloudDriveSyncWorker",
    "LocalDirSyncWorker",
    "ImageCrawlWorker",
    "MediaLoaderWorker",
    "ReverseSearchWorker",
    "WebRequestsWorker",
]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
