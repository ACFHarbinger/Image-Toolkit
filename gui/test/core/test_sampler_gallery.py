"""SamplerSubTab virtual dual-gallery migration tests (GUI/UX §2.1).

The found/selected card grids are replaced by a ``VirtualDualGallery``.
"""

from __future__ import annotations

import pytest

from gui.src.tabs.core.sampler_subtab import SamplerSubTab

pytestmark = pytest.mark.gui


def _paths(tmp_path, n):
    for i in range(n):
        (tmp_path / f"img_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("img_*.png"))]


def _make_tab(q_app, tmp_path, n=10):
    tab = SamplerSubTab()
    tab.start_loading_thumbnails(_paths(tmp_path, n))
    return tab


def test_scan_lands_in_found_panel(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=8)
    assert tab.dual.count_found() == 8
    assert tab.found_files == tab.dual.master_found_paths()
    assert tab.dual.count_selected() == 0
    tab.close()


def test_toggle_selection_updates_selected_panel_and_button(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    tab.toggle_selection(tab.found_files[0])
    tab.toggle_selection(tab.found_files[2])
    assert tab.selected_files == [tab.found_files[0], tab.found_files[2]]
    assert tab.dual.count_selected() == 2
    assert tab.btn_selected.isEnabled()
    assert "2" in tab.btn_selected.text()
    tab.close()


def test_toggle_off_removes_from_selection(q_app, tmp_path):
    tab = _make_tab(q_app, tmp_path, n=6)
    tab.toggle_selection(tab.found_files[2])
    tab.toggle_selection(tab.found_files[2])
    assert tab.dual.count_selected() == 0
    assert not tab.btn_selected.isEnabled()
    tab.close()
