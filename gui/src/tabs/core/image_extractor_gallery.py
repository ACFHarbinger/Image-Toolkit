"""Source-folder gallery for the Extractor tab's Image sub-tab.

The image counterpart of the Video sub-tab's "Available Media" gallery: pick
a folder, see its images and GIFs as thumbnails, click one to load it into
the frame-cutting canvas. Thumbnails come from a ``VirtualGallery`` (lazy,
off-thread loading); the gallery's top and bottom borders can be dragged to
change its height.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...components.containers.height_resize_grip import enable_height_resize
from ...components.virtual_gallery import VirtualGallery
from ...utils.sort_utils import natural_sort_key

SOURCE_GALLERY_HEIGHT = 300
SOURCE_THUMBNAIL_SIZE = 120
_IMAGE_SUFFIXES = {f".{ext.lower()}" for ext in SUPPORTED_IMG_FORMATS}


def list_source_images(directory: str) -> List[str]:
    """Images and GIFs directly inside *directory*, in natural sort order."""
    try:
        entries = sorted(os.scandir(directory), key=lambda e: natural_sort_key(e.name))
    except OSError:
        return []
    return [e.path for e in entries if e.is_file() and Path(e.name).suffix.lower() in _IMAGE_SUFFIXES]


class ImageSourceGallery(QWidget):
    """"Source Directory" picker plus the "Available Images" gallery."""

    image_chosen = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None, settings_scope: str = "ImageExtractorSubTab"):
        super().__init__(parent)
        self.source_dir = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        dir_group = QGroupBox("Source Directory")
        dir_layout = QHBoxLayout(dir_group)
        self.line_edit_dir = QLineEdit()
        self.line_edit_dir.setPlaceholderText("Select a folder containing images or GIFs...")
        self.line_edit_dir.returnPressed.connect(lambda: self.scan_directory(self.line_edit_dir.text()))
        self.btn_browse_dir = QPushButton("Browse...")
        self.btn_browse_dir.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.line_edit_dir)
        dir_layout.addWidget(self.btn_browse_dir)
        layout.addWidget(dir_group)

        self.gallery_group = QGroupBox("Available Images")
        gallery_layout = QVBoxLayout(self.gallery_group)
        self.gallery = VirtualGallery(self.gallery_group)
        self.gallery.setObjectName("image_extractor_source_gallery")
        self.gallery.set_thumbnail_size(SOURCE_THUMBNAIL_SIZE)
        self.gallery.setFixedHeight(SOURCE_GALLERY_HEIGHT)
        self.gallery.path_clicked.connect(self.image_chosen)
        gallery_layout.addWidget(self.gallery)
        layout.addWidget(self.gallery_group)
        enable_height_resize(
            self.gallery, settings_scope=settings_scope, settings_key="gallery_height/source"
        )

    @Slot()
    def browse_directory(self) -> None:
        # Non-native dialog, as everywhere in this app (native GTK + JVM crash).
        d = QFileDialog.getExistingDirectory(
            self,
            "Select Source Directory",
            self.source_dir or os.path.expanduser("~"),
            QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly,
        )
        if d:
            self.scan_directory(d)

    def scan_directory(self, path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        self.source_dir = path
        self.line_edit_dir.setText(path)
        paths = list_source_images(path)
        self.gallery.set_paths(paths)
        self.gallery_group.setTitle(f"Available Images ({len(paths)})")
        return True

    def mark_current(self, path: Optional[str]) -> None:
        """Highlight the image currently loaded in the canvas."""
        self.gallery.set_preview([path] if path else [])

    def cancel_loading(self) -> None:
        self.gallery.cancel_loading()


__all__ = ["ImageSourceGallery", "list_source_images"]
