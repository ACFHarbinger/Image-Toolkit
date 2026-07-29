"""Right-click context menu (clear/swap wallpaper queue/graph).

Extracted from ``monitor_drop_view.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMenu


class _ContextMenuMixin:
    """Builds and dispatches the per-monitor right-click context menu."""

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        clear_action = menu.addAction("Clear All Images (Current and Queue)")
        clear_action.triggered.connect(
            lambda: self.clear_requested_id.emit(self.monitor_id)
        )

        menu.addSeparator()
        if self.other_monitors:
            swap_menu = menu.addMenu("Swap Wallpaper Queue with...")
            for target_id, target_name in self.other_monitors:
                action = swap_menu.addAction(f"{target_name} (ID: {target_id})")
                action.triggered.connect(
                    lambda _, tid=target_id: self.swap_requested_id.emit(
                        self.monitor_id, tid
                    )
                )

            swap_graph_menu = menu.addMenu("Swap Wallpaper Graph with...")
            for target_id, target_name in self.other_monitors:
                action = swap_graph_menu.addAction(f"{target_name} (ID: {target_id})")
                action.triggered.connect(
                    lambda _, tid=target_id: self.swap_graph_requested_id.emit(
                        self.monitor_id, tid
                    )
                )
        else:
            # Fallback for 2-monitor legacy case or if targets not populated
            swap_action = menu.addAction("Swap Wallpaper Queue (Monitor switch)")
            swap_action.triggered.connect(
                lambda: self.swap_requested_id.emit(self.monitor_id, "")
            )
            swap_graph_action = menu.addAction("Swap Wallpaper Graph (Monitor switch)")
            swap_graph_action.triggered.connect(
                lambda: self.swap_graph_requested_id.emit(self.monitor_id, "")
            )

        # Let parent (WallpaperTab) add dynamic items (like "Set Active Wallpaper")
        self.context_menu_requested.emit(self.monitor_id, menu)

        menu.exec(event.globalPos())


__all__ = ["_ContextMenuMixin"]
