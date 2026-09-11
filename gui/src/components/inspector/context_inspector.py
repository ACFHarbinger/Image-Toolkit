"""Universal Context Inspector Panel component (§2.38, #539)."""

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

from gui.src.modules.context import ModuleContext
from gui.src.modules.events import (
    EventHub,
    EventSubscription,
    FilterByTagIntent,
    InspectImageIntent,
    NavigateIntent,
    SelectionChangedFact,
    ToggleInspectorIntent,
)
from gui.src.theming.presets import DANBOORU_TAG_COLORS
from gui.src.theming.theme_api import qss


class ContextInspectorPanel(QWidget):
    """Universal collapsible right-hand inspector panel for metadata, EXIF, and tool parameters."""

    collapse_requested = Signal()
    tag_clicked = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        event_hub: Optional[EventHub] = None,
        context: Optional[ModuleContext] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("context_inspector")
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)
        self._context: Optional[ModuleContext] = context
        self._event_hub: Optional[EventHub] = None
        self._subscriptions: list[EventSubscription] = []
        self._build_ui()

        hub = event_hub or (context.event_hub if context is not None else None)
        if hub is not None:
            self.bind_event_hub(hub)

    def bind_event_hub(self, event_hub: EventHub) -> None:
        """Bind panel to EventHub for typed intent and fact subscriptions."""
        self._event_hub = event_hub
        for sub in self._subscriptions:
            sub.disconnect()
        self._subscriptions.clear()

        self._subscriptions.append(
            event_hub.subscribe(InspectImageIntent, self._on_inspect_intent, owner=self)
        )
        self._subscriptions.append(
            event_hub.subscribe(SelectionChangedFact, self._on_selection_fact, owner=self)
        )
        self._subscriptions.append(
            event_hub.subscribe(ToggleInspectorIntent, self._on_toggle_intent, owner=self)
        )

    def _on_inspect_intent(self, intent: InspectImageIntent) -> None:
        tags_dict: dict[str, list[str]] = {k: list(v) for k, v in intent.tags} if intent.tags else {}
        meta_dict: dict[str, str] = dict(intent.metadata) if intent.metadata else {}
        self.set_image_context(
            file_path=intent.file_path,
            resolution=intent.resolution,
            tags=tags_dict or None,
            metadata=meta_dict or None,
        )

    def _on_selection_fact(self, fact: SelectionChangedFact) -> None:
        target_path: Optional[str] = None
        if fact.active_path:
            target_path = fact.active_path
        elif fact.paths:
            target_path = fact.paths[0]

        if not target_path:
            self.clear_context()
            return

        tags_dict = {k: list(v) for k, v in fact.tags} if fact.tags else None
        meta_dict = dict(fact.metadata) if fact.metadata else None
        self.set_image_context(
            file_path=target_path,
            resolution=fact.resolution,
            tags=tags_dict,
            metadata=meta_dict,
        )

    def _on_toggle_intent(self, intent: ToggleInspectorIntent) -> None:
        if intent.visible is None:
            self.setVisible(self.isHidden())
        else:
            self.setVisible(intent.visible)

    def _on_close_clicked(self) -> None:
        self.collapse_requested.emit()
        self.hide()
        if self._event_hub is not None:
            self._event_hub.publish(ToggleInspectorIntent(origin="inspector", visible=False))

    def _on_tag_chip_clicked(self, tag: str) -> None:
        self.tag_clicked.emit(tag)
        if self._event_hub is not None:
            self._event_hub.publish(
                FilterByTagIntent(origin="inspector", module_id="library.search", tag_name=tag)
            )
            self._event_hub.publish(
                NavigateIntent(origin="inspector", module_id="library.search")
            )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # 1. Header with bilingual title and close button
        header_layout = QHBoxLayout()
        self.title_label = QLabel("◈ INSPECTOR // 情報")
        self.title_label.setStyleSheet(qss("context_inspector_title"))
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setToolTip("Collapse Inspector (Ctrl+I)")
        self.close_btn.setStyleSheet(qss("context_inspector_close_btn"))
        self.close_btn.clicked.connect(self._on_close_clicked)
        header_layout.addWidget(self.close_btn)
        root_layout.addLayout(header_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(qss("context_inspector_divider"))
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
        self.preview_label.setStyleSheet(qss("context_inspector_preview"))
        self.preview_label.setText("No Image Selected\n選択なし")
        self.content_layout.addWidget(self.preview_label)

        # Primary Properties (Filename, Resolution, Aspect Ratio, Format)
        self.info_group = QWidget()
        info_layout = QVBoxLayout(self.info_group)
        info_layout.setContentsMargins(4, 4, 4, 4)
        info_layout.setSpacing(4)

        self.filename_label = QLabel("--")
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet(qss("context_inspector_filename"))
        info_layout.addWidget(self.filename_label)

        # Badges row (Resolution pill, Format pill)
        badges_layout = QHBoxLayout()
        self.res_badge = QLabel("-- × --")
        self.res_badge.setStyleSheet(qss("context_inspector_res_badge"))
        badges_layout.addWidget(self.res_badge)

        self.fmt_badge = QLabel("--")
        self.fmt_badge.setStyleSheet(qss("context_inspector_fmt_badge"))
        badges_layout.addWidget(self.fmt_badge)
        badges_layout.addStretch()
        info_layout.addLayout(badges_layout)
        self.content_layout.addWidget(self.info_group)

        # 3. Tags Container
        self.tags_header = QLabel("🏷️ TAGS // タグ")
        self.tags_header.setStyleSheet(qss("context_inspector_section_header"))
        self.content_layout.addWidget(self.tags_header)

        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(3)
        self.content_layout.addWidget(self.tags_container)

        # 4. Metadata / EXIF Table
        self.exif_header = QLabel("📋 METADATA // メタデータ")
        self.exif_header.setStyleSheet(qss("context_inspector_section_header"))
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
                    QSize(max(self.width() - 20, 200), 180),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
                if resolution is None:
                    resolution = (pix.width(), pix.height())
            else:
                self.preview_label.setText("Preview Unavailable\nプレビュー不可")
        else:
            self.preview_label.setText("No Image Selected\n選択なし")

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
                cat_tag.setStyleSheet(
                    qss("context_inspector_tag_category", TAG_COLOR=style_token["text"])
                )
                row.addWidget(cat_tag)

                for t in tag_list[:6]:
                    chip = QPushButton(t)
                    chip.setStyleSheet(
                        qss(
                            "context_inspector_tag_chip",
                            TAG_BG=style_token["bg"],
                            TAG_TEXT=style_token["text"],
                            TAG_BORDER=style_token["border"],
                        )
                    )
                    chip.clicked.connect(lambda _=False, tag=t: self._on_tag_chip_clicked(tag))
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
