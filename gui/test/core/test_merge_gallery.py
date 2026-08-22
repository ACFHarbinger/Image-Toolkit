"""MergeTab virtual-gallery migration tests (GUI/UX §2.1).

The Image Library gallery now renders through the `VirtualGallery` composite
(MultiSelection mode preserves click-to-toggle + native highlight) and the
merge selection syncs with the canvas/queue via the view's selection model.
These tests exercise the migrated surface; the queue strip and canvas are
untouched.
"""

from __future__ import annotations

import pytest

from gui.src.tabs.core.merge_tab import MergeTab

pytestmark = pytest.mark.gui


def _paths(tmp_path, n):
    for i in range(n):
        (tmp_path / f"img_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("img_*.png"))]


def _make_tab(q_app, tmp_path, n=15):
    tab = MergeTab()
    tab.start_loading_gallery(_paths(tmp_path, n))
    return tab


def test_scan_lands_in_virtual_gallery(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=12)
    assert tab.gallery.count() == 12
    assert tab.gallery.model.rowCount() == 12
    assert tab.gallery_image_paths[0] == tab.gallery.model.path_at(0)
    tab.close()


def test_selection_syncs_to_selected_files(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=10)
    sm = tab.gallery.view.selectionModel()
    sm.select(tab.gallery.model.index(0, 0), sm.SelectionFlag.Select)
    sm.select(tab.gallery.model.index(1, 0), sm.SelectionFlag.Select)
    assert tab.selected_files == [tab.gallery_image_paths[0], tab.gallery_image_paths[1]]
    assert tab.run_button.isEnabled()
    tab.close()


def test_toggle_selection_api_toggles(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=8)
    tab.toggle_selection(tab.gallery_image_paths[3])
    assert tab.gallery_image_paths[3] in tab.selected_files
    tab.toggle_selection(tab.gallery_image_paths[3])
    assert tab.gallery_image_paths[3] not in tab.selected_files
    tab.close()


def test_push_selection_to_gallery(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    tab.selected_files = [tab.gallery_image_paths[5]]
    tab._push_selection_to_gallery()
    sm = tab.gallery.view.selectionModel()
    selected = [tab.gallery.model.path_at(i.row()) for i in sm.selectedIndexes()]
    assert selected == [tab.gallery_image_paths[5]]
    tab.close()


def test_search_filters_gallery(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=30)
    tab.search_input.setText("img_000")
    tab._perform_search()
    assert tab.gallery.count() == 10
    tab.close()


def test_run_button_disabled_under_two(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    assert not tab.run_button.isEnabled()
    sm = tab.gallery.view.selectionModel()
    sm.select(tab.gallery.model.index(0, 0), sm.SelectionFlag.Select)
    assert not tab.run_button.isEnabled()  # 1 selected
    sm.select(tab.gallery.model.index(1, 0), sm.SelectionFlag.Select)
    assert tab.run_button.isEnabled()  # 2 selected
    tab.close()
