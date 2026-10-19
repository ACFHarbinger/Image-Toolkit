"""Per-class session values in the app's QSettings (``session/{class_name}/{key}``).

Lives below ``gui.src.windows`` so widgets and base classes can persist UI state
without importing the settings window (which reaches the tabs; import-linter
forbids ``gui.src.classes`` → ``gui.src.tabs``). ``AppSettings.session`` delegates here.
"""

from __future__ import annotations

from typing import Any

ORG = "ImageToolkit"
APP = "ImageToolkit"


def _q():
    from PySide6.QtCore import QSettings

    return QSettings(ORG, APP)


def session_value(class_name: str, key: str, default: Any = None) -> Any:
    return _q().value(f"session/{class_name}/{key}", default)


def set_session_value(class_name: str, key: str, value: Any) -> None:
    _q().setValue(f"session/{class_name}/{key}", value)
