"""Monitor selection sync (self + linked peers) and the "Set Wallpaper" button state.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QVBoxLayout, QWidget

from ......components import DraggableMonitorContainer, MonitorDropView
from ......styles import STYLE_START_ACTION

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _MonitorSelectionMixin:
    """Monitor selection (with peer sync) and the shared "Set Wallpaper" button."""

    def set_system_display_ref(self: "WallpaperCommonBaseHostProtocol", system_display):
        """Set the system display reference.

        Args:
            system_display: The system display reference.
        """
        self._system_display_ref = system_display

    def create_monitor_layout_section(self: "WallpaperCommonBaseHostProtocol", title: str) -> QGroupBox:
        layout_group = QGroupBox(title)

        self.monitor_layout_container = DraggableMonitorContainer()

        gb_layout = QVBoxLayout(layout_group)
        gb_layout.addWidget(self.monitor_layout_container)
        return layout_group

    def _select_monitor(self: "WallpaperCommonBaseHostProtocol", monitor_id: Optional[str]):
        new_id = None if self._current_monitor_id == monitor_id else monitor_id

        self._current_monitor_id = new_id

        # Sync selection styling locally
        for mid, widget in self.monitor_widgets.items():
            if isinstance(widget, MonitorDropView):
                widget.set_selected(mid == new_id)
                widget.repaint()

        # Sync peer selection styling
        if not getattr(self, "_syncing_selection", False):
            self._syncing_selection = True
            try:
                for peer in getattr(self, "linked_tabs", []):
                    peer._select_monitor_peer(new_id)
            finally:
                self._syncing_selection = False

        # Flush only posted paint events, NOT the full event queue: a full
        # QApplication.processEvents() here reentrantly pumps timers and
        # queued signals. During session recovery this fires the scan-dir
        # restore timer (armed 250ms earlier by set_config) from inside
        # _select_monitor_peer's call stack, starting scanner QThreads
        # mid-recovery -- the documented deleteOrphaned/heap-corruption
        # crash shape (see Addendum 21 of
        # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md, and the
        # user crash whose caller trace reached populate_scan_image_gallery
        # via exactly this line). sendPostedEvents(None, Paint) still
        # delivers the repaint the original processEvents() was there for
        # (monitor highlight delay, commit 06375b44) without that hazard.
        QApplication.sendPostedEvents(None, QEvent.Type.Paint)

        self._on_monitor_selected(new_id)

    def _select_monitor_peer(self: "WallpaperCommonBaseHostProtocol", monitor_id: Optional[str]):
        self._current_monitor_id = monitor_id
        for mid, widget in self.monitor_widgets.items():
            if isinstance(widget, MonitorDropView):
                widget.set_selected(mid == monitor_id)
                widget.repaint()

        # Same narrowing as _select_monitor above: paint-only flush, never a
        # full processEvents() (which reentrantly fires timers/queued signals
        # mid-call -- the crash trace in the user report reached
        # _do_pending_scan_dir_restore via this line during session recovery).
        QApplication.sendPostedEvents(None, QEvent.Type.Paint)

        self._on_monitor_selected(monitor_id)

    def _on_monitor_selected(self: "WallpaperCommonBaseHostProtocol", monitor_id: Optional[str]):
        pass

    def update_card_style(self: "WallpaperCommonBaseHostProtocol", widget: QWidget, is_selected: bool):
        super().update_card_style(widget, is_selected)  # type: ignore[safe-super]

        label = widget.findChild(QLabel)
        if not label:
            return

        path = getattr(label, "file_path", getattr(label, "path", ""))
        if not path:
            return

        in_queue = False
        for p in self.monitor_image_paths.values():
            if path == p:
                in_queue = True
                break

        if not in_queue:
            for queue in self.monitor_slideshow_queues.values():
                if path in queue:
                    in_queue = True
                    break

        if in_queue:
            if is_selected:
                label.setStyleSheet("border: 3px solid #2ecc71; background-color: rgba(88, 101, 242, 0.4);")
            else:
                label.setStyleSheet("border: 3px solid #2ecc71; background-color: rgba(46, 204, 113, 0.15);")

    def _refresh_gallery_highlights(self: "WallpaperCommonBaseHostProtocol"):
        for path, widget in self.path_to_card_widget.items():
            self.update_card_style(widget, self.is_path_selected(path))
        self._sync_virtual_gallery_marks()

    def _queued_paths(self: "WallpaperCommonBaseHostProtocol") -> list:
        """Union of every path currently in a monitor display queue (including
        the single assigned image per monitor)."""
        paths = []
        for p in self.monitor_image_paths.values():
            if p:
                paths.append(p)
        for queue in self.monitor_slideshow_queues.values():
            paths.extend(queue)
        return paths

    def _sync_virtual_gallery_marks(self: "WallpaperCommonBaseHostProtocol"):
        """Mark the virtual gallery rows: display-queue members get the green
        border, click-selected rows the indigo border. No-op for the classic
        QLabel-grid galleries, which are styled per-card in ``update_card_style``."""
        gallery = getattr(self, "gallery", None)
        if gallery is None or not hasattr(gallery, "set_in_db"):
            return
        gallery.set_in_db(self._queued_paths())
        gallery.set_selected(self.selected_files)

    def toggle_selection(self: "WallpaperCommonBaseHostProtocol", path: str, *args, **kwargs):
        super().toggle_selection(path)  # type: ignore[safe-super]
        self._sync_virtual_gallery_marks()

    def select_all_items(self: "WallpaperCommonBaseHostProtocol", *args, **kwargs):
        super().select_all_items()  # type: ignore[safe-super]
        self._sync_virtual_gallery_marks()

    def deselect_all_items(self: "WallpaperCommonBaseHostProtocol", *args, **kwargs):
        super().deselect_all_items()  # type: ignore[safe-super]
        self._sync_virtual_gallery_marks()

    def _is_slideshow_validation_ready(self: "WallpaperCommonBaseHostProtocol") -> Tuple[bool, int]:
        target_monitor_ids = list(self.monitor_widgets.keys())
        total_images = 0
        for mid in target_monitor_ids:
            total_images += len(self.monitor_slideshow_queues.get(mid, []))
        return total_images > 0, total_images

    def check_all_monitors_set(self: "WallpaperCommonBaseHostProtocol"):  # noqa: C901
        self._refresh_gallery_highlights()
        for peer in getattr(self, "linked_tabs", []):
            peer._refresh_gallery_highlights()

        target = self if hasattr(self, "set_wallpaper_btn") else None
        if not target:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "set_wallpaper_btn"):
                    target = peer
                    break
        if not target:
            return

        btn = target.set_wallpaper_btn
        if not btn:
            return

        if target.slideshow_timer and target.slideshow_timer.isActive():
            return
        if target.current_wallpaper_worker:
            return

        btn.setStyleSheet(STYLE_START_ACTION)
        target_monitor_ids = list(target.monitor_widgets.keys())
        num_monitors = len(target_monitor_ids)
        set_count = sum(
            1
            for mid in target_monitor_ids
            if mid in target.monitor_image_paths and target.monitor_image_paths[mid]
        )
        is_ready, total_images = target._is_slideshow_validation_ready()

        bg_type = getattr(target, "background_type", "Image")
        solid_color_hex = getattr(target, "solid_color_hex", "#000000")

        if bg_type == "Solid Color":
            btn.setText(f"Set Solid Color ({solid_color_hex})")
            btn.setEnabled(num_monitors > 0)
            return

        if bg_type == "Slideshow":
            if is_ready:
                btn.setEnabled(True)
                btn.setText(
                    f"Start Slideshow ({total_images} total items)"
                )
            else:
                btn.setEnabled(False)
                btn.setText("Slideshow (Drop images/videos)")

        elif bg_type == "Smart Video Slideshow":
            if is_ready:
                btn.setText(
                    f"Start Video Slideshow ({total_images} items)"
                )
                btn.setEnabled(True)
            else:
                btn.setText("Set Video (0 items)")
                btn.setEnabled(False)

        elif bg_type == "Smart Video":
            if set_count > 0:
                btn.setText("Set Video")
                btn.setEnabled(True)
            else:
                btn.setText("Set Video (0 items)")
                btn.setEnabled(False)

        elif set_count > 0:
            btn.setText("Set Wallpaper")
            btn.setEnabled(True)
        else:
            btn.setText("Set Wallpaper (0 items)")
            btn.setEnabled(False)
        target.wallpapers_changed.emit()


__all__ = ["_MonitorSelectionMixin"]
