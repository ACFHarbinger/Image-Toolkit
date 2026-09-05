"""
Global Activity & Log Panel Widget (§2.17 Options A & D).
=========================================================
Collapsible, filterable, and unified log panel connected to central LogHub.
"""

from __future__ import annotations

from typing import Optional, Set

from PySide6.QtCore import Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...constants import LEVEL_COLORS
from .log_hub import LogEntry, LogHub, get_log_hub


class GlobalLogPanel(QWidget):
    """
    Unified Activity History & Log Panel.

    Features
    --------
    - Connects to global ``LogHub`` singleton automatically.
    - Level filtering (ALL, DEBUG+, INFO+, WARNING+, ERROR+).
    - Source / subsystem filtering.
    - Real-time text search filtering.
    - Badge counter for warning and error counts.
    - Auto-scroll / Follow toggle.
    - Copy All and Export to File.
    """

    def __init__(
        self,
        hub: Optional[LogHub] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._hub = hub or get_log_hub()
        self._known_sources: Set[str] = set()

        self._setup_ui()
        self._connect_hub()
        self._refresh_all_entries()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        # Level filter
        self.level_combo = QComboBox(self)
        self.level_combo.addItems(
            ["All Levels", "DEBUG+", "INFO+", "WARNING+", "ERROR+", "SUCCESS"]
        )
        self.level_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.level_combo)

        # Source filter
        self.source_combo = QComboBox(self)
        self.source_combo.addItem("All Sources")
        self.source_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.source_combo)

        # Text search input
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Filter logs…")
        self.search_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.search_edit.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.search_edit)

        # Badge counter
        self.badge_label = QLabel(self)
        self.badge_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #a0a0a0; padding: 0 4px;")
        toolbar.addWidget(self.badge_label)

        # Follow checkbox
        self.follow_chk = QCheckBox("Follow", self)
        self.follow_chk.setChecked(True)
        self.follow_chk.setToolTip("Auto-scroll to newest log entry")
        toolbar.addWidget(self.follow_chk)

        # Actions
        self.copy_btn = QPushButton("Copy All", self)
        self.copy_btn.clicked.connect(self._copy_all)
        toolbar.addWidget(self.copy_btn)

        self.export_btn = QPushButton("Export…", self)
        self.export_btn.clicked.connect(self._export_to_file)
        toolbar.addWidget(self.export_btn)

        self.clear_btn = QPushButton("Clear", self)
        self.clear_btn.clicked.connect(self._clear_logs)
        toolbar.addWidget(self.clear_btn)

        root_layout.addLayout(toolbar)

        # Log output text area
        self.log_output = QPlainTextEdit(self)
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Monospace", 9))
        self.log_output.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #1a1b26;"
            "  color: #c0caf5;"
            "  border: 1px solid #292e42;"
            "  border-radius: 4px;"
            "}"
        )
        root_layout.addWidget(self.log_output, 1)

    def _connect_hub(self) -> None:
        self._hub.entry_added.connect(self._on_entry_added)
        self._hub.cleared.connect(self._on_hub_cleared)

    # ---- Entry handling -------------------------------------------------

    @Slot(object)
    def _on_entry_added(self, entry: LogEntry) -> None:
        if entry.source not in self._known_sources:
            self._known_sources.add(entry.source)
            self.source_combo.blockSignals(True)
            current_src = self.source_combo.currentText()
            self.source_combo.clear()
            self.source_combo.addItem("All Sources")
            for src in sorted(self._known_sources):
                self.source_combo.addItem(src)
            idx = self.source_combo.findText(current_src)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)
            self.source_combo.blockSignals(False)

        self._update_badge()

        if self._entry_matches_filters(entry):
            self._append_entry_to_view(entry)

    @Slot()
    def _on_hub_cleared(self) -> None:
        self.log_output.clear()
        self._update_badge()

    def _update_badge(self) -> None:
        errors = self._hub.error_count
        warnings = self._hub.warning_count
        if errors > 0 and warnings > 0:
            self.badge_label.setText(f"✕ {errors}  ⚠ {warnings}")
            self.badge_label.setStyleSheet("color: #f7768e; font-weight: bold;")
        elif errors > 0:
            self.badge_label.setText(f"✕ {errors}")
            self.badge_label.setStyleSheet("color: #f7768e; font-weight: bold;")
        elif warnings > 0:
            self.badge_label.setText(f"⚠ {warnings}")
            self.badge_label.setStyleSheet("color: #e0af68; font-weight: bold;")
        else:
            self.badge_label.setText("✓ Ready")
            self.badge_label.setStyleSheet("color: #9ece6a; font-weight: 500;")

    def _entry_matches_filters(self, entry: LogEntry) -> bool:
        # Level filter
        level_filter = self.level_combo.currentText()
        if level_filter == "DEBUG+" and entry.level_order < 10:
            return False
        if level_filter == "INFO+" and entry.level_order < 20:
            return False
        if level_filter == "WARNING+" and entry.level_order < 30:
            return False
        if level_filter == "ERROR+" and entry.level_order < 40:
            return False
        if level_filter == "SUCCESS" and entry.level != "SUCCESS":
            return False

        # Source filter
        source_filter = self.source_combo.currentText()
        if source_filter != "All Sources" and entry.source != source_filter:
            return False

        # Search query
        query = self.search_edit.text().strip().lower()
        if not query:
            return True
        return query in entry.message.lower() or query in entry.source.lower()


    def _append_entry_to_view(self, entry: LogEntry) -> None:
        colour = LEVEL_COLORS.get(entry.level.upper(), LEVEL_COLORS["INFO"])
        line = entry.formatted_line()

        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colour))
        cursor.insertText(line + "\n", fmt)

        if self.follow_chk.isChecked():
            self.log_output.setTextCursor(cursor)
            self.log_output.ensureCursorVisible()

    @Slot()
    def _on_filter_changed(self) -> None:
        self._refresh_all_entries()

    def _refresh_all_entries(self) -> None:
        self.log_output.clear()
        self._update_badge()
        for entry in self._hub.entries():
            if entry.source not in self._known_sources:
                self._known_sources.add(entry.source)
            if self._entry_matches_filters(entry):
                self._append_entry_to_view(entry)

    # ---- Toolbar actions ------------------------------------------------

    @Slot()
    def _copy_all(self) -> None:
        QGuiApplication.clipboard().setText(self.log_output.toPlainText())

    @Slot()
    def _export_to_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log", "", "Text files (*.txt);;All files (*.*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(self.log_output.toPlainText())
            except OSError as exc:
                self._hub.error(f"Failed to export log: {exc}", "logging")

    @Slot()
    def _clear_logs(self) -> None:
        self._hub.clear()


__all__ = ["GlobalLogPanel"]
