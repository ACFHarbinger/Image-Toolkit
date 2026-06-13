"""§2.20A — QSplitter state persistence via QSettings."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QSplitter


def persist_splitter(splitter: QSplitter, key: str) -> None:
    """Restore saved splitter state and auto-save on every move.

    *key* should be globally unique (e.g. ``"StitchFeedbackTab/main_splitter"``).
    Call once, immediately after ``setSizes(defaults)`` so the restore overrides
    the defaults when previous state exists.
    """
    settings = QSettings("ImageToolkit", "ImageToolkit")
    saved = settings.value(f"splitters/{key}")
    if saved:
        splitter.restoreState(saved)

    def _save(_pos: int = 0, _idx: int = 0) -> None:
        QSettings("ImageToolkit", "ImageToolkit").setValue(
            f"splitters/{key}", splitter.saveState()
        )

    splitter.splitterMoved.connect(_save)
