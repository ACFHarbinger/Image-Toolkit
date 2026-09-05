"""gui/src/modules/runtime_shell_flag.py
====================================
Feature flag for the experimental rail/ribbon runtime shell (#536).
"""

from __future__ import annotations

from gui.src.preferences import PreferenceStore, PrefKeys


def runtime_shell_enabled(preference_store: PreferenceStore | None = None) -> bool:
    """Return whether this account enables the experimental runtime shell."""
    store = preference_store or PreferenceStore.instance()
    return bool(store.get(PrefKeys.EXPERIMENTAL_RUNTIME_SHELL))


__all__ = [
    "runtime_shell_enabled",
]
