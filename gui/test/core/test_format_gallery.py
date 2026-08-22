"""FormatSubTab virtual dual-gallery migration tests (GUI/UX §2.1).

The found/selected card grids are replaced by a ``VirtualDualGallery``.
These tests exercise the migrated surface: scan results land in the found
panel, toggle-selection updates the selected panel and convert button, and
delete rebuilds both panels.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from gui.src.tabs.core.format_subtab import FormatSubTab

pytestmark = pytest.mark.gui


def _paths(tmp_path, n):
    for i in range(n):
        (tmp_path / f"img_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("img_*.png"))]


def _make_tab(q_app, tmp_path, n=12):
    tab = FormatSubTab()
    tab.start_loading_thumbnails(_paths(tmp_path, n))
    return tab


def test_scan_lands_in_found_panel(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=10)
    assert tab.dual.count_found() == 10
    assert tab.found_files == tab.dual.master_found_paths()
    assert tab.dual.count_selected() == 0
    tab.close()


def test_toggle_selection_updates_selected_panel_and_button(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=8)
    tab.toggle_selection(tab.found_files[0])
    tab.toggle_selection(tab.found_files[3])
    assert tab.selected_files == [tab.found_files[0], tab.found_files[3]]
    assert tab.dual.count_selected() == 2
    assert tab.btn_convert_contents.isEnabled()
    assert "2" in tab.btn_convert_contents.text()
    tab.close()


def test_toggle_off_removes_from_selection(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    tab.toggle_selection(tab.found_files[2])
    assert tab.dual.count_selected() == 1
    tab.toggle_selection(tab.found_files[2])
    assert tab.dual.count_selected() == 0
    assert not tab.btn_convert_contents.isEnabled()
    tab.close()


def test_delete_rebuilds_both_panels(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=8)
    tab.selected_files = [tab.found_files[0]]
    with patch(
        "gui.src.tabs.core.format_subtab._preview_context.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ), patch(
        "gui.src.tabs.core.format_subtab._preview_context.send2trash",
    ):
        tab.handle_delete_image(tab.found_files[0])
    assert tab.found_files[0] != "img_0000"
    assert tab.dual.count_found() == 7
    assert tab.dual.count_selected() == 0
    tab.close()


def test_empty_scan_leaves_empty_found_panel(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=0)
    assert tab.dual.count_found() == 0
    tab.close()
