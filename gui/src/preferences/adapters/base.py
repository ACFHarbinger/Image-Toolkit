"""gui/src/preferences/adapters/base.py
=======================================
Abstract base adapter for preference storage backends (§1.1, #525).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PreferenceAdapter(ABC):
    """Abstract interface for a storage backend attached to a PreferenceScope."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored preference value."""
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store a preference value."""
        raise NotImplementedError

    @abstractmethod
    def contains(self, key: str) -> bool:
        """Check if a preference key exists in the store."""
        raise NotImplementedError

    @abstractmethod
    def remove(self, key: str) -> None:
        """Remove a preference key from the store."""
        raise NotImplementedError

    @abstractmethod
    def all_keys(self) -> list[str]:
        """Return all keys held in this adapter."""
        raise NotImplementedError

    def clear(self) -> None:
        """Clear all keys in this adapter."""
        for key in list(self.all_keys()):
            self.remove(key)


__all__ = ["PreferenceAdapter"]
