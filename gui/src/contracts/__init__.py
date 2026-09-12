"""gui/src/contracts/__init__.py
==============================
Dependency-free structural contracts shared across otherwise-unrelated GUI
subsystems (tabs, windows, session recovery, ...).

Deliberately outside ``gui/src/tabs`` and ``gui/src/windows``: both of those
packages eagerly import the full tab tree / MainWindow at package-init time,
so any of *their* consumers importing a contract module that lived inside
either package would trip a circular import. Modules here must only depend
on the standard library.
"""

from __future__ import annotations

from .tab_config import (
    CURRENT_TAB_CONFIG_VERSION,
    ConfigCollectible,
    ConfigDefaultable,
    ConfigSettable,
    TabConfigPayload,
    TabConfigurable,
    apply_tab_config,
)

__all__ = [
    "CURRENT_TAB_CONFIG_VERSION",
    "ConfigCollectible",
    "ConfigDefaultable",
    "ConfigSettable",
    "TabConfigPayload",
    "TabConfigurable",
    "apply_tab_config",
]
