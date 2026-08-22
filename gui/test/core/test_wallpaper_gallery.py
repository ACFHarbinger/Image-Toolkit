"""Wallpaper subtab virtual-gallery migration tests (GUI/UX §2.1).

The wallpaper subtabs' gallery (MarqueeScrollArea + QGridLayout) is replaced
by the virtual-scroll VirtualGallery with the custom drag-to-monitor enabled.
"""

from __future__ import annotations

import types

import pytest

from gui.src.tabs.core.wallpaper_tab.monitor_display_subtab import MonitorDisplaySubTab
from gui.src.tabs.core.wallpaper_tab.system_display_subtab import SystemDisplaySubTab

pytestmark = pytest.mark.gui


def _paths(tmp_path, n):
    for i in range(n):
        (tmp_path / f"img_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("img_*.png"))]


def _make_system(q_app, tmp_path, n=8):
    tab = SystemDisplaySubTab(db_tab_ref=types.SimpleNamespace(db=None))
    tab.start_loading_gallery(_paths(tmp_path, n))
    return tab


def _make_monitor(q_app, tmp_path, n=8):
    tab = MonitorDisplaySubTab()
    tab.start_loading_gallery(_paths(tmp_path, n))
    return tab


@pytest.mark.parametrize("make", [_make_system, _make_monitor], ids=["system", "monitor"])
def test_scan_lands_in_virtual_gallery(q_app, tmp_path, make):
    tab = make(q_app, tmp_path, n=8)
    assert tab.gallery.count() == 8
    assert tab.gallery.model.rowCount() == 8
    assert tab.gallery_image_paths == tab.gallery.model._paths
    tab.close()


@pytest.mark.parametrize("make", [_make_system, _make_monitor], ids=["system", "monitor"])
def test_selection_toggle(q_app, tmp_path, make):
    tab = make(q_app, tmp_path, n=6)
    tab.toggle_selection(tab.gallery_image_paths[0])
    assert tab.selected_files == [tab.gallery_image_paths[0]]
    tab.close()


@pytest.mark.parametrize("make", [_make_system, _make_monitor], ids=["system", "monitor"])
def test_custom_drag_enabled(q_app, tmp_path, make):
    tab = make(q_app, tmp_path, n=4)
    assert tab.gallery.view._custom_drag_enabled is True
    assert callable(tab.gallery.view._custom_drop_handler)
    tab.close()


def test_drag_drop_handler_no_target_is_noop(q_app, tmp_path):
    tab = _make_system(q_app, tmp_path, n=4)
    from PySide6.QtCore import QPoint

    # No widget under the cursor (offscreen) -> the walk simply no-ops.
    tab._on_gallery_drag_drop(tab.gallery_image_paths[0], [tab.gallery_image_paths[0]], QPoint(0, 0))
    tab.close()
