"""Regression tests for the lazy gui.src.windows facade (issue #530, D9).

Importing the package must stay cheap (no eager submodule imports — pinned
structurally by backend/validation/check_init_boundaries.py in CI); these
tests pin the other half: the public surface resolves to the exact same
objects as direct submodule imports.
"""

import importlib

import gui.src.windows as windows_pkg
from gui.src.windows import _LAZY_EXPORTS

EXPECTED = {
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


def test_lazy_map_covers_documented_surface():
    assert _LAZY_EXPORTS == EXPECTED


def test_all_entries_resolve_through_the_map():
    assert set(windows_pkg.__all__) <= set(_LAZY_EXPORTS)


def test_each_export_is_identical_to_direct_submodule_import():
    for name, relative_module in EXPECTED.items():
        module = importlib.import_module(relative_module, "gui.src.windows")
        assert getattr(windows_pkg, name) is getattr(module, name), name


def test_unknown_attribute_still_raises_attribute_error():
    try:
        windows_pkg.__getattr__("NoSuchWindow")
    except AttributeError:
        return
    raise AssertionError("expected AttributeError for unknown window name")
