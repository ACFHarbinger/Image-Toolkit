"""§2.20A — QSplitter state persistence via QSettings."""
from __future__ import annotations

from PySide6.QtWidgets import QSplitter

from gui.src.utils.settings import AppSettings


def persist_splitter(splitter: QSplitter, key: str) -> None:
    """Restore saved splitter state and auto-save on every move.

    *key* should be globally unique (e.g. ``"StitchFeedbackTab/main_splitter"``).
    Call once, immediately after ``setSizes(defaults)`` so the restore overrides
    the defaults when previous state exists.
    """
    saved = AppSettings.splitter(key)
    if saved:
        splitter.restoreState(saved)

    def _save(_pos: int = 0, _idx: int = 0) -> None:
        AppSettings.set_splitter(key, splitter.saveState())

    splitter.splitterMoved.connect(_save)
