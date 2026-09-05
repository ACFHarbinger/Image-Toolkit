"""gui/src/preferences/__init__.py
================================
PreferenceStore contract package (§1.1, #525).

Provides typed key ownership (DEVICE, ACCOUNT, SESSION) and single-source
read/write routing for application settings.
"""

from __future__ import annotations

from .adapters import (
    MemoryPreferenceAdapter,
    PreferenceAdapter,
    QSettingsPreferenceAdapter,
    VaultPreferenceAdapter,
)
from .definitions import (
    ALL_KNOWN_DEFINITIONS,
    PreferenceDefinition,
    PrefKeys,
)
from .scopes import PreferenceScope
from .store import ChangeCallback, PreferenceStore

__all__ = [
    "ALL_KNOWN_DEFINITIONS",
    "ChangeCallback",
    "MemoryPreferenceAdapter",
    "PrefKeys",
    "PreferenceAdapter",
    "PreferenceDefinition",
    "PreferenceScope",
    "PreferenceStore",
    "QSettingsPreferenceAdapter",
    "VaultPreferenceAdapter",
]
