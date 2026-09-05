"""gui/src/preferences/adapters/memory_adapter.py
=============================================
In-memory dictionary adapter for ephemeral session preferences (§1.1, #525).
"""

from __future__ import annotations

import copy
from threading import RLock
from typing import Any

from .base import PreferenceAdapter


class MemoryPreferenceAdapter(PreferenceAdapter):
    """Thread-safe in-memory adapter for ephemeral session state or testing."""

    def __init__(self, initial_data: dict[str, Any] | None = None) -> None:
        self._lock = RLock()
        self._data: dict[str, Any] = copy.deepcopy(initial_data) if initial_data else {}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            val = self._data.get(key, default)
            return copy.deepcopy(val)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = copy.deepcopy(value)

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def remove(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def all_keys(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of all current data in this adapter."""
        with self._lock:
            return copy.deepcopy(self._data)


__all__ = ["MemoryPreferenceAdapter"]
