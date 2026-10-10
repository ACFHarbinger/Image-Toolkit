"""
TagReviewDialog — new_features.md §4.4C (human-in-the-loop tagging queue).

Thin modal wrapper around ``TagReviewPanel``. Train inlines that panel
directly (#734) so review no longer blocks the rest of the tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import QDialog, QVBoxLayout

from .tag_review_panel import TagReviewPanel


class TagReviewDialog(QDialog):
    def __init__(
        self,
        image_paths: List[Path],
        trigger: Optional[str] = None,
        general_thresh: float = 0.35,
        review_thresh: float = 0.15,
        model_repo: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("WD-Tagger Review Queue")
        self.resize(760, 560)
        self._panel = TagReviewPanel(modal_chrome=True, parent=self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._panel)
        self._panel.review_saved.connect(lambda _n: self.accept())
        self._panel.review_cancelled.connect(self.reject)
        self._panel.start_review(
            image_paths,
            trigger=trigger,
            general_thresh=general_thresh,
            review_thresh=review_thresh,
            model_repo=model_repo,
        )

    def __getattr__(self, name):
        return getattr(self._panel, name)
