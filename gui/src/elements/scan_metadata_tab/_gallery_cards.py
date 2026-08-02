"""Gallery card widget creation/styling + tag checkbox setup for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QLabel, QListWidgetItem, QVBoxLayout, QWidget

from ...components import ClickableLabel


class _GalleryCardsMixin:
    """Build/style thumbnail card widgets and populate the tag-checkbox list."""

    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        """Required by AbstractClassTwoGalleries base class."""
        return self._create_gallery_card(path, pixmap, is_selected)

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]) -> None:
        """Required by AbstractClassTwoGalleries base class."""
        if not widget:
            return
        inner_label = widget.findChild(QLabel)
        if inner_label:
            if pixmap and not pixmap.isNull():
                thumb_size = self.thumbnail_size
                if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
                    scaled = pixmap.scaled(
                        thumb_size,
                        thumb_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                    inner_label.setPixmap(scaled)
                else:
                    inner_label.setPixmap(pixmap)
            else:
                inner_label.setText("Error")
                inner_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")

    def _create_gallery_card(
        self,
        path: str,
        pixmap: Optional[QPixmap],
        is_selected: bool,
        is_in_db: bool = False,
    ) -> ClickableLabel:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)

        # Attach custom property to store DB status on the widget
        card_wrapper.setProperty("in_db", is_in_db)

        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        if pixmap and not pixmap.isNull():
            if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
                scaled = pixmap.scaled(
                    thumb_size,
                    thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                img_label.setPixmap(scaled)
            else:
                img_label.setPixmap(pixmap)
        else:
            # Modified to show Loading if passed as None, or Error if null/failed
            if pixmap is None:
                img_label.setText("Loading...")
                img_label.setStyleSheet("color: #b9bbbe; border: 1px dashed #4f545c;")
            else:
                img_label.setText("Error")
                img_label.setStyleSheet("color: #e74c3c; border: 1px solid #e74c3c;")

        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        self._update_card_style(img_label, is_selected, is_in_db)
        return card_wrapper

    def _update_card_style(self, img_label: QLabel, is_selected: bool, is_in_db: bool):
        """
        Updates card border style.
        Blue = Selected (Highest priority)
        Green = In Database (Medium priority)
        Grey = Default
        """
        if is_selected:
            # Blue Border
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        elif is_in_db:
            # Green Border
            img_label.setStyleSheet(
                "border: 3px solid #2ecc71; background-color: #36393f;"
            )
        else:
            # Default Grey Border
            # If text is loading/error, keep existing style, otherwise apply default
            if not img_label.pixmap() and (
                img_label.text() == "Loading..." or img_label.text() == "Error"
            ):
                pass
            else:
                img_label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: #36393f;"
                )

    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        db = self.db_tab_ref.db
        if not db:
            return []
        try:
            return db.get_all_tags_with_categories()
        except Exception:
            pass
        return []

    def _setup_tag_checkboxes(self):
        self.tags_list_widget.clear()

        tags_data = self._get_tags_from_db()

        for tag_data in tags_data:
            tag_name = tag_data["name"]

            item = QListWidgetItem(tag_name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, tag_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

            item.setForeground(QColor(tag_data.get("color") or "#95a5a6"))

            self.tags_list_widget.addItem(item)


__all__ = ["_GalleryCardsMixin"]
