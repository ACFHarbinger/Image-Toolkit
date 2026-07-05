import json
import os
import platform
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from backend.src.constants import (
    DAEMON_CONFIG_PATH,
    SUPPORTED_IMG_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
)
from backend.src.core import WallpaperManager
from backend.src.core.wallpaper import find_qdbus_binary
from PySide6.QtCore import (
    QEvent,
    QPoint,
    QRect,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QCursor, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from screeninfo import Monitor, get_monitors
from send2trash import send2trash  # pyrefly: ignore [untyped-import]
from shiboken6 import Shiboken as sip

from .....classes import AbstractClassSingleGallery
from .....components import (
    DraggableLabel,
    DraggableMonitorContainer,
    MonitorDropView,
)
from .....helpers import ImageScannerWorker, VideoScannerWorker
from .....styles import STYLE_START_ACTION
from .....utils.sort_utils import natural_sort_key
from .....windows import ImagePreviewWindow, SlideshowQueueWindow
from ..graph.data import GraphData, NodeData


class WallpaperCommonBase(AbstractClassSingleGallery):
    """Shared state and helpers for wallpaper subtabs.

    Holds monitor state, gallery helpers, and scanner methods.
    Subclasses build their own UI layouts using these facilities.
    """

    wallpapers_changed = Signal()
    monitors_updated = Signal(list)      # List[Monitor]
    qml_monitors_changed = Signal(list)  # List of dicts
    qml_status_changed = Signal(str)
    directory_scanned = Signal(str)

    # Sync signals
    sync_page_changed = Signal(int)
    sync_page_size_changed = Signal(str)
    sync_thumb_size_changed = Signal(int)
    sync_sort_combo_changed = Signal(str)
    sync_sort_dir_changed = Signal(bool)

    # Subclass-specific attributes used in shared methods
    slideshow_timer: Optional[QTimer]
    current_wallpaper_worker: Optional[Any]
    set_wallpaper_btn: Optional[Any]
    background_type_combo: Optional[Any]
    background_type: str
    solid_color_hex: str
    _graphs: Dict[str, Any]
    _monitor_display_ref: Optional[Any]
    _view: Any
    _scene: Any
    main_scroll_area: Optional[Any]
    scan_directory_path: Optional[Any]
    interval_min_spinbox: Optional[Any]
    style_combo: Optional[Any]

    def __init__(self):
        super().__init__()

        self.qdbus: Optional[str] = find_qdbus_binary()

        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropView] = {}
        self.monitor_image_paths: Dict[str, Optional[str]] = {}
        self.monitor_slideshow_queues: Dict[str, List[str]] = {}
        self.monitor_current_index: Dict[str, int] = {}
        self.monitor_history: Dict[str, List[str]] = {}

        self.img_scanner_worker: Optional[Any] = None
        self.img_scanner_thread: Optional[QThread] = None
        self.vid_scanner_worker: Optional[VideoScannerWorker] = None

        self.scanned_dir = None
        self.path_to_label_map = {}
        self._filtering_event = False
        self._system_display_ref = None

        self._current_monitor_id = None
        self.linked_tabs = []
        self.open_image_preview_windows = []
        self.open_queue_windows = []

        # Common attributes used or overridden by subclasses
        self.slideshow_timer = None
        self.current_wallpaper_worker = None
        self.background_type = "Image"
        self.solid_color_hex = "#000000"

        self._pagination_debounce_timer = QTimer()
        self._pagination_debounce_timer.setSingleShot(True)
        self._pagination_debounce_timer.setInterval(200)
        self._pagination_debounce_timer.timeout.connect(self._update_pagination_ui)

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

    def check_all_monitors_set(self):
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

    def handle_monitor_double_click(self, monitor_id: str):
        bg_type = getattr(self, "background_type", "Image")
        if bg_type == "Solid Color":
            return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        for win in list(self.open_queue_windows):
            try:
                if (
                    isinstance(win, SlideshowQueueWindow)
                    and win.monitor_id == monitor_id
                ):
                    win.activateWindow()
                    return
            except RuntimeError:
                if win in self.open_queue_windows:
                    self.open_queue_windows.remove(win)

        other_names = {
            mid: widget.monitor.name for mid, widget in self.monitor_widgets.items()
        }
        assert monitor_name is not None
        window = SlideshowQueueWindow(
            monitor_name,
            monitor_id,
            queue,
            pixmap_cache=self._initial_pixmap_cache,
            other_queues=self.monitor_slideshow_queues,
            other_names=other_names,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.queue_reordered.connect(self.on_queue_reordered)
        window.image_preview_requested.connect(self.handle_full_image_preview)
        window.item_swap_requested.connect(self.handle_item_swap_request)

        self.open_queue_windows = [
            w for w in self.open_queue_windows if not sip.isValid(w)
        ]

        def remove_closed_win(event: Any):
            self.open_queue_windows = [
                w for w in self.open_queue_windows if w != window and sip.isValid(w)
            ]
            event.accept()

        window.closeEvent = remove_closed_win
        window.show()
        self.open_queue_windows.append(window)

    def handle_thumbnail_double_click(self, image_path: str):
        if self._current_monitor_id is not None:
            self.on_image_dropped(self._current_monitor_id, image_path)
        else:
            self.handle_full_image_preview(image_path)

    def handle_full_image_preview(self, image_path: str):
        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if platform.system() == "Windows":
                    start_fn = getattr(os, "startfile", None)
                    if start_fn:
                        start_fn(image_path)
                elif platform.system() == "Linux":
                    subprocess.Popen(
                        ["xdg-open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                QMessageBox.warning(
                    self, "Video Error", f"Could not launch video player: {e}"
                )
            return

        all_paths_list = (
            sorted(self.gallery_image_paths, key=natural_sort_key)
            if self.gallery_image_paths
            else [image_path]
        )
        try:
            start_index = all_paths_list.index(image_path)
        except ValueError:
            all_paths_list = [image_path]
            start_index = 0

        for win in list(self.open_image_preview_windows):
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow()
                return
        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=all_paths_list,
            start_index=start_index,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.open_image_preview_windows = [
            w for w in self.open_image_preview_windows if not sip.isValid(w)
        ]

        def remove_closed_win(event: Any):
            self.open_image_preview_windows = [
                w
                for w in self.open_image_preview_windows
                if w != window and sip.isValid(w)
            ]
            event.accept()

        window.closeEvent = remove_closed_win
        window.show()
        self.open_image_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        if getattr(self, "background_type", None) == "Solid Color":
            return
        menu = QMenu(self)

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        view_text = "Play Video" if is_video else "View Full Size Preview"

        view_action = QAction(view_text, self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        if self.monitor_widgets:
            menu.addSeparator()
            add_menu = menu.addMenu("Add to Monitor Queue")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                action.triggered.connect(
                    lambda checked,
                    mid=monitor_id,
                    img_path=path: self.on_image_dropped(mid, img_path)
                )
                add_menu.addAction(action)

            add_graph_menu = menu.addMenu("Add to Monitor Graph")
            for monitor_id, widget in self.monitor_widgets.items():
                monitor_name = widget.monitor.name
                action = QAction(f"{monitor_name} (ID: {monitor_id})", self)
                action.triggered.connect(
                    lambda checked,
                    mid=monitor_id,
                    img_path=path: self.add_image_to_graph(mid, img_path)
                )
                add_graph_menu.addAction(action)

        menu.addSeparator()
        delete_action = QAction("🗑️ Delete File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def handle_delete_image(self, path: str):
        if not path or not Path(path).exists():
            QMessageBox.warning(
                self, "Delete Error", "File not found or path is invalid."
            )
            return
        filename = os.path.basename(path)
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        reply = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"Move to {action_name}:\n\n{filename}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            if send_to_trash_enabled:
                send2trash(path)
            else:
                os.remove(path)

            if path in self.gallery_image_paths:
                self.gallery_image_paths.remove(path)

            if path in self.path_to_label_map:
                widget = self.path_to_label_map.pop(path)
                widget.deleteLater()

            # Remove from queues of all tabs (local and peer)
            for tab in [self] + getattr(self, "linked_tabs", []):
                if path in tab.gallery_image_paths:
                    tab.gallery_image_paths.remove(path)
                if path in tab.path_to_label_map:
                    w = tab.path_to_label_map.pop(path)
                    w.deleteLater()

            for mid in self.monitor_slideshow_queues:
                self.monitor_slideshow_queues[mid] = [
                    p for p in self.monitor_slideshow_queues[mid] if p != path
                ]
            for mid, current_path in self.monitor_image_paths.items():
                if current_path == path:
                    self.monitor_image_paths[mid] = None

            self.update_monitor_widget_ui(mid)
            self.refresh_gallery_view()
            for peer in getattr(self, "linked_tabs", []):
                peer.refresh_gallery_view()
            self.check_all_monitors_set()

            QMessageBox.information(
                self, "Success", f"File moved to {action_name}: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Deletion Failed", f"Could not delete the file: {e}"
            )

    def add_image_to_graph(self, monitor_id: str, path: str):
        monitor_subtab = None
        if hasattr(self, "_graphs"):
            monitor_subtab = self
        elif hasattr(self, "_monitor_display_ref"):
            monitor_subtab = self._monitor_display_ref

        if monitor_subtab:
            if monitor_id not in monitor_subtab._graphs:
                monitor_subtab._graphs[monitor_id] = GraphData()
            graph = monitor_subtab._graphs[monitor_id]

            if monitor_subtab._current_monitor_id == monitor_id:
                center = monitor_subtab._view.mapToScene(monitor_subtab._view.viewport().rect().center())
                monitor_subtab._scene.add_node(path, center)
            else:
                nid = str(uuid.uuid4())
                is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
                display_mode = "video_runtime" if is_video else "fixed"
                nd = NodeData(node_id=nid, file_path=path,
                              display_mode=display_mode, duration_sec=30.0,
                              pos_x=0.0, pos_y=0.0)
                graph.nodes[nid] = nd
                if graph.basis_node_id is None:
                     graph.basis_node_id = nid

    def on_images_dropped(self, monitor_id: str, image_paths: list):
        if not image_paths:
            return

        for image_path in image_paths:
            self._process_single_drop(monitor_id, image_path)

        if image_paths:
            first_path = image_paths[0]
            self.monitor_image_paths[monitor_id] = first_path

            queue = self.monitor_slideshow_queues.get(monitor_id, [])
            batch_start = len(queue) - len(image_paths)
            self.monitor_current_index[monitor_id] = max(batch_start, 0)

            self.update_monitor_widget_ui(monitor_id)

        if hasattr(self, "toggle_daemon") and self._is_daemon_running_config():
            self.toggle_daemon(True)
        else:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "toggle_daemon") and peer._is_daemon_running_config():
                    peer.toggle_daemon(True)

        self.deselect_all_items()

    def _process_single_drop(self, monitor_id: str, image_path: str):
        is_video = image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        target = self if hasattr(self, "background_type_combo") else None
        if not target:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "background_type_combo"):
                    target = peer
                    break
        if target:
            combo = target.background_type_combo
            if combo is not None:
                bg_type = combo.currentText()
                if is_video and bg_type == "Image":
                    combo.setCurrentText("Smart Video")
                elif not is_video and bg_type in ["Smart Video", "Smart Video Slideshow"]:
                    combo.setCurrentText("Image")
                if bg_type == "Solid Color":
                    combo.setCurrentText("Image")

        if monitor_id not in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id] = []
        self.monitor_slideshow_queues[monitor_id].append(image_path)

        self.monitor_image_paths[monitor_id] = image_path

        queue = self.monitor_slideshow_queues[monitor_id]
        self.monitor_current_index[monitor_id] = len(queue) - 1

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

    @Slot(str, QMenu)
    def on_monitor_context_menu(self, monitor_id: str, menu: QMenu):
        if self._current_monitor_id == monitor_id:
            unselect_action = menu.addAction("Unselect Display")
            unselect_action.triggered.connect(lambda: self._select_monitor(monitor_id))
            menu.addSeparator()

        view_queue_action = menu.addAction("View Wallpaper Queue")
        view_queue_action.triggered.connect(lambda: self.handle_monitor_double_click(monitor_id))
        menu.addSeparator()

        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if queue:
            set_active_menu = menu.addMenu("Set Active Wallpaper from Queue...")

            current_active = self.monitor_image_paths.get(monitor_id)
            for i, path in enumerate(queue):
                filename = os.path.basename(path)
                action = set_active_menu.addAction(f"[{i}] {filename}")
                action.setCheckable(True)
                if path == current_active:
                    action.setChecked(True)
                action.triggered.connect(
                    lambda _, p=path, idx=i: self._set_specific_wallpaper(monitor_id, p, idx)
                )

            other_monitors = [
                (mid, widget)
                for mid, widget in self.monitor_widgets.items()
                if mid != monitor_id
            ]
            if other_monitors:
                menu.addSeparator()
                swap_menu = menu.addMenu("🔀 Swap Active Image with Monitor...")
                for t_mid, t_widget in other_monitors:
                    t_name = t_widget.monitor.name
                    t_active_path = self.monitor_image_paths.get(t_mid)
                    if t_active_path:
                        t_label = f"{t_name}  ←→  {os.path.basename(t_active_path)}"
                    else:
                        t_label = f"{t_name}  (empty)"
                    action = swap_menu.addAction(t_label)
                    action.setEnabled(bool(t_active_path and current_active))
                    action.triggered.connect(
                        lambda _, s=monitor_id, t=t_mid: self.handle_item_swap_request(
                            s, 0, t, 0
                        )
                    )

        menu.addSeparator()
        clear_graph_action = menu.addAction("Clear Monitor Graph")
        clear_graph_action.triggered.connect(
            lambda _, m=monitor_id: self.clear_monitor_graph(m)
        )

    def clear_monitor_graph(self, monitor_id: str):
        reply = QMessageBox.question(
            self, "Clear Graph",
            f"Are you sure you want to clear the graph for Monitor {monitor_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if hasattr(self, "_monitor_display_ref") and self._monitor_display_ref:
            self._monitor_display_ref.clear_monitor_graph_direct(monitor_id)
        else:
            self.clear_monitor_graph_direct(monitor_id)

    def clear_monitor_graph_direct(self, monitor_id: str):
        if hasattr(self, "_graphs"):
            self._graphs[monitor_id] = GraphData()
            if self._current_monitor_id == monitor_id and hasattr(self, "_scene"):
                self._scene.load_graph(self._graphs[monitor_id])
                if hasattr(self, "_on_graph_changed"):
                    self._on_graph_changed()

    def _set_specific_wallpaper(self, monitor_id: str, path: str, index: Optional[int] = None):
        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"File not found:\n{path}")
            return

        self.monitor_image_paths[monitor_id] = path

        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if index is not None and 0 <= index < len(queue) and queue[index] == path:
            self.monitor_current_index[monitor_id] = index
        elif path in queue:
            self.monitor_current_index[monitor_id] = queue.index(path)

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

        if hasattr(self, "run_wallpaper_worker"):
            self.run_wallpaper_worker()
        else:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "run_wallpaper_worker"):
                    peer.run_wallpaper_worker()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        self.on_images_dropped(monitor_id, [image_path])

    def swap_monitors(self, m0: str, m1: str = ""):
        monitor_ids = list(self.monitor_widgets.keys())
        if len(monitor_ids) < 2:
            return

        if not m1:
            if len(monitor_ids) == 2:
                m1 = next(mid for mid in monitor_ids if mid != m0)
            else:
                return

        if m0 not in self.monitor_widgets or m1 not in self.monitor_widgets:
            return

        self.monitor_image_paths[m0], self.monitor_image_paths[m1] = (
            self.monitor_image_paths.get(m1),
            self.monitor_image_paths.get(m0),
        )
        self.monitor_slideshow_queues[m0], self.monitor_slideshow_queues[m1] = (
            self.monitor_slideshow_queues.get(m1, []).copy(),
            self.monitor_slideshow_queues.get(m0, []).copy(),
        )
        self.monitor_current_index[m0], self.monitor_current_index[m1] = (
            self.monitor_current_index.get(m1, -1),
            self.monitor_current_index.get(m0, -1),
        )

        for mid in [m0, m1]:
            self.update_monitor_widget_ui(mid)

        self.check_all_monitors_set()

        if hasattr(self, "toggle_daemon") and self._is_daemon_running_config():
            self.toggle_daemon(True)
        else:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "toggle_daemon") and peer._is_daemon_running_config():
                    peer.toggle_daemon(True)

    def swap_graphs(self, m0: str, m1: str = ""):
        monitor_ids = list(self.monitor_widgets.keys())
        if len(monitor_ids) < 2:
            return
        if not m1:
            if len(monitor_ids) == 2:
                m1 = next(mid for mid in monitor_ids if mid != m0)
            else:
                return

        if hasattr(self, "_monitor_display_ref") and self._monitor_display_ref:
            self._monitor_display_ref.swap_graphs(m0, m1)
        elif hasattr(self, "_graphs") and (m0 in self._graphs or m1 in self._graphs):
            self._graphs[m0], self._graphs[m1] = (
                self._graphs.get(m1, GraphData()),
                self._graphs.get(m0, GraphData()),
            )
            if self._current_monitor_id in [m0, m1]:
                self._on_monitor_selected(self._current_monitor_id)

    def handle_item_swap_request(self, s_mid: str, s_idx: int, t_mid: str, t_idx: int):
        src_queue = self.monitor_slideshow_queues.get(s_mid, [])
        target_queue = self.monitor_slideshow_queues.get(t_mid, [])

        if s_idx < len(src_queue) and t_idx < len(target_queue):
            src_queue[s_idx], target_queue[t_idx] = (
                target_queue[t_idx],
                src_queue[s_idx],
            )

            if s_idx == 0:
                self.on_queue_reordered(s_mid, src_queue)
            if t_mid != s_mid and t_idx == 0:
                self.on_queue_reordered(t_mid, target_queue)

            for win in self.open_queue_windows:
                if sip.isValid(win) and isinstance(win, SlideshowQueueWindow):
                    if win.monitor_id == s_mid:
                        win.populate_list(src_queue)
                    elif win.monitor_id == t_mid:
                        win.populate_list(target_queue)

            self.check_all_monitors_set()

            if hasattr(self, "toggle_daemon") and self._is_daemon_running_config():
                self.toggle_daemon(True)
            else:
                for peer in getattr(self, "linked_tabs", []):
                    if hasattr(peer, "toggle_daemon") and peer._is_daemon_running_config():
                        peer.toggle_daemon(True)

    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        self.monitor_slideshow_queues[monitor_id] = new_queue
        self.monitor_current_index[monitor_id] = -1
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

    @Slot(str)
    def handle_clear_monitor_queue(self, monitor_id: str):
        if monitor_id not in self.monitor_widgets:
            return
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        if monitor_id in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id].clear()
        if monitor_id in self.monitor_image_paths:
            self.monitor_image_paths[monitor_id] = None
        if monitor_id in self.monitor_current_index:
            self.monitor_current_index[monitor_id] = -1

        system = platform.system()
        num_monitors_detected = len(self.monitors)
        current_system_wallpaper_paths = {}
        if system == "Linux" and num_monitors_detected > 0:
            try:
                if self.qdbus:
                    raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
                    current_system_wallpaper_paths = self._get_rotated_map_for_ui(
                        raw_paths
                    )
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
        if system_wallpaper_path and Path(system_wallpaper_path).exists():
            self.monitor_image_paths[monitor_id] = system_wallpaper_path

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

        QMessageBox.information(
            self,
            "Monitor Cleared",
            f"All pending items and the slideshow queue for **{monitor_name}** have been cleared.\n\nThe system's current background remains unchanged.",
        )

    def update_monitor_widget_ui(self, monitor_id: str):
        self._update_widget_ui_local(monitor_id)
        for peer in getattr(self, "linked_tabs", []):
            peer._update_widget_ui_local(monitor_id)

    def _update_widget_ui_local(self, monitor_id: str):
        widget = self.monitor_widgets.get(monitor_id)
        if widget:
            path = self.monitor_image_paths.get(monitor_id)
            if path:
                thumb = self._get_or_generate_thumbnail(path)
                widget.set_image(path, thumb)
            else:
                widget.clear()

    def closeEvent(self, event):
        for win in list(self.open_queue_windows):
            try:
                if sip.isValid(win):
                    win.close()
            except RuntimeError:
                pass
        self.open_queue_windows = []

        for win in list(self.open_image_preview_windows):
            try:
                if sip.isValid(win):
                    win.close()
            except RuntimeError:
                pass
        self.open_image_preview_windows = []

        super().closeEvent(event)

    def _refresh_open_queue_window(self, monitor_id: str):
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        for win in self.open_queue_windows:
            if (
                sip.isValid(win)
                and isinstance(win, SlideshowQueueWindow)
                and win.monitor_id == monitor_id
            ):
                win.populate_list(queue)

    def _is_daemon_running_config(self) -> bool:
        if not os.path.exists(DAEMON_CONFIG_PATH):
            return False
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                config = json.load(f)
            return config.get("running", False)
        except Exception:
            return False

    # ---- Thumbnail helpers -----------------------------------------------

    def _cache_get_thumb(self, path: str) -> Optional[QPixmap]:
        img = self._initial_pixmap_cache.get(path)
        if img is None:
            return None
        return QPixmap.fromImage(img) if isinstance(img, QImage) else img

    def _get_or_generate_thumbnail(self, path: str) -> Optional[QPixmap]:
        if not path:
            return None
        thumb = self._cache_get_thumb(path)
        if not thumb:
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                thumb = self._generate_video_thumbnail(path)
                if thumb:
                    self._initial_pixmap_cache[path] = thumb.toImage()
            elif os.path.exists(path):
                thumb = QPixmap(path)
        return thumb

    # ---- Monitor layout ---------------------------------------------------

    def populate_monitor_layout(self):
        self.monitor_layout_container.clear_widgets()
        self.monitor_widgets.clear()
        system_monitors = []
        try:
            system_monitors = get_monitors()
            system_monitors = sorted(system_monitors, key=lambda m: m.x)
            self.monitors = system_monitors
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
            self.monitors = []

        if not self.monitors or not self.monitors[0].name or "Mock" in self.monitors[0].name:
            cast(Any, self.monitor_layout_container).addWidget(
                QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?")
            )
            self.monitors_updated.emit(self.monitors)
            return

        current_system_wallpaper_paths = {}
        system = platform.system()
        num_monitors_detected = len(self.monitors)
        if system == "Linux" and num_monitors_detected > 0:
            try:
                if self.qdbus:
                    current_system_wallpaper_paths = (
                        WallpaperManager.get_current_system_wallpaper_path_kde(
                            self.monitors, self.qdbus
                        )
                    )
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        monitor_info_list = []
        for i, m in enumerate(self.monitors):
            m_id = str(i)
            m_name = m.name if m.name else f"Display {m_id}"
            monitor_info_list.append((m_id, m_name))

        monitor_id_to_widget = {}
        for i, monitor in enumerate(self.monitors):
            monitor_id = str(i)
            drop_widget = MonitorDropView(monitor, monitor_id)

            real_name = drop_widget.get_real_monitor_name()
            if real_name:
                drop_widget.set_hardware_name(real_name)

            drop_widget.other_monitors = [
                (mid, name) for mid, name in monitor_info_list if mid != monitor_id
            ]

            drop_widget.images_dropped.connect(self.on_images_dropped)
            drop_widget.clicked.connect(self._select_monitor)
            drop_widget.double_clicked.connect(
                lambda m_id=monitor_id: self.handle_monitor_double_click(m_id)
            )
            drop_widget.clear_requested_id.connect(self.handle_clear_monitor_queue)
            drop_widget.swap_requested_id.connect(self.swap_monitors)
            drop_widget.swap_graph_requested_id.connect(self.swap_graphs)
            drop_widget.context_menu_requested.connect(self.on_monitor_context_menu)
            self.monitor_widgets[monitor_id] = drop_widget

            current_image = self.monitor_image_paths.get(monitor_id)
            image_path_to_display = current_image

            if not image_path_to_display:
                from pathlib import Path
                system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
                if system_wallpaper_path and Path(system_wallpaper_path).exists():
                    image_path_to_display = system_wallpaper_path

            if image_path_to_display:
                if not self.monitor_image_paths.get(monitor_id):
                    self.monitor_image_paths[monitor_id] = image_path_to_display
                thumb = self._get_or_generate_thumbnail(image_path_to_display)
                drop_widget.set_image(image_path_to_display, thumb)
            else:
                drop_widget.clear()

            monitor_id_to_widget[monitor_id] = drop_widget
            self.monitor_widgets[monitor_id] = drop_widget

        for monitor in self.monitors:
            system_index = -1
            for i, sys_mon in enumerate(system_monitors):
                if (
                    sys_mon.x == monitor.x
                    and sys_mon.y == monitor.y
                    and sys_mon.width == monitor.width
                    and sys_mon.height == monitor.height
                ):
                    system_index = i
                    break
            if system_index != -1:
                monitor_id = str(system_index)
                if monitor_id in monitor_id_to_widget:
                    self.monitor_layout_container.addWidget(monitor_id_to_widget[monitor_id]) # pyrefly: ignore [bad-argument-type]

        self.monitors_updated.emit(self.monitors)

    def _get_rotated_map_for_ui(self, raw_paths: Dict[str, str | None]) -> Dict[str, str | None]:
        mapped = {}
        for idx, path in raw_paths.items():
            mapped[idx] = path
        return mapped

    def _get_current_system_image_paths_for_all(self) -> Dict[str, Optional[str]]:
        system = platform.system()
        num_monitors = len(self.monitors)
        current_paths: Dict[str, Optional[str]] = {}
        if num_monitors == 0:
            return current_paths
        if system == "Linux":
            try:
                if self.qdbus:
                    raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
                    current_paths = self._get_rotated_map_for_ui(raw_paths)
            except Exception:
                pass
        return current_paths

    # ---- Gallery ----------------------------------------------------------

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        draggable_label = DraggableLabel(
            path, size, selection_provider=lambda: self.selected_files
        )
        draggable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        draggable_label.path_clicked.connect(self.toggle_selection)
        draggable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        draggable_label.path_right_clicked.connect(self.show_image_context_menu)

        self.path_to_label_map[path] = draggable_label
        return draggable_label

    def populate_scan_image_gallery(self, directory: str, emit_signal: bool = True):
        if getattr(self, "background_type", None) == "Solid Color":
            return

        self.scanned_dir = directory
        path_edit = getattr(self, "scan_directory_path", None)
        if path_edit is not None:
            path_edit.setText(directory)

        if emit_signal:
            self.directory_scanned.emit(directory)

        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self._initial_pixmap_cache.clear()
        self.cancel_loading()
        self.gallery_image_paths = []

        try:
            entries = sorted(
                os.scandir(directory), key=lambda e: natural_sort_key(e.name)
            )
            all_exts = list(SUPPORTED_IMG_FORMATS) + list(SUPPORTED_VIDEO_FORMATS)
            valid_exts = tuple(f".{fmt.lower().lstrip('.')}" for fmt in all_exts)
            quick_paths = [
                e.path
                for e in entries
                if e.is_file() and e.name.lower().endswith(valid_exts)
            ]
            quick_paths_limited = quick_paths[:5000]
            if quick_paths_limited:
                self.start_loading_gallery(
                    quick_paths_limited, show_progress=False, append=False
                )
        except Exception:
            pass

        if self.img_scanner_thread is not None:
            if self.img_scanner_thread.isRunning():
                self.img_scanner_thread.requestInterruption()
                self.img_scanner_thread.quit()
                self.img_scanner_thread.wait()
            self.img_scanner_thread.deleteLater()
            self.img_scanner_thread = None

        if self.vid_scanner_worker is not None:
            try:
                self.vid_scanner_worker.signals.thumbnail_ready.disconnect()
                self.vid_scanner_worker.signals.finished.disconnect()
            except Exception:
                pass
            self.vid_scanner_worker.stop()
            self.vid_scanner_worker = None

        self.img_scanner_worker = ImageScannerWorker(directory)
        self.img_scanner_thread = QThread()
        self.img_scanner_worker.moveToThread(self.img_scanner_thread)

        self.img_scanner_thread.started.connect(self.img_scanner_worker.run_scan)
        self.img_scanner_worker.scan_finished.connect(self._on_image_scan_finished)
        self.img_scanner_worker.scan_error.connect(self.handle_scan_error)

        self.img_scanner_worker.scan_finished.connect(self.img_scanner_thread.quit)
        self.img_scanner_thread.finished.connect(self.img_scanner_thread.deleteLater)
        self.img_scanner_thread.finished.connect(
            lambda: setattr(self, "img_scanner_thread", None)
        )
        self.img_scanner_thread.start()

    @Slot(list)
    def _on_image_scan_finished(self, image_paths: list):
        existing_paths = set(getattr(self, "master_image_paths", []))
        new_paths = [p for p in image_paths if p not in existing_paths]

        if new_paths:
            self.start_loading_gallery(new_paths, show_progress=False, append=True)
        else:
            self.refresh_gallery_view()

        if self.scanned_dir:
            self.vid_scanner_worker = VideoScannerWorker(self.scanned_dir)
            self.vid_scanner_worker.signals.thumbnail_ready.connect(
                self._add_video_thumbnail_manual
            )
            self.vid_scanner_worker.signals.finished.connect(
                self._on_video_scan_finished
            )
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().start(self.vid_scanner_worker)

    @Slot()
    def _on_video_scan_finished(self):
        if self.gallery_image_paths:
            self.gallery_image_paths.sort(key=natural_sort_key)
            self.refresh_gallery_view()

    @Slot(str, QImage)
    def _add_video_thumbnail_manual(self, path: str, q_image: QImage):
        if path in self.gallery_image_paths:
            return

        pixmap = QPixmap.fromImage(q_image)

        if pixmap.isNull():
            if not hasattr(self, "_failed_paths"):
                self._failed_paths = set()
            self._failed_paths.add(path)

        self.gallery_image_paths.append(path)
        self._initial_pixmap_cache[path] = q_image
        self._pagination_debounce_timer.start()

        total_items = len(self.gallery_image_paths)
        start_index = self.current_page * self.page_size
        end_index = start_index + self.page_size
        item_index = total_items - 1

        if start_index <= item_index < end_index:
            card = self.create_card_widget(path, pixmap)

            if self.gallery_layout:
                current_count = self.gallery_layout.count()
                cols = self.calculate_columns()
                row = current_count // cols
                col = current_count % cols
                self.gallery_layout.addWidget(
                    card,
                    row,
                    col,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                )

            self.path_to_card_widget[path] = card

    def _handle_autoscroll(self, global_pos: QPoint):
        if not self.isVisible():
            return
        scroll_area = getattr(self, "main_scroll_area", None)
        if scroll_area is None:
            return

        vbar = scroll_area.verticalScrollBar()
        if not vbar or not vbar.isVisible():
            return

        viewport = scroll_area.viewport()
        vp_global_pos = viewport.mapToGlobal(QPoint(0, 0))
        vp_global_rect = QRect(vp_global_pos, viewport.size())

        buffer = 50
        if (global_pos.x() < vp_global_rect.left() - buffer) or (
            global_pos.x() > vp_global_rect.right() + buffer
        ):
            return

        height = vp_global_rect.height()
        threshold = 120
        scroll_step = 20
        rel_y = global_pos.y() - vp_global_rect.top()

        if rel_y < threshold:
            vbar.setValue(vbar.value() - scroll_step)
        elif rel_y > height - threshold:
            vbar.setValue(vbar.value() + scroll_step)

    def eventFilter(self, watched, event):
        if self._filtering_event:
            return False

        self._filtering_event = True
        try:
            if not self.isVisible():
                return False
        finally:
            self._filtering_event = False

        if event.type() == QEvent.Type.Wheel:
            if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                global_pos = QCursor.pos()
                if self.rect().contains(self.mapFromGlobal(global_pos)):
                    scroll_area = getattr(self, "main_scroll_area", None)
                    if scroll_area is not None:
                        vbar = scroll_area.verticalScrollBar()
                        if vbar and vbar.isVisible():
                            delta = event.angleDelta().y()
                            vbar.setValue(vbar.value() - delta)
                            return True

        elif event.type() in (QEvent.Type.DragMove, QEvent.Type.DragEnter):
            self._handle_autoscroll(QCursor.pos())

        return super().eventFilter(watched, event)

    def cancel_scanning(self):
        if self.img_scanner_thread and self.img_scanner_thread.isRunning():
            self.img_scanner_thread.quit()

    @Slot(list)
    def display_scan_results(self, image_paths: list):
        if self.background_type == "Solid Color":
            return
        self.clear_gallery_widgets()
        self.path_to_label_map.clear()
        self.check_all_monitors_set()
        final_paths = sorted(list(set(image_paths)), key=natural_sort_key)
        if not final_paths:
            return
        self.start_loading_gallery(final_paths)

    def handle_scan_error(self, message: str):
        self.clear_gallery_widgets()
        QMessageBox.warning(self, "Error Scanning", message)
        self.common_show_placeholder(
            self.gallery_layout, "Browse for a directory.", self.calculate_columns()
        )

    def browse_scan_directory(self):
        from PySide6.QtWidgets import QFileDialog
        if self.background_type == "Solid Color":
            QMessageBox.warning(
                self,
                "Mode Conflict",
                "Cannot browse directory while Solid Color background is selected.",
            )
            return

        if ImageScannerWorker is None:
            QMessageBox.warning(
                self,
                "Missing Helpers",
                "The ImageScannerWorker or ImageLoaderWorker could not be imported.",
            )
            return

        start_dir = self.last_browsed_scan_dir
        options = (
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        directory = QFileDialog.getExistingDirectory(
            self, "Select directory to scan", start_dir, options
        )

        if directory:
            self.last_browsed_scan_dir = directory
            path_edit = getattr(self, "scan_directory_path", None)
            if path_edit is not None:
                path_edit.setText(directory)
            self.populate_scan_image_gallery(directory)

    # ---- QML handlers -----------------------------------------------------

    @Slot()
    def request_monitors_qml(self):
        monitor_data = []
        for m in self.monitors:
            monitor_data.append(
                {
                    "name": m.name,
                    "x": m.x,
                    "y": m.y,
                    "width": m.width,
                    "height": m.height,
                    "is_primary": m.is_primary,
                }
            )
        self.qml_monitors_changed.emit(monitor_data)

    @Slot(str, str)
    def set_wallpaper_qml(self, path, monitor_name="All"):
        if monitor_name == "All":
            for mid in self.monitor_widgets.keys():
                self.monitor_image_paths[mid] = path
        else:
            if monitor_name in self.monitor_widgets:
                self.monitor_image_paths[monitor_name] = path
        if hasattr(self, "handle_set_wallpaper_click"):
            self.handle_set_wallpaper_click()

    @Slot(int, int, str, bool, bool)
    def update_slideshow_settings_qml(
        self, interval_min, style, random_order, include_subdirs
    ):
        if hasattr(self, "interval_min_spinbox"):
            self.interval_min_spinbox.setValue(interval_min)
        if hasattr(self, "style_combo"):
            self.style_combo.setCurrentText(style)
        self.request_monitors_qml()

    @Slot(str)
    def drop_image_qml(self, path):
        self.set_wallpaper_qml(path, "All")

    # ---- Sync overrides ---------------------------------------------------

    def _jump_to_page(self, page_index: int, emit_signal: bool = True):
        if self.current_page == page_index:
            return
        super()._jump_to_page(page_index)
        if emit_signal:
            self.sync_page_changed.emit(self.current_page)

    def _change_page(self, delta: int, emit_signal: bool = True):
        old_page = self.current_page
        super()._change_page(delta)
        if self.current_page != old_page and emit_signal:
            self.sync_page_changed.emit(self.current_page)

    def _on_page_size_changed(self, text: str, emit_signal: bool = True):
        super()._on_page_size_changed(text)
        if emit_signal:
            self.sync_page_size_changed.emit(text)

    def _on_thumb_slider_changed(self, value: int, emit_signal: bool = True):
        super()._on_thumb_slider_changed(value)
        if emit_signal:
            self.sync_thumb_size_changed.emit(value)

    def _on_sort_combo_changed(self, label: str, emit_signal: bool = True):
        super()._on_sort_combo_changed(label)
        if emit_signal:
            self.sync_sort_combo_changed.emit(label)

    def _on_sort_dir_toggled(self, btn, emit_signal: bool = True):
        super()._on_sort_dir_toggled(btn)
        if emit_signal:
            self.sync_sort_dir_changed.emit(self._sort_reverse)

    def sync_update_page(self, page: int):
        self._jump_to_page(page, emit_signal=False)

    def sync_update_page_size(self, text: str):
        if hasattr(self, "page_combo") and self.page_combo.currentText() != text:
            self.page_combo.blockSignals(True)
            self.page_combo.setCurrentText(text)
            self.page_combo.blockSignals(False)
            self._on_page_size_changed(text, emit_signal=False)

    def sync_update_thumb_size(self, value: int):
        if hasattr(self, "thumb_slider") and self.thumb_slider.value() != value:
            self.thumb_slider.blockSignals(True)
            self.thumb_slider.setValue(value)
            self.thumb_slider.blockSignals(False)
            self._on_thumb_slider_changed(value, emit_signal=False)

    def sync_update_sort_combo(self, label: str):
        if hasattr(self, "sort_combo") and self.sort_combo.currentText() != label:
            self.sort_combo.blockSignals(True)
            self.sort_combo.setCurrentText(label)
            self.sort_combo.blockSignals(False)
            self._on_sort_combo_changed(label, emit_signal=False)

    def sync_update_sort_dir(self, reverse: bool):
        if self._sort_reverse != reverse and hasattr(self, "sort_dir_btn"):
            self._on_sort_dir_toggled(self.sort_dir_btn, emit_signal=False)
