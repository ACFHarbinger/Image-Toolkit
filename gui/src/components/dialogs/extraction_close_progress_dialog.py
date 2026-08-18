"""Mini Progress Dialog for Deferred Close during Active Background Tasks."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TaskCloseProgressDialog(QDialog):
    """
    Compact dialog displayed when closing the application while background tasks are still running
    (e.g., video extractions, media loader downloads, web crawlers, conversions).
    Allows user to monitor background completion, cancel remaining tasks, or confirm exit once finished.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        on_confirm: Optional[Callable[[], None]] = None,
        total: int = 0,
        completed: int = 0,
        title: str = "Tasks in Progress",
        header: str = "⚙️ Tasks in Progress",
        subtext: str = "Finishing remaining background tasks before exit...",
        cancel_text: str = "Cancel Tasks",
        item_unit: str = "tasks",
    ) -> None:
        super().__init__(parent)
        self.on_cancel_callback = on_cancel
        self.on_confirm_callback = on_confirm
        self.total_items = max(total, 1)
        self.completed_items = completed
        self.item_unit = item_unit
        self._is_finished = False

        self.setWindowTitle(title)
        self.setFixedSize(440, 190)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        self._setup_ui(header, subtext, cancel_text)
        self.update_progress(completed=self.completed_items, total=self.total_items)

    def _setup_ui(self, header: str, subtext: str, cancel_text: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        self.lbl_header = QLabel(header)
        self.lbl_header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.lbl_header)

        self.lbl_subtext = QLabel(subtext)
        self.lbl_subtext.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_subtext)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_items)
        self.progress_bar.setValue(self.completed_items)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #444; border-radius: 4px; text-align: center; height: 20px; }"
            "QProgressBar::chunk { background-color: #3498db; border-radius: 3px; }"
        )
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel(f"Processed {self.completed_items} of {self.total_items} {self.item_unit}")
        self.lbl_status.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_status)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(cancel_text)
        self.btn_cancel.setStyleSheet(
            "QPushButton { padding: 6px 14px; border-radius: 4px; border: 1px solid #777; }"
            "QPushButton:hover { background-color: #e74c3c; color: white; border-color: #c0392b; }"
        )
        self.btn_cancel.clicked.connect(self._handle_cancel)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setEnabled(False)
        self.btn_ok.setStyleSheet(
            "QPushButton { padding: 6px 20px; border-radius: 4px; background-color: #555; color: #aaa; }"
            "QPushButton:enabled { background-color: #3498db; color: white; font-weight: bold; }"
            "QPushButton:enabled:hover { background-color: #2980b9; }"
        )
        self.btn_ok.clicked.connect(self._handle_confirm)
        btn_layout.addWidget(self.btn_ok)

        layout.addLayout(btn_layout)

    def update_progress(self, completed: int, total: int, item_title: str = "") -> None:
        """Update progress counts and current item text."""
        self.completed_items = completed
        self.total_items = max(total, 1)
        self.progress_bar.setRange(0, self.total_items)
        self.progress_bar.setValue(self.completed_items)

        current_str = f" • Current: {item_title}" if item_title else ""
        self.lbl_status.setText(f"Processed {self.completed_items} of {self.total_items} {self.item_unit}{current_str}")

    def on_all_finished(self) -> None:
        """Called when all background tasks have completed."""
        self._is_finished = True
        self.progress_bar.setValue(self.total_items)
        self.lbl_header.setText("✅ Tasks Complete")
        self.lbl_subtext.setText("All background tasks finished successfully.")
        self.lbl_status.setText(f"All {self.completed_items} {self.item_unit} completed.")

        self.btn_cancel.setEnabled(False)
        self.btn_ok.setEnabled(True)
        self.btn_ok.setFocus()

    def _handle_cancel(self) -> None:
        callback = self.on_cancel_callback
        try:
            self.reject()
        except RuntimeError:
            pass
        if callback:
            callback()

    def _handle_confirm(self) -> None:
        callback = self.on_confirm_callback
        try:
            self.accept()
        except RuntimeError:
            pass
        if callback:
            callback()


# Aliases for backwards compatibility
ProcessCloseProgressDialog = TaskCloseProgressDialog
ExtractionCloseProgressDialog = TaskCloseProgressDialog

__all__ = [
    "TaskCloseProgressDialog",
    "ProcessCloseProgressDialog",
    "ExtractionCloseProgressDialog",
]
