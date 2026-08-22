"""ReverseImageSearchTab virtual-gallery migration tests (GUI/UX §2.1).

The tab now renders its scanned directory through the `VirtualGallery`
composite (QListView + QAbstractListModel) instead of a paginated
QGridLayout + ClickableLabel grid. These tests exercise the new surface:
scan results land in the model, the search box filters the model, selection
maps onto the view's selection model, and Ctrl+wheel zoom resizes the
gallery. The scan thread itself is bypassed (results are fed directly to
`on_scan_finished`), matching how the tab consumes `ImageScannerWorker`.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from gui.src.tabs.web.reverse_search_tab import ReverseImageSearchTab

pytestmark = pytest.mark.gui


@pytest.fixture
def mock_deps():
    with (
        patch("gui.src.tabs.web.reverse_search_tab.ImageScannerWorker"),
        patch("gui.src.tabs.web.reverse_search_tab.ReverseSearchWorker"),
    ):
        yield


def _paths(tmp_path, n):
    for i in range(n):
        (tmp_path / f"img_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("*.png"))]


def _make_tab(q_app, tmp_path, n=40) -> ReverseImageSearchTab:
    tab = ReverseImageSearchTab()
    tab.on_scan_finished(_paths(tmp_path, n))
    return tab


def test_scan_populates_virtual_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=25)
    assert tab.gallery.count() == 25
    assert len(tab.gallery_image_paths) == 25
    # Every scanned path is a model row — no page cap, no card widgets.
    assert tab.gallery.model.rowCount() == 25
    assert tab.gallery.model.path_at(0) == tab.gallery_image_paths[0]
    assert tab.gallery.model.path_at(24) == tab.gallery_image_paths[-1]
    tab.close()


def test_empty_scan_clears_gallery(q_app, mock_deps, tmp_path):
    tab = ReverseImageSearchTab()
    tab.gallery.set_paths(["/a.png"])
    tab.on_scan_finished([])
    assert tab.gallery.count() == 0
    assert tab.gallery_image_paths == []
    tab.close()


def test_search_box_filters_virtual_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=30)
    # The base wires search_input.textChanged -> debounce -> _perform_search.
    tab.search_input.setText("img_000")
    tab._perform_search()
    # "img_000" matches img_0000..img_0009 (10 rows).
    assert len(tab.gallery_image_paths) == 10
    assert tab.gallery.count() == 10
    tab.close()


def test_selection_maps_onto_view_selection_model(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=20)
    target = tab.gallery_image_paths[3]
    tab.handle_image_selection(target)
    assert tab.selected_source_path == target
    assert tab.btn_search.isEnabled()
    assert tab.lbl_selected_path.text() == os.path.basename(target)
    # The single-selection is reflected in the view's selection model.
    sm = tab.gallery.view.selectionModel()
    selected = [tab.gallery.model.path_at(i.row()) for i in sm.selectedIndexes()]
    assert selected == [target]
    tab.close()


def test_select_all_delegates_to_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=15)
    tab.select_all_items()
    assert len(tab.gallery.selected_files()) == 15
    tab.deselect_all_items()
    assert tab.gallery.selected_files() == []
    tab.close()


def test_ctrl_wheel_zoom_resizes_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=10)
    before = tab.thumbnail_size
    tab._on_ctrl_wheel_zoom(120)  # zoom in
    assert tab.thumbnail_size == min(512, before + 16)
    assert tab.gallery.thumbnail_size == tab.thumbnail_size
    assert tab.gallery.view.iconSize().width() == tab.thumbnail_size
    tab.close()


def test_gallery_model_qml_property_still_populated(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=12)
    model = tab.gallery_model
    assert len(model) == 12
    assert all("path" in item and "name" in item for item in model)
    tab.close()
