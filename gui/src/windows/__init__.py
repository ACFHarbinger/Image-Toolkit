"""Top-level window classes — lazily re-exported (issue #530, D9).

Importing this package must stay cheap: it must NOT eagerly import every
window submodule (that pulls ``MainWindow`` and the world at package-import
time — half of the import-graph collapse in report §1 finding 5).
Submodules load on first attribute access via PEP 562 ``__getattr__``; the
public surface is unchanged. Guarded by
``backend/validation/check_init_boundaries.py`` (fails CI on any eager
submodule import added here).
"""

import importlib

_LAZY_EXPORTS = {
    "LoginWindow": ".authentication",
    "CloudComputeWindow": ".cloud",
    "DragPreviewWindow": ".drag_preview_window",
    "ImageCompareWindow": ".image_compare_window",
    "ImagePreviewWindow": ".image_preview_window",
    "LogBackend": ".logging",
    "LogWindow": ".logging",
    "MainWindow": ".main",
    "show_main_status": ".main",
    "show_tray_notification": ".main",
    "MetadataEditorWindow": ".metadata",
    "SettingsBackend": ".settings",
    "SettingsWindow": ".settings",
    "SlideshowBackend": ".slideshow_backend",
    "SlideshowQueueWindow": ".slideshow_window",
}

__all__ = [
    "CloudComputeWindow",
    "DragPreviewWindow",
    "MetadataEditorWindow",
    "ImageCompareWindow",
    "ImagePreviewWindow",
    "SlideshowBackend",
    "SlideshowQueueWindow",
    "LogBackend",
    "LogWindow",
    "SettingsBackend",
    "SettingsWindow",
    "LoginWindow",
    "MainWindow",
]


def __getattr__(name):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
