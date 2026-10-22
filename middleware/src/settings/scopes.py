"""Setting ownership scopes (W0-16 / #880).

Mirrors ``gui/src/preferences/scopes.py`` so both GUIs agree on the
canonical ownership domain. The Qt shell keeps its own enum; the drift
test in ``middleware/test/settings`` fails CI if the two diverge.
"""

from __future__ import annotations

from enum import Enum


class SettingScope(str, Enum):
    """Canonical ownership scope for a setting key."""

    DEVICE = "device"
    ACCOUNT = "account"
    SESSION = "session"


ALL_SCOPES = frozenset(SettingScope)


__all__ = ["ALL_SCOPES", "SettingScope"]
