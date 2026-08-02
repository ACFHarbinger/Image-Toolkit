"""Monitor selection sync (self + linked peers) and the "Set Wallpaper" button state.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QVBoxLayout, QWidget

from ......components import DraggableMonitorContainer, MonitorDropView
from ......styles import STYLE_START_ACTION


class _MonitorSelectionMixin:
    """Monitor selection (with peer sync) and the shared "Set Wallpaper" button."""

    def set_system_display_ref(self, system_display):
        """Set the system display reference.

        Args:
            system_display: The system display reference.
        """
        self._system_display_ref = system_display

    def create_monitor_layout_section(self, title: str) -> QGroupBox:
        group_box_style = """
            QGroupBox {
                border: 1px solid #4f545c;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 10px;
                color: white;
                border-radius: 4px;
            }
        """
        layout_group = QGroupBox(title)
        layout_group.setStyleSheet(group_box_style)

        self.monitor_layout_container = DraggableMonitorContainer()

        gb_layout = QVBoxLayout(layout_group)
        gb_layout.addWidget(self.monitor_layout_container)
        return layout_group

    def _select_monitor(self, monitor_id: Optional[str]):
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

        QApplication.processEvents()

        self._on_monitor_selected(new_id)

    def _select_monitor_peer(self, monitor_id: Optional[str]):
        self._current_monitor_id = monitor_id
        for mid, widget in self.monitor_widgets.items():
            if isinstance(widget, MonitorDropView):
                widget.set_selected(mid == monitor_id)
                widget.repaint()

        QApplication.processEvents()

        self._on_monitor_selected(monitor_id)

    def _on_monitor_selected(self, monitor_id: Optional[str]):
        pass

    def update_card_style(self, widget: QWidget, is_selected: bool):
        super().update_card_style(widget, is_selected)

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

    def _refresh_gallery_highlights(self):
        for path, widget in self.path_to_card_widget.items():
            self.update_card_style(widget, self.is_path_selected(path))

    def _is_slideshow_validation_ready(self) -> Tuple[bool, int]:
        target_monitor_ids = list(self.monitor_widgets.keys())
        total_images = 0
        for mid in target_monitor_ids:
            total_images += len(self.monitor_slideshow_queues.get(mid, []))
        return total_images > 0, total_images

    def check_all_monitors_set(self):  # noqa: C901
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
