"""Timestamp tags (named markers on the timeline), their UI row, and the
video-surface/slider right-click context menu.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QWidget,
)

from ..labels import _TagLabel


class _TagsLogicMixin:
    """Timestamp tags, their UI row, and the video-surface context menu."""

    def _build_tags_row(self) -> QHBoxLayout:
        """Builds "Row 5: Tags" for the Extraction Settings panel."""
        extract_tags_layout = QHBoxLayout()
        self.btn_add_tag = QPushButton("🏷️ Add Tag")
        self.btn_add_tag.clicked.connect(self.add_tag)
        self.btn_add_tag.setEnabled(False)

        # Scrollable container for tags
        self.tags_scroll = QScrollArea()
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tags_scroll.setMaximumHeight(45)
        self.tags_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.tags_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tags_scroll.setStyleSheet("background: transparent;")

        self.tags_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tags_scroll.setStyleSheet("background: transparent;")

        self.tags_container = QWidget()
        self.tags_container.setStyleSheet("background: transparent;")
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 5, 0, 5)
        self.tags_layout.setSpacing(8)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tags_scroll.setWidget(self.tags_container)

        self.btn_clear_tags = QPushButton("Clear Tags")
        self.btn_clear_tags.clicked.connect(self.clear_tags)
        self.btn_clear_tags.setEnabled(False)

        extract_tags_layout.addWidget(self.btn_add_tag)
        extract_tags_layout.addWidget(self.tags_scroll, 1)
        extract_tags_layout.addWidget(self.btn_clear_tags)
        extract_tags_layout.addStretch()

        return extract_tags_layout

    @Slot()
    def add_tag(self):
        current_ms = self.media_player.position()
        formatted = self._format_time(current_ms)

        proposed_name = f"Tag {len(self.tags_ms) + 1}"
        label, ok = QInputDialog.getText(
            self, "Add Tag", f"Enter label for tag at {formatted}:", text=proposed_name
        )
        if ok and label:
            self.tags_ms.append((current_ms, label))
            self.tags_ms.sort(key=lambda x: x[0])  # Keep sorted by time
            self._update_tags_ui()

    @Slot()
    def clear_tags(self):
        self.tags_ms.clear()
        self._update_tags_ui()

    def _update_tags_ui(self):
        # Clear existing tag labels
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        if not self.tags_ms:
            none_label = QLabel("Tags: None")
            none_label.setStyleSheet("color: #666; font-style: italic;")
            self.tags_layout.addWidget(none_label)
            self.btn_clear_tags.setEnabled(False)
        else:
            self.btn_clear_tags.setEnabled(True)
            self.tags_layout.addWidget(QLabel("Tags:"))
            for i, (ms, label_text) in enumerate(self.tags_ms):
                tag_display = f"{label_text} ({self._format_time(ms)})"
                label = _TagLabel(tag_display, ms, i)
                label.clicked.connect(self.jump_to_tag_time)
                label.double_clicked.connect(self.jump_to_tag_time)
                label.right_clicked.connect(self.show_tag_context_menu)
                self.tags_layout.addWidget(label)

        self.tags_layout.addStretch()

        has_tags = len(self.tags_ms) > 0
        self.btn_clear_tags.setEnabled(has_tags)

    @Slot(QPoint)
    def show_video_context_menu(self, pos: QPoint):
        """Show a context menu on the video player or slider with tag jumping and other options."""
        sender = self.sender()
        if not sender:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1e1f22; color: white; border: 1px solid #4f545c; }"
        )

        # 1. Jump to Tag Submenu
        if self.tags_ms:
            jump_menu = menu.addMenu("📍 Jump to Tag")
            jump_menu.setStyleSheet(
                "QMenu { background-color: #1e1f22; color: #FFC107; }"
            )
            for ms, label in self.tags_ms:
                action = QAction(f"{label} ({self._format_time(ms)})", self)
                action.triggered.connect(lambda _, m=ms: self.jump_to_tag_time(m))
                jump_menu.addAction(action)
            menu.addSeparator()

        # 2. Add Tag at current pos
        add_tag_action = QAction("🏷️ Add Tag Here", self)
        add_tag_action.triggered.connect(self.add_tag)
        menu.addAction(add_tag_action)

        # 3. Range actions
        set_start_action = QAction("🎞️ Set Range Start", self)
        set_start_action.triggered.connect(self.set_range_start)
        menu.addAction(set_start_action)

        set_end_action = QAction("🎞️ Set Range End", self)
        set_end_action.triggered.connect(self.set_range_end)
        menu.addAction(set_end_action)

        menu.addSeparator()

        # 4. Extraction triggers (convenience)
        if self.end_time_ms > self.start_time_ms:
            extract_vid_action = QAction("🎬 Extract Video Range", self)
            extract_vid_action.triggered.connect(self.extract_range_as_video)
            menu.addAction(extract_vid_action)

        # Show at global position
        global_pos = sender.mapToGlobal(pos) # pyrefly: ignore [missing-attribute]
        menu.exec(global_pos)

    @Slot(int)
    def jump_to_tag_time(self, ms: int):
        self.media_player.setPosition(ms)
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )

    @Slot(QPoint, int)
    def show_tag_context_menu(self, global_pos: QPoint, index: int):
        menu = QMenu(self)

        jump_action = QAction("📍 Jump to Tag", self)
        jump_action.triggered.connect(
            lambda: self.jump_to_tag_time(self.tags_ms[index][0])
        )
        menu.addAction(jump_action)
        menu.addSeparator()

        edit_action = QAction("Edit Tag", self)
        edit_action.triggered.connect(lambda: self.edit_tag(index))
        menu.addAction(edit_action)

        delete_action = QAction("Delete Tag", self)
        delete_action.triggered.connect(lambda: self.delete_tag(index))
        menu.addAction(delete_action)

        menu.exec(global_pos)

    def edit_tag(self, index: int):
        if 0 <= index < len(self.tags_ms):
            ms, label = self.tags_ms[index]
            formatted_time = self._format_time(ms)

            new_label, ok = QInputDialog.getText(
                self, "Edit Tag", f"Label for tag at {formatted_time}:", text=label
            )
            if ok and new_label:
                # Also allow editing time? Let's just do label for now as it's easier.
                # Actually, editing time would be good too.
                new_time_str, ok_time = QInputDialog.getText(
                    self,
                    "Edit Tag Time",
                    f"Time for '{new_label}':",
                    text=formatted_time,
                )
                if ok_time and new_time_str:
                    new_ms = self._parse_time(new_time_str)
                    if new_ms is not None:
                        self.tags_ms[index] = (new_ms, new_label)
                        self.tags_ms.sort(key=lambda x: x[0])
                        self._update_tags_ui()
                    else:
                        QMessageBox.warning(
                            self, "Invalid Format", "Invalid time format."
                        )

    def delete_tag(self, index: int):
        if 0 <= index < len(self.tags_ms):
            self.tags_ms.pop(index)
            self._update_tags_ui()

    def _validate_range(self):
        if self.end_time_ms > self.start_time_ms:
            total_duration_ms = self.end_time_ms - self.start_time_ms

            # Subtract cut durations
            cut_duration_ms = 0
            for c_start, c_end in self.cuts_ms:
                overlap_start = max(self.start_time_ms, c_start)
                overlap_end = min(self.end_time_ms, c_end)
                if overlap_end > overlap_start:
                    cut_duration_ms += overlap_end - overlap_start

            actual_duration_ms = max(0, total_duration_ms - cut_duration_ms)
            duration_str = self._format_time(actual_duration_ms)

            self.btn_extract_range.setEnabled(True)
            self.btn_extract_range.setText(f"Extract Range ({duration_str})")
            self.btn_extract_gif.setEnabled(True)
            self.btn_extract_gif.setText(f"GIF Extract as GIF ({duration_str})")
            self.btn_extract_video.setEnabled(True)
            self.btn_extract_video.setText(f"MP4 Extract as Video ({duration_str})")
        else:
            self.btn_extract_range.setEnabled(False)
            self.btn_extract_range.setText("🎞️ Extract Range")
            self.btn_extract_gif.setEnabled(False)
            self.btn_extract_gif.setText("GIF Extract as GIF")
            self.btn_extract_video.setEnabled(False)
            self.btn_extract_video.setText("MP4 Extract as Video")

    @Slot()
    def jump_to_range_start(self):
        self.media_player.setPosition(self.start_time_ms)
        # Pause to let user see exactly where they are? Or keep playing?
        # Usually pausing is better when jumping to specific frame.
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )

    @Slot()
    def jump_to_range_end(self):
        self.media_player.setPosition(self.end_time_ms)
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )


__all__ = ["_TagsLogicMixin"]
