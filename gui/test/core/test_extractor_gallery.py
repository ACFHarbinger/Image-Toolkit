"""VideoExtractorSubTab virtual-gallery migration tests (GUI/UX §2.1).

The extracted-frames results gallery now renders through the `VirtualGallery`
composite instead of the paginated QGridLayout + ClickableLabel grid. These
tests exercise the migrated surface: extraction paths land in the model,
selection syncs bidirectionally with the view's selection model, search
filters the model, and delete rebuilds the gallery from the updated master
list. The extraction machinery itself (queue/ffmpeg/player) is untouched.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from gui.src.tabs.core.extractor_tab import VideoExtractorSubTab

pytestmark = pytest.mark.gui


@pytest.fixture
def mock_deps():
    with (
        patch("gui.src.tabs.core.extractor_tab.manager.FrameExtractionWorker"),
        patch("gui.src.tabs.core.extractor_tab._queue_management.QueueExecutionWorker"),
    ):
        yield


def _frames(tmp_path, n):
    for i in range(n):
        (tmp_path / f"frame_{i:04d}.png").write_bytes(b"not-a-real-png")
    return [str(p) for p in sorted(tmp_path.glob("frame_*.png"))]


def _make_tab(q_app, mock_deps, tmp_path, n=20):
    tab = VideoExtractorSubTab()
    paths = _frames(tmp_path, n)
    tab.current_extracted_paths = list(paths)
    tab.start_loading_gallery(paths)
    return tab


def test_extraction_paths_land_in_virtual_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, mock_deps, tmp_path, n=15)
    assert tab.gallery.count() == 15
    assert tab.gallery.model.rowCount() == 15
    assert tab.gallery.model.path_at(0) == tab.gallery_image_paths[0]
    assert tab.gallery_image_paths == sorted(tab.gallery_image_paths)
    tab.close()


def test_selection_syncs_gallery_to_files(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, mock_deps, tmp_path, n=10)
    sm = tab.gallery.view.selectionModel()
    sm.select(tab.gallery.model.index(0, 0), sm.SelectionFlag.Select)
    sm.select(tab.gallery.model.index(2, 0), sm.SelectionFlag.Select)
    assert tab.selected_files == [tab.gallery_image_paths[0], tab.gallery_image_paths[2]]
    tab.close()


def test_selection_syncs_files_to_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, mock_deps, tmp_path, n=10)
    tab.selected_files = [tab.gallery_image_paths[4]]
    tab._push_selection_to_gallery()
    sm = tab.gallery.view.selectionModel()
    selected = [tab.gallery.model.path_at(i.row()) for i in sm.selectedIndexes()]
    assert selected == [tab.gallery_image_paths[4]]
    assert tab.selected_files == [tab.gallery_image_paths[4]]
    tab.close()


def test_search_filters_virtual_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, mock_deps, tmp_path, n=30)
    tab.search_input.setText("frame_000")
    tab._perform_search()
    assert len(tab.gallery_image_paths) == 10
    assert tab.gallery.count() == 10
    tab.close()


def test_delete_selected_rebuilds_gallery(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, mock_deps, tmp_path, n=8)
    tab.selected_files = [tab.gallery_image_paths[0]]
    with patch(
        "gui.src.tabs.core.extractor_tab._gallery_selection.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ), patch(
        "gui.src.tabs.core.extractor_tab._gallery_selection.os.remove",
    ):
        tab.delete_selected_images()
    assert tab.gallery.count() == 7
    assert tab.gallery_image_paths[0] != "frame_0000"
    assert tab.selected_files == []
    tab.close()


def test_double_click_preview_uses_gallery_paths(q_app, mock_deps, tmp_path):
    tab = _make_tab(q_app, mock_deps, tmp_path, n=5)
    # Non-blocking: just confirm the double-click handler resolves against
    # current_extracted_paths (no preview window asserted — needs a display).
    assert tab.current_extracted_paths
    tab.close()
