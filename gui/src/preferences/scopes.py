"""gui/src/preferences/scopes.py
==============================
Preference key ownership scopes (§1.1, #525).

Defines the canonical ownership domain for application settings:
- DEVICE: Local machine / hardware / OS configuration (persisted to QSettings).
  Never synced across accounts or cloud vaults. Preserved in guest sessions.
- ACCOUNT: User profile configuration (persisted to encrypted vault).
  Synced with user profile. Volatile / discarded in guest sessions.
- SESSION: Ephemeral runtime state for the active application instance.
  Discarded on application exit.
"""

from __future__ import annotations

from enum import Enum


class PreferenceScope(str, Enum):
    """Canonical ownership scope for a preference key."""

    DEVICE = "device"
    ACCOUNT = "account"
    SESSION = "session"


__all__ = ["PreferenceScope"]
