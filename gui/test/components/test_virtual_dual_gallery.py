"""Unit tests for VirtualDualGallery composite (GUI/UX §2.1 & §2.4 dual-panel)."""

import pytest
from gui.src.components.gallery import VirtualDualGallery
from PySide6.QtGui import QColor, QImage

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_paths(tmp_path):
    paths = []
    for name in ["apple_1.png", "apple_2.png", "banana_1.png", "orange_1.png"]:
        p = str(tmp_path / name)
        img = QImage(100, 100, QImage.Format.Format_RGB32)
        img.fill(QColor(100, 150, 200))
        img.save(p)
        paths.append(p)
    return paths


def test_dual_gallery_init(q_app):
    dg = VirtualDualGallery()
    dg.show()
    assert dg.count_found() == 0
    assert dg.count_selected() == 0
    assert dg.found_gallery.model._cache is dg.selected_gallery.model._cache
    dg.close()


def test_dual_gallery_population_and_selection(sample_paths, q_app):
    dg = VirtualDualGallery()
    dg.show()
    dg.set_found_paths(sample_paths)

    assert dg.count_found() == 4
    assert dg.count_selected() == 0

    # 1. Toggle selection
    p0, p1 = sample_paths[0], sample_paths[1]
    res = dg.toggle_selection(p0)
    assert res is True
    assert dg.count_selected() == 1
    assert dg.selected_paths() == [p0]

    dg.toggle_selection(p1)
    assert dg.count_selected() == 2
    assert dg.selected_paths() == [p0, p1]

    # Deselect p0
    res = dg.toggle_selection(p0)
    assert res is False
    assert dg.count_selected() == 1
    assert dg.selected_paths() == [p1]

    # 2. Select All
    dg.select_all()
    assert dg.count_selected() == 4

    # 3. Invert Selection (§2.4E)
    dg.invert_selection()
    assert dg.count_selected() == 0

    dg.toggle_selection(sample_paths[0])
    assert dg.count_selected() == 1
    dg.invert_selection()
    assert dg.count_selected() == 3
    assert sample_paths[0] not in dg.selected_paths()

    # 4. Deselect All
    dg.deselect_all()
    assert dg.count_selected() == 0
    dg.close()



def test_dual_gallery_search_filtering(sample_paths, q_app):
    dg = VirtualDualGallery()
    dg.show()
    dg.set_found_paths(sample_paths)
    dg.toggle_selection(sample_paths[3])  # select orange

    # Apply search filter for "apple"
    dg.txt_found_search.setText("apple")
    dg._apply_search_filter()

    assert dg.count_found() == 2
    assert all("apple" in p for p in dg.found_paths())
    # Selected files remain untouched by Found search filter
    assert dg.count_selected() == 1
    assert dg.selected_paths() == [sample_paths[3]]

    # Clear filter
    dg.txt_found_search.setText("")
    dg._apply_search_filter()
    assert dg.count_found() == 4
    dg.close()


def test_dual_gallery_compare_selected(sample_paths, q_app):
    dg = VirtualDualGallery()
    dg.show()
    dg.set_found_paths(sample_paths)

    # Less than 2 selected -> None
    assert dg.compare_selected() is None

    # Select 2 items -> opens ImageCompareWindow
    dg.toggle_selection(sample_paths[0])
    dg.toggle_selection(sample_paths[1])
    win = dg.compare_selected()
    assert win is not None
    assert len(win.image_paths) == 2
    win.close()
    dg.close()


def test_dual_gallery_clear_and_lifecycle(sample_paths, q_app):
    dg = VirtualDualGallery()
    dg.show()
    dg.set_found_paths(sample_paths)
    dg.select_all()

    dg.cancel_loading()
    dg.clear_cache()
    dg.clear()

    assert dg.count_found() == 0
    assert dg.count_selected() == 0
    assert len(dg.found_paths()) == 0
    assert len(dg.selected_paths()) == 0
    dg.close()
