"""ScanMetadataTab virtual dual-gallery migration tests (GUI/UX §2.1).

The scan-results + selected grids are replaced by a ``VirtualDualGallery``;
scan results land in the found panel, selection syncs with the dual, and the
in-database flag drives the green-border delegate styling.
"""

from __future__ import annotations

import types

import pytest

from gui.src.tabs.database.scan_metadata_tab import ScanMetadataTab

pytestmark = pytest.mark.gui


def _paths(tmp_path, n):
    for i in range(n):
        (tmp_path / f"img_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("img_*.png"))]


def _make_tab(q_app, tmp_path, n=10):
    tab = ScanMetadataTab(db_tab_ref=types.SimpleNamespace(db=None))
    tab.scan_image_list = _paths(tmp_path, n)
    tab.apply_scan_filters()
    return tab


def test_scan_lands_in_found_panel(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=8)
    assert tab.dual.count_found() == 8
    assert tab.scan_filtered_list == tab.dual.master_found_paths()
    assert tab.dual.count_selected() == 0
    tab.close()


def test_toggle_selection_syncs_set_and_dual(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    tab.toggle_selection(tab.scan_filtered_list[0])
    tab.toggle_selection(tab.scan_filtered_list[2])
    assert tab.selected_image_paths == {tab.scan_filtered_list[0], tab.scan_filtered_list[2]}
    assert tab.dual.count_selected() == 2
    assert "2" in tab.upsert_button.text()
    tab.close()


def test_toggle_off_removes_from_selection(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    tab.toggle_selection(tab.scan_filtered_list[2])
    tab.toggle_selection(tab.scan_filtered_list[2])
    assert tab.selected_image_paths == set()
    assert tab.dual.count_selected() == 0
    tab.close()


def test_in_db_flag_styling(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    model = tab.dual.found_gallery.model
    assert model.is_in_db(tab.scan_filtered_list[0]) is False
    model.mark_in_db(tab.scan_filtered_list[0], True)
    assert model.is_in_db(tab.scan_filtered_list[0]) is True
    assert model.data(model.index(0, 0), model.InDbRole) is True
    tab.close()


def test_keyboard_select_all(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=8)
    tab._select_all_images()
    assert len(tab.selected_image_paths) == 8
    tab._deselect_all_images()
    assert tab.selected_image_paths == set()
    tab.close()
