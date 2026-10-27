"""Load core wrappers on demand so vault startup does not load image/ML engines."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    'DuplicateFinder': 'duplicate_finder',
    'FileDeleter': 'file_system_entries',
    'FSETool': 'file_system_entries',
    'ImageFormatConverter': 'image',
    'ImageMerger': 'image',
    'PhashDeduplicator': 'phash_deduplicator',
    'compute_phash': 'phash_deduplicator',
    'SimilarityCache': 'similarity',
    'SimilarityConfig': 'similarity',
    'SimilarityEngine': 'similarity',
    'SimilarityReport': 'similarity',
    'TriageRules': 'similarity',
    'SimilarityFinder': 'similarity_finder',
    'VaultManager': 'vault_manager',
    'VideoFormatConverter': 'video',
    'probe_audio_codec': 'video',
    'probe_codecs': 'video',
    'probe_video_codec': 'video',
    'WallpaperManager': 'wallpaper',
    'evaluate_kde_script_dbus_python': 'wallpaper',
    'evaluate_kde_script_with_fallback': 'wallpaper',
    'find_qdbus_binary': 'wallpaper',
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value
