"""Saved ASP runs: notes, an explicit output snapshot, and a case delta table."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..constants import user_interface as ui_constants
from ..other.run_library import (
    annotate_run,
    compare_cases,
    filter_by_tags,
    list_runs,
    snapshot_outputs,
)
from .theme import heading, subtle

_COMPARE_KEYS = ("case", "asp", "asp_prev", "delta_asp", "prev_run")


def _split_tags(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _run_cells(run: dict) -> list[str]:
    tags = run.get("tags") or []
    tag_text = ", ".join(str(tag) for tag in tags) if isinstance(tags, list) else str(tags)
    cases = run.get("cases") or []
    count = len(cases) if isinstance(cases, (list, tuple)) else 0
    return [
        str(run.get("run_id") or ""),
        str(run.get("label") or ""),
        tag_text,
        str(run.get("description") or ""),
        str(count),
    ]


def _format_value(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _delta_color(widget: QWidget, value: object) -> QColor | None:
    """Green above +0.01 ASP, red below -0.01. Missing constants fall back to highlight."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number > 0.01:
        tone = "COL_GOOD"
    elif number < -0.01:
        tone = "COL_BAD"
    else:
        return None
    raw = getattr(ui_constants, tone, None)
    if raw:
        return QColor(str(raw))
    return widget.palette().highlight().color()


def _message(exc: BaseException) -> str:
    return str(exc) or exc.__class__.__name__


