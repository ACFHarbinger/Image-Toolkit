"""Settings conflict detection (W0-16 / #880).

Two sources of conflict, both reported with the evidence needed to
resolve them:

1. **Concurrent writers.** ``SettingsService.set_if_unchanged`` is a
   compare-and-swap: it fails with :class:`ConflictError` when the stored
   value changed since the caller last read it, so a lost update cannot
   happen silently.
2. **Legacy migration overlap.** A key present in both the legacy store
   and the new store with different values is a :class:`SettingsConflict`
   record; :class:`ConflictPolicy` decides whether migration aborts
   (default), keeps the legacy value, or keeps the new one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConflictError(Exception):
    """A concurrent writer changed the value between read and write."""

    def __init__(self, key: str, expected: Any, actual: Any) -> None:
        self.key = key
        self.expected = expected
        self.actual = actual
        super().__init__(f"conflict on {key!r}: expected {expected!r}, found {actual!r}")


class ConflictPolicy(str, Enum):
    """How migration resolves a key claimed by both stores."""

    ABORT = "abort"  # fail the migration, write nothing (default)
    PREFER_LEGACY = "prefer_legacy"  # legacy value wins
    PREFER_NEW = "prefer_new"  # new-store value wins


@dataclass(frozen=True)
class SettingsConflict:
    """One key claimed by both the legacy and the new store."""

    key: str
    legacy_value: Any
    new_value: Any

    def resolved_value(self, policy: ConflictPolicy) -> Any:
        return self.legacy_value if policy is ConflictPolicy.PREFER_LEGACY else self.new_value


class MigrationConflictError(Exception):
    """Migration aborted: the listed keys conflict (policy ABORT)."""

    def __init__(self, conflicts: list[SettingsConflict]) -> None:
        self.conflicts = conflicts
        keys = ", ".join(repr(c.key) for c in conflicts)
        super().__init__(f"legacy settings conflict on: {keys} (rerun with ConflictPolicy.PREFER_LEGACY or PREFER_NEW)")


__all__ = [
    "ConflictError",
    "ConflictPolicy",
    "MigrationConflictError",
    "SettingsConflict",
]
