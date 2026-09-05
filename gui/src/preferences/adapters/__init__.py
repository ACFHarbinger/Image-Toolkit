"""gui/src/preferences/adapters/__init__.py
=========================================
Storage backend adapters for PreferenceStore (§1.1, #525).
"""

from __future__ import annotations

from .base import PreferenceAdapter
from .memory_adapter import MemoryPreferenceAdapter
from .qsettings_adapter import QSettingsPreferenceAdapter
from .vault_adapter import VaultPreferenceAdapter

__all__ = [
    "MemoryPreferenceAdapter",
    "PreferenceAdapter",
    "QSettingsPreferenceAdapter",
    "VaultPreferenceAdapter",
]