class RunLibraryPanel(QWidget):
    """List archived runs and compare two of them. Nothing is written until asked."""

    openCase = Signal(str)

    def __init__(self, parent=None, root: Path | None = None):
        super().__init__(parent)
        self._root = root
        self._listed: list[dict] = []
        self._base_dir: str | None = None
        self._cases: list[str] = []
        self._active_cases: list[str] | None = None
        self._source_ready = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(heading("Runs"))

        self._tag_filter = QLineEdit()
        self._tag_filter.setPlaceholderText("Filter by tag")
        self._tag_filter.textChanged.connect(self._on_tag_filter)
        layout.addWidget(self._tag_filter)

        self._runs = self._make_table(["id", "label", "tags", "description", "cases"])
        self._runs.itemSelectionChanged.connect(self._load_selected_note)
        header = self._runs.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._runs, stretch=2)
        self._runs_empty = subtle("No saved runs.")
        layout.addWidget(self._runs_empty)

        self._description = QPlainTextEdit()
        self._description.setPlaceholderText("Description")
        self._description.setFixedHeight(56)
        self._tags = QLineEdit()
        self._tags.setPlaceholderText("Tags, comma-separated")
        self._label = QLineEdit()
        self._label.setPlaceholderText("Snapshot label")
        layout.addWidget(self._description)
        layout.addWidget(self._tags)
        layout.addWidget(self._label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        note = QPushButton("Save note")
        note.clicked.connect(self._save_note)
        self._save_btn = QPushButton("Save current outputs…")
        self._save_btn.setProperty("role", "primary")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_outputs)
        buttons.addWidget(note)
        buttons.addWidget(self._save_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        layout.addWidget(heading("Compare"))
        picks = QHBoxLayout()
        picks.setContentsMargins(0, 0, 0, 0)
        picks.addWidget(QLabel("Run"))
        self._run_combo = QComboBox()
        picks.addWidget(self._run_combo, stretch=1)
        picks.addWidget(QLabel("Against"))
        self._against_combo = QComboBox()
        picks.addWidget(self._against_combo, stretch=1)
        compare = QPushButton("Compare")
        compare.clicked.connect(self._compare)
        picks.addWidget(compare)
        layout.addLayout(picks)

        self._compare = self._make_table(list(_COMPARE_KEYS))
        self._compare.itemDoubleClicked.connect(self._on_compare_double_clicked)
        layout.addWidget(self._compare, stretch=2)
        self._compare_empty = subtle("No comparison yet.")
        layout.addWidget(self._compare_empty)

        self._status = subtle("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self.reload()

    def set_source(self, base_dir: str, cases: list[str]) -> None:
        """Remember the outputs a later snapshot may copy. Does not write."""
        self._base_dir = base_dir
        self._cases = list(cases)
        self._source_ready = True
        self._save_btn.setEnabled(True)

    def set_active_cases(self, cases: list[str] | None) -> None:
        """None compares every case in the run. A list limits compare_cases."""
        self._active_cases = None if cases is None else [str(case) for case in cases]

    def reload(self) -> None:
        try:
            runs = filter_by_tags(list_runs(root=self._root), _split_tags(self._tag_filter.text()))
        except Exception as exc:
            self._status.setText(_message(exc))
            return
        self._listed = list(runs)
        self._fill_runs(self._listed)
        self._fill_combos(self._listed)
        self._runs_empty.setVisible(not self._listed)
        if self._tag_filter.text().strip() and not self._listed:
            self._runs_empty.setText("No runs match these tags.")
        else:
            self._runs_empty.setText("No saved runs.")

    def _on_tag_filter(self, _text: str) -> None:
        self.reload()

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setSortingEnabled(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        return table

    def _fill_runs(self, runs: list[dict]) -> None:
        selected = self._selected_run_id()
        table = self._runs
        table.blockSignals(True)
        table.setRowCount(len(runs))
        restore_row = -1
        for row, run in enumerate(runs):
            run_id = str(run.get("run_id") or "")
            if selected and run_id == selected:
                restore_row = row
            for col, text in enumerate(_run_cells(run)):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, run_id)
                table.setItem(row, col, item)
        if restore_row >= 0:
            table.setCurrentCell(restore_row, 0)
        else:
            table.setCurrentItem(None)
        table.blockSignals(False)

    def _fill_combos(self, runs: list[dict]) -> None:
        current = self._run_combo.currentData()
        against = self._against_combo.currentData()
        self._run_combo.blockSignals(True)
        self._against_combo.blockSignals(True)
        self._run_combo.clear()
        self._against_combo.clear()
        self._against_combo.addItem("Previous", None)
        for run in runs:
            run_id = str(run.get("run_id") or "")
            label = str(run.get("label") or "")
            text = f"{label} ({run_id})" if label else run_id
            self._run_combo.addItem(text, run_id)
            self._against_combo.addItem(text, run_id)
        self._select_data(self._run_combo, current)
        self._select_data(self._against_combo, against)
        self._run_combo.blockSignals(False)
        self._against_combo.blockSignals(False)

    @staticmethod
    def _select_data(combo: QComboBox, data) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == data:
                combo.setCurrentIndex(index)
                return
        if combo.count():
            combo.setCurrentIndex(0)

    def _selected_run_id(self) -> str | None:
        row = self._runs.currentRow()
        item = self._runs.item(row, 0) if row >= 0 else None
        if item is None:
            return None
        run_id = item.data(Qt.ItemDataRole.UserRole)
        return str(run_id) if run_id else None

    def _selected_run(self) -> dict | None:
        run_id = self._selected_run_id()
        if not run_id:
            return None
        for run in self._listed:
            if str(run.get("run_id") or "") == run_id:
                return run
        return None

    def _load_selected_note(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        self._description.setPlainText(str(run.get("description") or ""))
        tags = run.get("tags") or []
        if isinstance(tags, list):
            self._tags.setText(", ".join(str(tag) for tag in tags))
        else:
            self._tags.setText(str(tags))

    def _save_note(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            self._status.setText("No run selected.")
            return
        try:
            annotate_run(
                run_id,
                description=self._description.toPlainText().strip(),
                tags=_split_tags(self._tags.text()),
                root=self._root,
            )
        except Exception as exc:
            self._status.setText(_message(exc))
            return
        self.reload()
        self._status.setText(f"Noted {run_id}.")

    def _save_outputs(self) -> None:
        if not self._source_ready or self._base_dir is None:
            self._status.setText("No current outputs to save.")
            return
        answer = QMessageBox.question(
            self,
            "Save current outputs",
            "Keep a snapshot of the current outputs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            snapshot_outputs(
                self._base_dir,
                list(self._cases),
                description=self._description.toPlainText().strip(),
                tags=_split_tags(self._tags.text()),
                label=self._label.text().strip() or None,
                root=self._root,
            )
        except Exception as exc:
            self._status.setText(_message(exc))
            return
        self.reload()
        self._status.setText("Saved current outputs.")

    def _compare(self) -> None:
        run_id = self._run_combo.currentData()
        if not run_id:
            self._status.setText("No run selected.")
            return
        try:
            rows = compare_cases(
                str(run_id),
                self._against_combo.currentData(),
                cases=self._active_cases,
                root=self._root,
            )
        except Exception as exc:
            self._status.setText(_message(exc))
            self._fill_compare([])
            return
        self._fill_compare(rows)
        if rows:
            self._status.setText(f"{len(rows)} cases.")
        else:
            self._status.setText("No cases to compare.")

    def _fill_compare(self, rows: list[dict]) -> None:
        table = self._compare
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            case = str(row.get("case") or "")
            for col, key in enumerate(_COMPARE_KEYS):
                value = row.get(key)
                item = QTableWidgetItem(_format_value(value))
                if key == "case":
                    item.setData(Qt.ItemDataRole.UserRole, case)
                if key == "delta_asp":
                    color = _delta_color(self, value)
                    if color is not None:
                        item.setForeground(color)
                table.setItem(row_index, col, item)
        self._compare_empty.setVisible(not rows)
        if not rows:
            self._compare_empty.setText("No cases to compare.")

    def _on_compare_double_clicked(self, item: QTableWidgetItem) -> None:
        source = self._compare.item(item.row(), 0)
        if source is None:
            return
        name = source.data(Qt.ItemDataRole.UserRole) or source.text()
        if name:
            self.openCase.emit(str(name))
