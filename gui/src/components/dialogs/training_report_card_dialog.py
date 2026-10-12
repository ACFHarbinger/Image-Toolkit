"""#746: the training report card — the three-question summary shown after
a successful training run (Qwen's proposal §4.2). Non-modal by design: it
is a summary panel, not a blocking question."""
from __future__ import annotations

from backend.src.core.training_report import (
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_INFO,
    STATUS_WARN,
    ReportCard,
)
from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

_STATUS_COLORS = {
    STATUS_GOOD: "#3a9d6e",
    STATUS_WARN: "#c9a227",
    STATUS_BAD: "#c0392b",
    STATUS_INFO: "#8a8a8a",
}
_STATUS_DOTS = {STATUS_GOOD: "●", STATUS_WARN: "●", STATUS_BAD: "●", STATUS_INFO: "○"}


class TrainingReportCardDialog(QDialog):
    """Renders a ReportCard: one row per verdict plus the suggestion banner."""

    experiment_requested = Signal(str)
    start_tournament_requested = Signal(str)
    # #743: fired by "View Rank Chart" when the run has adapter artifacts.
    rank_chart_requested = Signal()

    def __init__(
        self,
        card: ReportCard,
        *,
        run_dir: str = "",
        rank_chart_available: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Training Report Card")
        self.setModal(False)
        self._run_dir = run_dir

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        title = QLabel("Training Report Card")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        for verdict in card.verdicts:
            root.addLayout(self._row(verdict.question, verdict))

        line = QLabel("—" * 24)
        root.addWidget(line)
        suggestion = QLabel("What to try next")
        suggestion.setStyleSheet("font-weight: bold;")
        root.addWidget(suggestion)
        root.addLayout(self._row("", card.suggestion))

        buttons = QHBoxLayout()
        buttons.addStretch()
        if rank_chart_available:
            rank_btn = QPushButton("View Rank Chart")
            rank_btn.setToolTip("Effective rank vs chosen rank across checkpoints (#743)")
            rank_btn.clicked.connect(self.rank_chart_requested.emit)
            buttons.addWidget(rank_btn)
        if run_dir:
            experiment_btn = QPushButton("Experiment from this run…")
            experiment_btn.clicked.connect(lambda: self.experiment_requested.emit(run_dir))
            buttons.addWidget(experiment_btn)
            if self._tournament_inputs_available(run_dir):
                tournament_btn = QPushButton("Start Tournament…")
                tournament_btn.setToolTip(
                    "Blind pairwise comparison of this run's checkpoint sample grids"
                )
                tournament_btn.clicked.connect(self._start_tournament)
                buttons.addWidget(tournament_btn)
            open_btn = QPushButton("Open Run Folder")
            open_btn.setToolTip(run_dir)
            open_btn.clicked.connect(self._open_run_folder)
            buttons.addWidget(open_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setDefault(True)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def _row(self, question: str, verdict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        dot = QLabel(_STATUS_DOTS.get(verdict.status, "○"))
        color = _STATUS_COLORS.get(verdict.status, _STATUS_COLORS[STATUS_INFO])
        dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        dot.setToolTip(verdict.status)
        row.addWidget(dot)

        text = QVBoxLayout()
        text.setSpacing(0)
        if question:
            heading = QLabel(f"<b>{question}</b> {verdict.headline}")
            heading.setWordWrap(True)
            text.addWidget(heading)
        else:
            heading = QLabel(verdict.headline)
            heading.setWordWrap(True)
            text.addWidget(heading)
        if verdict.detail:
            detail = QLabel(verdict.detail)
            detail.setWordWrap(True)
            detail.setStyleSheet("color: #8a8a8a;")
            text.addWidget(detail)
        row.addLayout(text, stretch=1)
        return row

    def _open_run_folder(self) -> None:
        if self._run_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._run_dir))

    def _start_tournament(self) -> None:
        if self._run_dir:
            self.start_tournament_requested.emit(self._run_dir)

    @staticmethod
    def _tournament_inputs_available(run_dir: str) -> bool:
        """Cheap filesystem probe so the button never offers a tournament
        the run cannot deliver (needs ≥2 checkpoints and ≥2 sample grids)."""
        from backend.src.core import checkpoint_tournament as ct

        try:
            return (
                len(ct.discover_sample_grids(run_dir)) >= 2
                and len(ct.discover_checkpoints(run_dir)) >= 2
            )
        except OSError:
            return False
