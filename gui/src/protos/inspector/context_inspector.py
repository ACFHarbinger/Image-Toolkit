"""Universal Context Inspector Panel component (§2.38)."""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.presets import DANBOORU_TAG_COLORS


class ContextInspectorPanel(QWidget):
    """Universal collapsible right-hand inspector panel for metadata, EXIF, and tool parameters."""

    collapse_requested = Signal()
    tag_clicked = Signal(str)  # tag_name clicked for quick filter/search

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("context_inspector")
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # 1. Header with bilingual title and close button
        header_layout = QHBoxLayout()
        self.title_label = QLabel("◈ INSPECTOR // 情報")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 10.5pt; color: #00f0ff;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setToolTip("Collapse Inspector (Ctrl+I)")
        self.close_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 11pt; color: #888; } QPushButton:hover { color: #fff; background: rgba(255,255,255,0.1); border-radius: 12px; }")
        self.close_btn.clicked.connect(self.collapse_requested)
        header_layout.addWidget(self.close_btn)
        root_layout.addLayout(header_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.1); max-height: 1px;")
        root_layout.addWidget(divider)

        # 2. Scrollable Body
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        # Image Preview Thumbnail
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedHeight(180)
        self.preview_label.setStyleSheet("background: rgba(0, 0, 0, 0.25); border-radius: 6px;")
        self.preview_label.setText("No Image Selected\n選択なし")
        self.content_layout.addWidget(self.preview_label)

        # Primary Properties (Filename, Resolution, Aspect Ratio, Format)
        self.info_group = QWidget()
        info_layout = QVBoxLayout(self.info_group)
        info_layout.setContentsMargins(4, 4, 4, 4)
        info_layout.setSpacing(4)

        self.filename_label = QLabel("--")
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet("font-weight: 600; font-size: 9.5pt;")
        info_layout.addWidget(self.filename_label)

        # Badges row (Resolution pill, Format pill)
        badges_layout = QHBoxLayout()
        self.res_badge = QLabel("-- × --")
        self.res_badge.setStyleSheet("background: rgba(0, 240, 255, 0.12); color: #00f0ff; border: 1px solid rgba(0, 240, 255, 0.25); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        badges_layout.addWidget(self.res_badge)

        self.fmt_badge = QLabel("--")
        self.fmt_badge.setStyleSheet("background: rgba(255, 255, 255, 0.08); color: #cccccc; border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        badges_layout.addWidget(self.fmt_badge)
        badges_layout.addStretch()
        info_layout.addLayout(badges_layout)
        self.content_layout.addWidget(self.info_group)

        # 3. Tags Container
        self.tags_header = QLabel("🏷️ TAGS // タグ")
        self.tags_header.setStyleSheet("font-weight: bold; font-size: 8.5pt; color: #aaaaaa;")
        self.content_layout.addWidget(self.tags_header)

        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(3)
        self.content_layout.addWidget(self.tags_container)

        # 4. Metadata / EXIF Table
        self.exif_header = QLabel("📋 METADATA // メタデータ")
        self.exif_header.setStyleSheet("font-weight: bold; font-size: 8.5pt; color: #aaaaaa;")
        self.content_layout.addWidget(self.exif_header)

        self.exif_table = QTableWidget(0, 2)
        self.exif_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.exif_table.horizontalHeader().setStretchLastSection(True)
        self.exif_table.verticalHeader().setVisible(False)
        self.exif_table.setMaximumHeight(160)
        self.content_layout.addWidget(self.exif_table)

        self.content_layout.addStretch()
        self.scroll.setWidget(self.content_container)
        root_layout.addWidget(self.scroll, 1)

    def set_image_context(
        self,
        file_path: str,
        resolution: Optional[tuple[int, int]] = None,
        tags: Optional[dict[str, list[str]]] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> None:
        """Populate inspector with image details."""
        self.filename_label.setText(os.path.basename(file_path))

        if os.path.exists(file_path):
            pix = QPixmap(file_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    QSize(self.width() - 20, 180),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
                if resolution is None:
                    resolution = (pix.width(), pix.height())

        if resolution:
            w, h = resolution
            self.res_badge.setText(f"{w} × {h}")
        else:
            self.res_badge.setText("-- × --")

        ext = os.path.splitext(file_path)[1].upper().lstrip(".") or "IMG"
        self.fmt_badge.setText(ext)

        # Clear and populate tags
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if tags:
            for category, tag_list in tags.items():
                style_token = DANBOORU_TAG_COLORS.get(category.lower(), DANBOORU_TAG_COLORS["general"])
                row = QHBoxLayout()
                cat_tag = QLabel(f"{category}:")
                cat_tag.setStyleSheet(f"color: {style_token['text']}; font-weight: 600; font-size: 8pt;")
                row.addWidget(cat_tag)

                for t in tag_list[:6]:
                    chip = QPushButton(t)
                    chip.setStyleSheet(f"background: {style_token['bg']}; color: {style_token['text']}; border: 1px solid {style_token['border']}; border-radius: 3px; padding: 1px 5px; font-size: 7.5pt;")
                    chip.clicked.connect(lambda _=False, tag=t: self.tag_clicked.emit(tag))
                    row.addWidget(chip)
                row.addStretch()
                self.tags_layout.addLayout(row)

        # Clear and populate metadata
        self.exif_table.setRowCount(0)
        if metadata:
            self.exif_table.setRowCount(len(metadata))
            for i, (k, v) in enumerate(metadata.items()):
                self.exif_table.setItem(i, 0, QTableWidgetItem(str(k)))
                self.exif_table.setItem(i, 1, QTableWidgetItem(str(v)))

    def clear_context(self) -> None:
        """Reset inspector to empty state."""
        self.filename_label.setText("--")
        self.res_badge.setText("-- × --")
        self.fmt_badge.setText("--")
        self.preview_label.setText("No Image Selected\n選択なし")
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.exif_table.setRowCount(0)


__all__ = ["ContextInspectorPanel"]
