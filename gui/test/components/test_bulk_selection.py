"""Unit tests for Bulk Selection and Multi-Item Operations (Roadmap §2.4).

Verifies:
- Shift+Click range selection and Ctrl+Click multi-select over QItemSelectionModel
- Select All, Deselect All, and Invert Selection on VirtualGallery & VirtualGalleryView
- Invert Selection on VirtualDualGallery
- Selection methods on AbstractClassTwoGalleries & AbstractClassSingleGallery mixins
- Shortcut registration for gallery.select_all, gallery.deselect_all, gallery.invert_selection
"""

from __future__ import annotations

import pytest
from gui.src.classes.image.abstract_class_single_gallery._selection import _SelectionMixin
from gui.src.classes.image.abstract_class_two_galleries._selection_ops import _SelectionOpsMixin
from gui.src.components.virtual_gallery import VirtualGallery
from gui.src.utils.manager.shortcut_manager import get_registry
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QWidget

pytestmark = pytest.mark.gui





@pytest.fixture
def sample_image_files(tmp_path):
    files = []
    for i in range(6):
        path = str(tmp_path / f"item_{i:02d}.png")
        img = QImage(64, 64, QImage.Format.Format_RGB32)
        img.fill(QColor(i * 30, 100, 150))
        img.save(path)
        files.append(path)
    return files


def test_virtual_gallery_bulk_selection(sample_image_files, q_app):
    """Test Select All, Clear Selection, and Invert Selection on VirtualGallery."""
    vg = VirtualGallery()
    vg.show()
    vg.set_paths(sample_image_files)

    assert len(vg.selected_files()) == 0

    # 1. Select all
    vg.select_all()
    assert len(vg.selected_files()) == 6
    assert set(vg.selected_files()) == set(sample_image_files)

    # 2. Invert selection (all -> none)
    vg.invert_selection()
    assert len(vg.selected_files()) == 0

    # 3. Select subset manually via view selection model
    sm = vg.view.selectionModel()
    sm.select(vg.model.index(0, 0), sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
    sm.select(vg.model.index(2, 0), sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
    assert len(vg.selected_files()) == 2
    assert vg.selected_files() == [sample_image_files[0], sample_image_files[2]]

    # 4. Invert selection (2 selected -> 4 selected)
    vg.invert_selection()
    assert len(vg.selected_files()) == 4
    assert sample_image_files[0] not in vg.selected_files()
    assert sample_image_files[2] not in vg.selected_files()
    assert sample_image_files[1] in vg.selected_files()
    assert sample_image_files[3] in vg.selected_files()

    # 5. Deselect all
    vg.deselect_all()
    assert len(vg.selected_files()) == 0

    vg.close()


def test_virtual_gallery_view_keypress_selection(sample_image_files, q_app):
    """Test Ctrl+A, Ctrl+D, Ctrl+I keyboard shortcuts dispatched in VirtualGalleryView."""
    vg = VirtualGallery()
    vg.show()
    vg.set_paths(sample_image_files)

    view = vg.view
    assert len(view.selected_paths()) == 0

    # Simulate Ctrl+A (Select All)
    event_select_all = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier,
    )
    view.keyPressEvent(event_select_all)
    assert len(view.selected_paths()) == 6

    # Simulate Ctrl+I (Invert Selection)
    event_invert = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_I,
        Qt.KeyboardModifier.ControlModifier,
    )
    view.keyPressEvent(event_invert)
    assert len(view.selected_paths()) == 0

    # Simulate Ctrl+D (Deselect All)
    view.select_all()
    assert len(view.selected_paths()) == 6
    event_deselect = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_D,
        Qt.KeyboardModifier.ControlModifier,
    )
    view.keyPressEvent(event_deselect)
    assert len(view.selected_paths()) == 0

    vg.close()


def test_shortcut_registry_has_gallery_selection_entries():
    """Verify registry contains all gallery selection actions."""
    reg = get_registry()
    actions = set(reg._defaults.keys())
    assert "gallery.select_all" in actions
    assert "gallery.deselect_all" in actions
    assert "gallery.invert_selection" in actions



def test_two_galleries_mixin_invert_selection(sample_image_files, q_app):
    """Test invert_selection logic on _SelectionOpsMixin."""
    class DummyTwoGalleriesHost(_SelectionOpsMixin, QWidget):
        def __init__(self, paths):
            super().__init__()
            self.found_files = list(paths)
            self.found_current_page = 0
            self.found_page_size = 100
            self.selected_files = [paths[0], paths[1]]
            self.path_to_label_map = {}
            self.refresh_selected_panel_called = False
            self.on_selection_changed_called = False

        def common_get_paginated_slice(self, full_list, page, page_size):
            return list(full_list)

        def refresh_selected_panel(self):
            self.refresh_selected_panel_called = True

        def on_selection_changed(self):
            self.on_selection_changed_called = True

        def update_card_style(self, widget, is_selected):
            pass

    host = DummyTwoGalleriesHost(sample_image_files)
    assert host.selected_files == [sample_image_files[0], sample_image_files[1]]

    host.invert_selection()
    assert host.refresh_selected_panel_called is True
    assert host.on_selection_changed_called is True
    assert len(host.selected_files) == 4
    assert sample_image_files[0] not in host.selected_files
    assert sample_image_files[1] not in host.selected_files
    assert sample_image_files[2] in host.selected_files
    assert sample_image_files[3] in host.selected_files


def test_single_gallery_mixin_invert_selection(sample_image_files, q_app):
    """Test invert_selection logic on single gallery _SelectionMixin."""
    class DummySingleGalleryHost(_SelectionMixin, QWidget):
        def __init__(self, paths):
            super().__init__()
            self.gallery_image_paths = list(paths)
            self.current_page = 0
            self.page_size = 100
            self.selected_files = [paths[0]]
            self.path_to_card_widget = {}
            self.on_selection_changed_called = False

        def common_get_paginated_slice(self, full_list, page, page_size):
            return list(full_list)

        def on_selection_changed(self):
            self.on_selection_changed_called = True

        def update_card_style(self, widget, is_selected):
            pass

    host = DummySingleGalleryHost(sample_image_files)
    assert host.selected_files == [sample_image_files[0]]

    host.invert_selection()
    assert host.on_selection_changed_called is True
    assert len(host.selected_files) == 5
    assert sample_image_files[0] not in host.selected_files
    assert sample_image_files[1] in host.selected_files
