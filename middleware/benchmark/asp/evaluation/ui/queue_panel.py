"""The dataset queue sidebar: every test in the corpus, its rating state, and
free navigation to any of them.

The old dashboard offered only Back / Skip / Next over a filtered ``todo`` list,
so there was no way to jump to a specific test, no view of overall progress
beyond a text line, and — because Skip didn't record history — no way back to
something you'd passed. A visible, clickable list of all 97 with their state is
also what makes a partially-finished pass resumable in practice: you can see at
a glance what's left.

Search and a saved subset only change which names are listed. Next / Back
still walk the session order. Load subset applies a subset that was already
saved.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..constants.user_interface import COL_GOOD, COL_TEXT_DIM, COL_WARN, SCORE_COLORS
from ..other.case_library import selectable_subsets, upsert_subset
from ..other.session import EvaluationSession
from .theme import subtle

FILTER_ALL = "all"
FILTER_TODO = "todo"
FILTER_RATED = "rated"
FILTER_SKIPPED = "skipped"

_FILTERS = (
    (FILTER_ALL, "All tests"),
    (FILTER_TODO, "Not yet rated"),
    (FILTER_RATED, "Rated"),
    (FILTER_SKIPPED, "Skipped"),
)


def _message(exc: BaseException) -> str:
    return str(exc) or exc.__class__.__name__


def _subset_payload(row: object) -> dict | None:
    if not isinstance(row, dict):
        return None
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    kind = str(row.get("kind") or "")
    raw_ids = row.get("case_ids")
    if not isinstance(raw_ids, (list, tuple)):
        raw_ids = []
    return {
        "name": name,
        "kind": kind,
        "description": str(row.get("description") or ""),
        "case_ids": [str(case) for case in raw_ids],
        "label": f"{name} ({kind})" if kind else name,
    }


class QueuePanel(QWidget):
    datasetSelected = Signal(str)
    directoriesChanged = Signal()
    subsetChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session: EvaluationSession | None = None
        self._suppress = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._case_line = QLabel("Case: —")
        self._case_line.setProperty("role", "heading")
        layout.addWidget(self._case_line)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search cases")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._subset = QComboBox()
        self._subset.currentIndexChanged.connect(self._on_subset_changed)
        layout.addWidget(self._subset)
        self._subset_hint = subtle("")
        self._subset_hint.setWordWrap(True)
        layout.addWidget(self._subset_hint)

        self._save_subset_btn = QPushButton("Save subset…")
        self._save_subset_btn.clicked.connect(self._save_subset)
        self._load_subset_btn = QPushButton("Load subset…")
        self._load_subset_btn.setToolTip("Apply a saved subset to the queue")
        self._load_subset_btn.clicked.connect(self._load_subset)
        layout.addWidget(self._save_subset_btn)
        layout.addWidget(self._load_subset_btn)

        self._filter = QComboBox()
        for key, label in _FILTERS:
            self._filter.addItem(label, key)
        self._filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._filter)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self._list, stretch=1)

        self._empty = subtle("")
        self._empty.setWordWrap(True)
        layout.addWidget(self._empty)

        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)
        self._summary = QLabel("")
        self._summary.setProperty("role", "subtle")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        self._status = subtle("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._reload_subsets()

    def set_session(self, session: EvaluationSession) -> None:
        self._session = session
        self.refresh()

    def select_all_cases(self) -> None:
        """Drop the subset filter so a newly added directory is visible."""
        if self._subset.currentIndex() != 0:
            self._subset.setCurrentIndex(0)
            return
        self.refresh()

    def refresh(self) -> None:
        if self._session is None:
            self._case_line.setText("Case: —")
            self._empty.setText("")
            return
        mode = self._filter.currentData()
        query = self._search.text().strip().casefold()
        subset = self._subset_ids()
        self._suppress = True
        try:
            self._list.clear()
            for name in self._session.order:
                if not self._include_name(name, mode, query, subset):
                    continue
                rated = self._session.is_rated(name)
                skipped = self._session.is_skipped(name) and not rated
                self._list.addItem(self._make_item(name, rated, skipped))
            self._select_current()
        finally:
            self._suppress = False
        self._update_case_line()
        self._update_empty()
        self._update_subset_hint()
        self._update_progress()
        self.subsetChanged.emit()

    def _include_name(self, name: str, mode, query: str, subset: set[str] | None) -> bool:
        if subset is not None and name not in subset:
            return False
        if query and query not in name.casefold():
            return False
        assert self._session is not None
        rated = self._session.is_rated(name)
        skipped = self._session.is_skipped(name) and not rated
        if mode == FILTER_TODO and rated:
            return False
        if mode == FILTER_RATED and not rated:
            return False
        return not (mode == FILTER_SKIPPED and not skipped)

    def _subset_ids(self) -> set[str] | None:
        data = self._subset.currentData()
        if not isinstance(data, dict):
            return None
        return set(data.get("case_ids") or [])

    def shows_all_cases(self) -> bool:
        """True when compare should see every case in the run, not the queue filter."""
        if self._search.text().strip():
            return False
        if self._filter.currentData() != FILTER_ALL:
            return False
        return not isinstance(self._subset.currentData(), dict)

    def _make_item(self, name: str, rated: bool, skipped: bool) -> QListWidgetItem:
        assert self._session is not None
        entry = self._session.evaluations.get(name)
        if rated and entry is not None:
            marker = "●"
            detail = f"  ASP {entry.asp} / Sim {entry.simple}"
            color = SCORE_COLORS.get(entry.asp, COL_GOOD)
        elif skipped:
            marker, detail, color = "○", "  skipped", COL_WARN
        else:
            marker, detail, color = "·", "", COL_TEXT_DIM
        item = QListWidgetItem(f"{marker} {name}{detail}")
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setForeground(QColor(color))
        if entry is not None and entry.defects:
            item.setToolTip("defects: " + ", ".join(entry.defects))
        return item

    def _select_current(self) -> None:
        if self._session is None or self._session.current is None:
            return
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == self._session.current:
                self._list.setCurrentRow(row)
                self._list.scrollToItem(item)
                return

    def _on_current_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if self._suppress or current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        if name and self._session is not None and name != self._session.current:
            self.datasetSelected.emit(name)

    def _on_search_changed(self, _text: str) -> None:
        self.refresh()

    def _on_filter_changed(self, _index: int) -> None:
        self.refresh()

    def _on_subset_changed(self, _index: int) -> None:
        self.refresh()

    def _update_case_line(self) -> None:
        current = self._session.current if self._session is not None else None
        self._case_line.setText(f"Case: {current}" if current else "Case: —")

    def _update_empty(self) -> None:
        if self._session is None or self._list.count():
            self._empty.setText("")
            return
        self._empty.setText("No cases match.")

    def _update_subset_hint(self) -> None:
        data = self._subset.currentData()
        text = str(data.get("description") or "") if isinstance(data, dict) else ""
        self._subset_hint.setText(text)

    def _update_progress(self) -> None:
        assert self._session is not None
        progress = self._session.progress()
        self._progress.setMaximum(max(1, progress.total))
        self._progress.setValue(progress.rated)
        self._progress.setFormat(f"{progress.rated}/{progress.total} rated (%p%)")
        remaining = progress.total - progress.rated
        parts = [f"{remaining} left"]
        if progress.skipped:
            parts.append(f"{progress.skipped} skipped")
        if progress.position:
            parts.append(f"at #{progress.position}")
        self._summary.setText(" · ".join(parts))

    def active_names(self) -> list[str]:
        names: list[str] = []
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            name = item.data(Qt.ItemDataRole.UserRole)
            if name:
                names.append(str(name))
        return names

    def visible_names(self) -> list[str]:
        return self.active_names()

    def _reload_subsets(self, select: str | None = None) -> None:
        if select is None:
            current = self._subset.currentData()
            if isinstance(current, dict):
                select = str(current.get("name") or "")
        self._subset.blockSignals(True)
        self._subset.clear()
        self._subset.addItem("All cases", None)
        try:
            rows = selectable_subsets()
        except Exception as exc:
            self._status.setText(_message(exc))
            rows = []
        for row in rows:
            info = _subset_payload(row)
            if info is None:
                continue
            self._subset.addItem(info["label"], info)
        self._subset.setCurrentIndex(self._subset_index(select))
        self._subset.blockSignals(False)
        self.refresh()

    def _subset_index(self, name: str | None) -> int:
        if not name:
            return 0
        for index in range(self._subset.count()):
            data = self._subset.itemData(index)
            if isinstance(data, dict) and data.get("name") == name:
                return index
        return 0

    def _save_subset(self) -> None:
        if self._session is None:
            self._status.setText("No cases loaded.")
            return
        prompted = self._prompt_subset()
        if prompted is None:
            return
        name, description = prompted
        if not name:
            self._status.setText("Enter a subset name.")
            return
        try:
            saved = upsert_subset(name, self.active_names(), description=description)
        except Exception as exc:
            self._status.setText(_message(exc))
            return
        chosen = saved.get("name", name) if isinstance(saved, dict) else name
        self._status.setText(f"Saved subset {chosen}.")
        self._reload_subsets(select=str(chosen))

    def _select_subset_named(self, name: str) -> bool:
        """Select a saved subset by name. False when that name is not in the menu."""
        key = name.strip()
        if not key:
            return False
        for index in range(self._subset.count()):
            data = self._subset.itemData(index)
            if isinstance(data, dict) and data.get("name") == key:
                self._subset.setCurrentIndex(index)
                return True
        return False

    def _load_subset(self) -> None:
        self._reload_subsets()
        choices: list[tuple[str, dict]] = []
        for index in range(self._subset.count()):
            data = self._subset.itemData(index)
            if isinstance(data, dict) and data.get("name"):
                choices.append((str(data["name"]), data))
        if not choices:
            self._status.setText("No saved subsets.")
            return
        chosen = self._prompt_load_subset(choices)
        if chosen is None:
            return
        if not self._select_subset_named(chosen):
            self._status.setText(f"No subset named {chosen}.")
            return
        self._status.setText(f"Loaded subset {chosen}.")

    def _prompt_load_subset(self, choices: list[tuple[str, dict]]) -> str | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Load subset")
        form = QVBoxLayout(dialog)
        listing = QListWidget()
        for name, data in choices:
            count = len(data.get("case_ids") or [])
            label = str(data.get("label") or name)
            item = QListWidgetItem(f"{label}  ·  {count} cases")
            description = str(data.get("description") or "")
            if description:
                item.setToolTip(description)
            item.setData(Qt.ItemDataRole.UserRole, name)
            listing.addItem(item)
        listing.setCurrentRow(0)
        listing.itemDoubleClicked.connect(lambda _item: dialog.accept())
        form.addWidget(listing)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        current = listing.currentItem()
        if current is None:
            return None
        name = current.data(Qt.ItemDataRole.UserRole)
        return str(name) if name else None

    def _prompt_subset(self) -> tuple[str, str] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Save subset")
        form = QVBoxLayout(dialog)
        form.addWidget(QLabel("Name"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Required")
        form.addWidget(name_edit)
        form.addWidget(QLabel("Description"))
        desc_edit = QLineEdit()
        form.addWidget(desc_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        form.addWidget(buttons)

        def _try_accept() -> None:
            if name_edit.text().strip():
                dialog.accept()

        buttons.accepted.connect(_try_accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return name_edit.text().strip(), desc_edit.text().strip()
