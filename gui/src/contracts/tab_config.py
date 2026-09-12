"""Cross-tab TabConfig contract (ui-arch-35 / R1.2).

Tabs that persist a named configuration snapshot -- Ctrl+S
(``windows/main/_save_tab_config.py``), Meta+S
(``windows/main/_load_tab_config.py``), workflow templates
(``windows/main/_workflow_templates.py``), session recovery
(``windows/main/_session_recovery.py``, ``_startup_prefs.py``), and
Settings' "Tab Default Configuration Management" section
(``windows/settings/_tab_config_editing.py``) -- implement up to three
loosely related methods with no shared type: ``get_default_config()``,
``collect()``, ``set_config(config)``. Each call site re-derived its own
``hasattr(tab, ...) and callable(...)`` guard. This module makes the
contract explicit so call sites can ``isinstance()``-check it instead, and
centralizes the one real variation across implementers: some
``set_config`` accept an optional ``quiet`` keyword (suppresses status
messages/dialogs during startup and session recovery) and some don't.

Lives in ``gui.src.contracts`` rather than ``gui.src.tabs`` so that
importing it doesn't pull in the full tab tree (see
``gui/src/contracts/__init__.py``).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

CURRENT_TAB_CONFIG_VERSION = 1


@runtime_checkable
class ConfigCollectible(Protocol):
    """A tab that can snapshot its current settings as a plain dict."""

    def collect(self) -> dict[str, Any]: ...


@runtime_checkable
class ConfigSettable(Protocol):
    """A tab that can have a previously-saved config applied back to it."""

    def set_config(self, config: dict[str, Any]) -> None: ...


@runtime_checkable
class ConfigDefaultable(Protocol):
    """A tab that can report its own built-in default config."""

    def get_default_config(self) -> dict[str, Any]: ...


@runtime_checkable
class TabConfigurable(ConfigCollectible, ConfigSettable, Protocol):
    """Full save+load contract: ``collect()`` to snapshot, ``set_config()`` to restore."""


@dataclass
class TabConfigPayload:
    """Versioned envelope for a config blob persisted to the vault.

    ``version`` lets a future change to the storage shape (e.g. splitting
    ``values`` into typed sections) detect and migrate old snapshots
    instead of silently misreading them. Tabs still exchange plain
    ``dict`` via ``collect()``/``set_config()`` -- this is the storage
    envelope around that dict, not the tab-facing shape.
    """

    values: dict[str, Any] = field(default_factory=dict)
    version: int = CURRENT_TAB_CONFIG_VERSION


def apply_tab_config(tab: ConfigSettable, config: dict[str, Any], *, quiet: bool = False) -> None:
    """Calls ``tab.set_config(config)``, passing ``quiet=True`` only if that
    implementer's ``set_config`` accepts it.

    Centralizes the ``inspect.signature`` duck-typing that
    ``_session_recovery.py`` and ``_startup_prefs.py`` each used to
    duplicate.
    """
    if quiet and "quiet" in inspect.signature(tab.set_config).parameters:
        tab.set_config(config, quiet=True)  # type: ignore[call-arg]
    else:
        tab.set_config(config)


__all__ = [
    "CURRENT_TAB_CONFIG_VERSION",
    "ConfigCollectible",
    "ConfigDefaultable",
    "ConfigSettable",
    "TabConfigPayload",
    "TabConfigurable",
    "apply_tab_config",
]
