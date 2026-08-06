"""Preference Review Dialog -- DPO preference capture (roadmap §6.3, issue #197).

Side-by-side A/B candidate comparison with a single-click preference vote,
built as a stub ahead of the LocalDPO/LoRA alignment pipeline (§4.1/§4.2)
itself: per this section's own "build early" rationale, preference data
collection should start as soon as any generative colorization mode ships
(the Manga Colorization Tab's three working modes -- Scribble, Screentone,
Reference/Optimal-Transport -- already qualify), rather than being
retrofitted once the training loop exists. Every vote is appended to a
local JSON-lines log via `backend/src/manga/preference_log.py`, immediately
readable by a future training script.

New feature, not code motion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
from manga.features.preference_log import log_preference
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..elements.canvas_editor import rgb_array_to_qpixmap

# Candidate previews are scaled to this width for side-by-side display;
# the underlying full-resolution array is never touched, only the QPixmap
# shown in the dialog.
_PREVIEW_WIDTH = 360


class MangaPreferenceDialog(QDialog):
    """Show two candidate colorizations side by side and record which one
    the user prefers (or a tie/skip) to the local preference log."""

    preference_recorded = Signal(str)  # "a" | "b" | "tie"

    def __init__(
        self,
        candidate_a: np.ndarray,
        candidate_b: np.ndarray,
        source_a: str = "Candidate A",
        source_b: str = "Candidate B",
        metadata: Optional[dict[str, Any]] = None,
        log_path: Optional[Path] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Manga Colorization -- Preference Review")
        self._source_a = source_a
        self._source_b = source_b
        self._metadata = metadata
        self._log_path = log_path
        self._winner: Optional[str] = None

        self._build_ui(candidate_a, candidate_b)

    def _build_ui(self, candidate_a: np.ndarray, candidate_b: np.ndarray) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Which colorization do you prefer?"))

        images_row = QHBoxLayout()
        images_row.addLayout(self._candidate_column(candidate_a, self._source_a))
        images_row.addLayout(self._candidate_column(candidate_b, self._source_b))
        layout.addLayout(images_row)

        buttons_row = QHBoxLayout()
        self.btn_prefer_a = QPushButton("← Prefer A")
        self.btn_prefer_a.clicked.connect(lambda: self._vote("a"))
        buttons_row.addWidget(self.btn_prefer_a)

        self.btn_tie = QPushButton("Tie / Skip")
        self.btn_tie.clicked.connect(lambda: self._vote("tie"))
        buttons_row.addWidget(self.btn_tie)

        self.btn_prefer_b = QPushButton("Prefer B →")
        self.btn_prefer_b.clicked.connect(lambda: self._vote("b"))
        buttons_row.addWidget(self.btn_prefer_b)

        layout.addLayout(buttons_row)

    def _candidate_column(self, candidate: np.ndarray, source_label: str) -> QVBoxLayout:
        col = QVBoxLayout()
        title = QLabel(source_label)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(title)

        image_label = QLabel()
        pixmap = rgb_array_to_qpixmap(candidate)
        if pixmap.width() > _PREVIEW_WIDTH:
            pixmap = pixmap.scaledToWidth(_PREVIEW_WIDTH, Qt.TransformationMode.SmoothTransformation)
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(image_label)
        return col

    def _vote(self, winner: str) -> None:
        self._winner = winner
        log_preference(self._source_a, self._source_b, winner, metadata=self._metadata, log_path=self._log_path)
        self.preference_recorded.emit(winner)
        self.accept()

    def winner(self) -> Optional[str]:
        """The recorded vote (``"a"``/``"b"``/``"tie"``), or ``None`` if the
        dialog was closed without voting."""
        return self._winner


__all__ = ["MangaPreferenceDialog"]
