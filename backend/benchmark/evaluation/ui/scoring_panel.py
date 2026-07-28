"""The 0-4 structural-coherence scoring + free-text feedback UI, kept as
its own widget so ``main_window.py`` only has to wire signals, not build
this layout inline.

Evaluation scale (unchanged from the original CLI tool):
    4 = keepable — no visible structural defects
    3 = minor flaw — small artifact, still clearly usable
    2 = flawed but parses — visible defect, but anatomy/content still reads
    1 = mostly broken — hard to parse, major tearing/duplication
    0 = incoherent — torn anatomy, duplicated strips, or misordered content
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ..constants.user_interface import SCORE_SCALE_HINT


class ScoreRow(QWidget):
    scoreChanged = Signal(int)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        self._group = QButtonGroup(self)
        self._buttons = []
        for i in range(5):
            btn = QPushButton(str(i))
            btn.setCheckable(True)
            btn.setFixedWidth(32)
            self._group.addButton(btn, i)
            layout.addWidget(btn)
            self._buttons.append(btn)
        self._group.idClicked.connect(self.scoreChanged.emit)

    def set_score(self, score: Optional[int]) -> None:
        self._group.setExclusive(False)
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == score)
        self._group.setExclusive(True)

    def score(self) -> Optional[int]:
        checked = self._group.checkedId()
        return checked if checked >= 0 else None


class ScoringPanel(QWidget):
    evaluationChanged = Signal()
    notesChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QGroupBox("Structural Coherence Evaluation")
        layout = QVBoxLayout(box)
        layout.addWidget(QLabel(SCORE_SCALE_HINT))

        self.asp_row = ScoreRow("ASP:")
        self.simple_row = ScoreRow("Simple:")
        layout.addWidget(self.asp_row)
        layout.addWidget(self.simple_row)
        self.asp_row.scoreChanged.connect(lambda _: self.evaluationChanged.emit())
        self.simple_row.scoreChanged.connect(lambda _: self.evaluationChanged.emit())

        layout.addWidget(QLabel("Notes (difference summary, ASP vs Simple):"))
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.textChanged.connect(lambda: self.notesChanged.emit(self.notes_edit.toPlainText()))
        layout.addWidget(self.notes_edit)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

    def load_entry(self, asp: Optional[int], simple: Optional[int], notes: str) -> None:
        self.asp_row.set_score(asp)
        self.simple_row.set_score(simple)
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(notes)
        self.notes_edit.blockSignals(False)

    def asp_score(self) -> Optional[int]:
        return self.asp_row.score()

    def simple_score(self) -> Optional[int]:
        return self.simple_row.score()

    def notes(self) -> str:
        return self.notes_edit.toPlainText()
