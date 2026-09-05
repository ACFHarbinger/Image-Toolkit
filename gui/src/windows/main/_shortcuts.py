"""Keyboard shortcut discovery overlay (Ctrl+/ or F1) (§2.25A).

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from ...components.dialogs.shortcut_discovery_dialog import ShortcutDiscoveryDialog


class _ShortcutOverlayMixin:
    """Displays every registered keyboard shortcut in a searchable overlay dialog."""

    def _open_shortcut_overlay(self) -> None:
        dlg = ShortcutDiscoveryDialog(self)
        dlg.exec()


__all__ = ["_ShortcutOverlayMixin"]
