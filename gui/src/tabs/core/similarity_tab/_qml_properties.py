"""QML Property accessors and gallery-card rendering for ``SimilarityTab``.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ....components import ClickableLabel


class _QmlPropertiesMixin:
    """scanRunning/confidenceThreshold/selectedFiles Qt Properties and card rendering."""

    # ==================================================================
    # Similarity state accessors
    # ==================================================================
    # NOTE: ``_cluster_model`` (a ClusterListModel) is kept for internal cluster
    # bookkeeping/auto-select. It is intentionally NOT exposed as a Qt Property:
    # this is a native widget tab, and a ``QAbstractListModel*`` property type
    # is not registerable on a plain QObject meta-object (it only warned).

    def _get_scan_running(self) -> bool:
        return self._scan_running

    def _get_conf_threshold(self) -> float:
        return self._sim_config.confidence_threshold

    def _set_conf_threshold(self, value: float):
        self.set_confidence_threshold(value)

    def _get_selected_files(self) -> List[str]:
        return sorted(self.selected_files)

    # ==================================================================
    # Gallery card rendering (from DeleteTab)
    # ==================================================================

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        card_wrapper.set_image_label(img_label)
        if pixmap and not pixmap.isNull():
            img_label.setPixmap(pixmap.scaled(thumb_size, thumb_size,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        card_wrapper.path_double_clicked.connect(self.open_full_preview)
        card_wrapper.path_right_clicked.connect(self.show_image_context_menu)
        card_wrapper.set_selected_style(is_selected, self._update_card_style, img_label)
        return card_wrapper

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        try:
            if not isinstance(widget, ClickableLabel):
                return
            img_label = widget.findChild(QLabel)
            if not img_label:
                return
            if pixmap and not pixmap.isNull():
                thumb_size = self.thumbnail_size
                scaled = pixmap.scaled(thumb_size, thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img_label.setPixmap(scaled)
                img_label.setText("")
            else:
                img_label.clear()
                img_label.setText("Loading...")
            is_selected = widget.path in self.selected_files
            self._update_card_style(img_label, is_selected)
        except RuntimeError:
            pass

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            try:
                px = img_label.pixmap()
                if px and not px.isNull():
                    img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")
                else:
                    img_label.setStyleSheet("border: 1px dashed #666; color: #999;")
            except RuntimeError:
                pass

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_delete_files.setText(f"Delete Selected Files ({count})")
        self.btn_delete_files.setEnabled(count > 0)
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        has_dups = len(self.found_files) > 0
        self.btn_compare_properties.setVisible(has_dups)
        self.btn_compare_properties.setEnabled(count > 0)
        self.selection_changed_qml.emit()


__all__ = ["_QmlPropertiesMixin"]
