"""gui/src/preferences/adapters/qsettings_adapter.py
================================================
QSettings adapter for device-scoped preferences (§1.1, #525).
"""

from __future__ import annotations

from typing import Any

from .base import PreferenceAdapter


class QSettingsPreferenceAdapter(PreferenceAdapter):
    """Adapter backed by PySide6 QSettings for persistent device-scoped state."""

    ORG: str = "ImageToolkit"
    APP: str = "ImageToolkit"

    def __init__(self, org: str | None = None, app: str | None = None) -> None:
        self.org = org or self.ORG
        self.app = app or self.APP

    def _q(self):
        from PySide6.QtCore import QSettings
        return QSettings(self.org, self.app)

    def get(self, key: str, default: Any = None) -> Any:
        q = self._q()
        if not q.contains(key):
            return default
        val = q.value(key, default)
        return val

    def set(self, key: str, value: Any) -> None:
        self._q().setValue(key, value)

    def contains(self, key: str) -> bool:
        return self._q().contains(key)

    def remove(self, key: str) -> None:
        self._q().remove(key)

    def all_keys(self) -> list[str]:
        return list(self._q().allKeys())


__all__ = ["QSettingsPreferenceAdapter"]
