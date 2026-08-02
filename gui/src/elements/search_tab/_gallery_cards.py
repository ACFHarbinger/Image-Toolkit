"""Gallery card creation/styling for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from ...components import DraggableLabel


class _GalleryCardsMixin:
    """Implements the AbstractClassTwoGalleries card-widget abstract methods."""

    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        """
        Creates a DraggableLabel for the Search Tab gallery.
        Returns the label directly — no QWidget wrapper needed.
        """
        image_label = DraggableLabel(
            path, self.thumbnail_size, selection_provider=lambda: self.selected_files
        )
        image_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

        # Wire up the ClickableLabel-compatible style callback so the base
        # class can call image_label.set_selected_style(bool) transparently.
        image_label.set_selected_style(
            is_selected, callback=self._update_card_style
        )

        # Connect signals
        image_label.path_clicked.connect(
            lambda checked, p=path: self.toggle_selection(p)
        )
        image_label.path_double_clicked.connect(self.open_file_preview)
        image_label.path_right_clicked.connect(
            lambda pos, p=path, w=image_label: self.show_context_menu(pos, p, w)
        )

        if pixmap and not pixmap.isNull():
            if (
                pixmap.width() > self.thumbnail_size
                or pixmap.height() > self.thumbnail_size
            ):
                pixmap = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            image_label.setPixmap(pixmap)
        else:
            image_label.setText("Loading...")
            image_label.setStyleSheet("color: #888; font-size: 10px;")

        # Apply initial selection style
        self._update_card_style(image_label, is_selected)

        return image_label

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        """
        Called by lazy loader when pixmap is ready or unloaded.
        'widget' is the DraggableLabel returned by create_card_widget.
        """
        if not isinstance(widget, DraggableLabel):
            return
        image_label = widget
        if pixmap and not pixmap.isNull():
            if (
                pixmap.width() > self.thumbnail_size
                or pixmap.height() > self.thumbnail_size
            ):
                pixmap = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            image_label.setPixmap(pixmap)
            image_label.setText("")
        else:
            image_label.clear()
            image_label.setText("Loading...")

        is_selected = image_label.file_path in self.selected_files
        self._update_card_style(image_label, is_selected)

    def on_selection_changed(self):
        # The base class method is sufficient here.
        pass

    def _update_card_style(self, label: QLabel, is_selected: bool):
        if is_selected:
            label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if label.text() == "Loading...":
                label.setStyleSheet("border: 1px dashed #666; color: #888;")
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")

    # --- Selection Logic Overrides/Helpers ---

    @Slot()
    def select_all_results(self):
        # Calls the inherited select_all_items which handles state update and UI refresh
        self.select_all_items()

    @Slot()
    def deselect_all_results(self):
        # Calls the inherited deselect_all_items which handles state update and UI refresh
        self.deselect_all_items()

    def _update_found_card_styles(self):
        """Helper to re-evaluate and apply style to all currently loaded/visible found cards."""
        for path, widget in self.path_to_label_map.items():
            if widget:
                # Find the ClickableLabel to extract the path and the internal QLabel for styling
                image_label = widget.findChild(QLabel)
                if image_label:
                    is_selected = path in self.selected_files
                    self._update_card_style(image_label, is_selected)


__all__ = ["_GalleryCardsMixin"]
