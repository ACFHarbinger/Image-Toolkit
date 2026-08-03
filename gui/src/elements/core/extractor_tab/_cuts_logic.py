"""Range/cuts state (start/end trim, mid-clip cut segments) and their UI row.

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
    QWidget,
)

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol

# NOTE: ``_CutLabel`` is imported lazily (inside the method that uses it)
# rather than at module load time. ``gui.src.tabs.core`` eagerly re-exports
# every tab (including this one via a thin shim), so a top-level import
# here would create a circular import when this module is loaded first.


class _CutsLogicMixin:
    """Extraction range and mid-clip cut segments, and their UI row."""

    def _build_cuts_row(self: "VideoExtractorSubTabHostProtocol") -> QHBoxLayout:
        """Builds "Row 3: Cuts" for the Extraction Settings panel."""
        extract_cuts_layout = QHBoxLayout()
        self.btn_set_cut_start = QPushButton("Set Cut Start [00:00]")
        self.btn_set_cut_start.clicked.connect(self.set_cut_start)
        self.btn_set_cut_start.setEnabled(False)

        self.btn_set_cut_end = QPushButton("Set Cut End [00:00]")
        self.btn_set_cut_end.clicked.connect(self.set_cut_end)
        self.btn_set_cut_end.setEnabled(False)

        self.btn_add_cut = QPushButton("Add Cut")
        self.btn_add_cut.clicked.connect(self.add_cut)
        self.btn_add_cut.setEnabled(False)

        # Scrollable container for individual cuts
        self.cuts_scroll = QScrollArea()
        self.cuts_scroll.setWidgetResizable(True)
        self.cuts_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.cuts_scroll.setMaximumHeight(45)
        self.cuts_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.cuts_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.cuts_scroll.setStyleSheet("background: transparent;")

        self.cuts_container = QWidget()
        self.cuts_container.setStyleSheet("background: transparent;")
        self.cuts_layout = QHBoxLayout(self.cuts_container)
        self.cuts_layout.setContentsMargins(0, 5, 0, 5)
        self.cuts_layout.setSpacing(8)
        self.cuts_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.cuts_scroll.setWidget(self.cuts_container)

        self.btn_clear_cuts = QPushButton("Clear Cuts")
        self.btn_clear_cuts.clicked.connect(self.clear_cuts)
        self.btn_clear_cuts.setEnabled(False)

        extract_cuts_layout.addWidget(self.btn_set_cut_start)
        extract_cuts_layout.addWidget(self.btn_set_cut_end)
        extract_cuts_layout.addWidget(self.btn_add_cut)
        extract_cuts_layout.addWidget(self.cuts_scroll, 1)  # Give it stretch
        extract_cuts_layout.addWidget(self.btn_clear_cuts)
        extract_cuts_layout.addStretch()

        return extract_cuts_layout

    def _update_range_labels(self: "VideoExtractorSubTabHostProtocol"):
        """Updates the text and enabled state of range-related buttons."""
        start_str = self._format_time(self.start_time_ms)
        end_str = self._format_time(self.end_time_ms)

        self.btn_set_start.setText(f"Start: {start_str}")
        self.btn_set_end.setText(f"End: {end_str}")

        self.btn_snapshot.setText(f"📸 Snapshot at {start_str}")
        self.btn_snapshot.setEnabled(True)
        self.btn_jump_start.setEnabled(True)
        self.btn_jump_end.setEnabled(True)

        self._validate_range()

    @Slot()
    def set_range_start(self: "VideoExtractorSubTabHostProtocol"):
        self.start_time_ms = self.media_player.position()
        self._update_range_labels()

    @Slot()
    def set_range_end(self: "VideoExtractorSubTabHostProtocol"):
        self.end_time_ms = self.media_player.position()
        self._update_range_labels()

    @Slot()
    def set_cut_start(self: "VideoExtractorSubTabHostProtocol"):
        self.cut_start_ms = self.media_player.position()
        time_str = self._format_time(self.cut_start_ms)
        self.btn_set_cut_start.setText(f"Cut Start: {time_str}")
        self._validate_cut_range()

    @Slot()
    def set_cut_end(self: "VideoExtractorSubTabHostProtocol"):
        self.cut_end_ms = self.media_player.position()
        time_str = self._format_time(self.cut_end_ms)
        self.btn_set_cut_end.setText(f"Cut End: {time_str}")
        self._validate_cut_range()

    def _validate_cut_range(self: "VideoExtractorSubTabHostProtocol"):
        if self.cut_end_ms > self.cut_start_ms:
            self.btn_add_cut.setEnabled(True)
        else:
            self.btn_add_cut.setEnabled(False)

    @Slot()
    def add_cut(self: "VideoExtractorSubTabHostProtocol"):
        if self.cut_end_ms > self.cut_start_ms:
            self.cuts_ms.append((self.cut_start_ms, self.cut_end_ms))
            self.cut_start_ms = 0
            self.cut_end_ms = 0
            self.btn_set_cut_start.setText("Set Cut Start [00:00]")
            self.btn_set_cut_end.setText("Set Cut End [00:00]")
            self.btn_add_cut.setEnabled(False)
            self._update_cuts_label()

    @Slot()
    def clear_cuts(self: "VideoExtractorSubTabHostProtocol"):
        self.cuts_ms.clear()
        self._update_cuts_label()

    def _update_cuts_label(self: "VideoExtractorSubTabHostProtocol"):
        # Clear existing cut labels
        while self.cuts_layout.count():
            item = self.cuts_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.cuts_ms:
            none_label = QLabel("Cuts: None")
            none_label.setStyleSheet("color: #666; font-style: italic;")
            self.cuts_layout.addWidget(none_label)
            self.btn_clear_cuts.setEnabled(False)
        else:
            self.btn_clear_cuts.setEnabled(True)
            self.cuts_layout.addWidget(QLabel("Cuts:"))
            for i, (s, e) in enumerate(self.cuts_ms):
                cut_text = f"[{self._format_time(s)}-{self._format_time(e)}]"
                from gui.src.tabs.core.labels import _CutLabel

                label = _CutLabel(cut_text, i)
                label.right_clicked.connect(self.show_cut_context_menu)
                self.cuts_layout.addWidget(label)

        self.cuts_layout.addStretch()
        self._validate_range()

    @Slot(QPoint, int)
    def show_cut_context_menu(self: "VideoExtractorSubTabHostProtocol", global_pos: QPoint, index: int):
        menu = QMenu(cast(QWidget, self))

        edit_start_action = QAction("Edit Start Timestamp", cast(QWidget, self))
        edit_start_action.triggered.connect(
            lambda: self.edit_cut_timestamp(index, is_start=True)
        )
        menu.addAction(edit_start_action)

        edit_end_action = QAction("Edit End Timestamp", cast(QWidget, self))
        edit_end_action.triggered.connect(
            lambda: self.edit_cut_timestamp(index, is_start=False)
        )
        menu.addAction(edit_end_action)

        menu.addSeparator()

        jump_start_action = QAction("Jump to Start", cast(QWidget, self))
        jump_start_action.triggered.connect(
            lambda: self.jump_to_cut_time(index, is_start=True)
        )
        menu.addAction(jump_start_action)

        jump_end_action = QAction("Jump to End", cast(QWidget, self))
        jump_end_action.triggered.connect(
            lambda: self.jump_to_cut_time(index, is_start=False)
        )
        menu.addAction(jump_end_action)

        menu.addSeparator()

        delete_action = QAction("Delete Cut", cast(QWidget, self))
        delete_action.triggered.connect(lambda: self.delete_cut(index))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def edit_cut_timestamp(self: "VideoExtractorSubTabHostProtocol", index: int, is_start: bool):
        if 0 <= index < len(self.cuts_ms):
            current_start, current_end = self.cuts_ms[index]
            current_val = current_start if is_start else current_end
            formatted = self._format_time(current_val)

            label_text = (
                "New Start Time (MM:SS:mmm):"
                if is_start
                else "New End Time (MM:SS:mmm):"
            )
            new_time_str, ok = QInputDialog.getText(
                cast(QWidget, self), "Edit Cut", label_text, text=formatted
            )

            if ok and new_time_str:
                new_ms = self._parse_time(new_time_str)
                if new_ms is not None:
                    if is_start:
                        if new_ms < current_end:
                            self.cuts_ms[index] = (new_ms, current_end)
                        else:
                            QMessageBox.warning(
                                cast(QWidget, self),
                                "Invalid Time",
                                "Start time must be before end time.",
                            )
                    else:
                        if new_ms > current_start:
                            self.cuts_ms[index] = (current_start, new_ms)
                        else:
                            QMessageBox.warning(
                                cast(QWidget, self),
                                "Invalid Time",
                                "End time must be after start time.",
                            )
                    self._update_cuts_label()
                else:
                    QMessageBox.warning(
                        cast(QWidget, self),
                        "Invalid Format",
                        "Please use MM:SS:mmm, MM:SS, or SS formats.",
                    )

    def jump_to_cut_time(self: "VideoExtractorSubTabHostProtocol", index: int, is_start: bool):
        if 0 <= index < len(self.cuts_ms):
            ms = self.cuts_ms[index][0] if is_start else self.cuts_ms[index][1]
            self.media_player.setPosition(ms)

    def delete_cut(self: "VideoExtractorSubTabHostProtocol", index: int):
        if 0 <= index < len(self.cuts_ms):
            self.cuts_ms.pop(index)
            self._update_cuts_label()


__all__ = ["_CutsLogicMixin"]
