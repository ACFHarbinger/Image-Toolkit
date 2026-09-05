"""§2.20A — QSplitter state persistence via QSettings."""
from __future__ import annotations

from PySide6.QtWidgets import QSplitter

from .app_settings import AppSettings


def restore_splitter_state(splitter: QSplitter, key: str) -> bool:
    """Restore saved splitter state from QSettings under splitters/{key}."""
    saved = AppSettings.splitter(key)
    if saved:
        return splitter.restoreState(saved)
    return False


def save_splitter_state(splitter: QSplitter, key: str) -> None:
    """Save current splitter state to QSettings under splitters/{key}."""
    AppSettings.set_splitter(key, splitter.saveState())  # pyrefly: ignore [bad-argument-type]


def persist_splitter(splitter: QSplitter, key: str) -> None:
    """Restore saved splitter state and auto-save on every move.

    *key* should be globally unique (e.g. ``"StitchFeedbackTab/main_splitter"``).
    Call once, immediately after ``setSizes(defaults)`` so the restore overrides
    the defaults when previous state exists.
    """
    restore_splitter_state(splitter, key)

    def _save(_pos: int = 0, _idx: int = 0) -> None:
        save_splitter_state(splitter, key)

    splitter.splitterMoved.connect(_save)


__all__ = ["persist_splitter", "restore_splitter_state", "save_splitter_state"]
