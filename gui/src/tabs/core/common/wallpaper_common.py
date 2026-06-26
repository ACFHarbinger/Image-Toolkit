import os
import platform
import subprocess

from typing import Dict, List, Optional, Any, Tuple
from PySide6.QtCore import (
    Qt,
    QThread,
    QTimer,
    Slot,
    QPoint,
    QEvent,
    QRect,
    Signal,
)
from PySide6.QtGui import QPixmap, QImage, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QScrollArea,
    QLabel,
    QApplication,
    QMessageBox,
)
from screeninfo import get_monitors, Monitor

from ....classes import AbstractClassSingleGallery
from ....helpers import ImageScannerWorker, VideoScannerWorker
from ....components import (
    MonitorDropWidget,
    DraggableLabel,
    MarqueeScrollArea,
    DraggableMonitorContainer,
)
from ....utils.sort_utils import natural_sort_key
from backend.src.constants import (
    SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_IMG_FORMATS,
)
from backend.src.core import WallpaperManager
from backend.src.core.wallpaper import find_qdbus_binary


class WallpaperCommonBase(AbstractClassSingleGallery):
    """Shared state and helpers for wallpaper subtabs.

    Holds monitor state, gallery helpers, and scanner methods.
    Subclasses build their own UI layouts using these facilities.
    """

    monitors_updated = Signal(list)      # List[Monitor]
    qml_monitors_changed = Signal(list)  # List of dicts
    qml_status_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.qdbus: Optional[str] = find_qdbus_binary()

        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropWidget] = {}
        self.monitor_image_paths: Dict[str, str] = {}
        self.monitor_slideshow_queues: Dict[str, List[str]] = {}
        self.monitor_current_index: Dict[str, int] = {}
        self.monitor_history: Dict[str, List[str]] = {}

        self.img_scanner_worker: Optional[Any] = None
        self.img_scanner_thread: Optional[QThread] = None
        self.vid_scanner_worker: Optional[VideoScannerWorker] = None

        self.scanned_dir = None
        self.path_to_label_map = {}
        self._filtering_event = False

        self._pagination_debounce_timer = QTimer()
        self._pagination_debounce_timer.setSingleShot(True)
        self._pagination_debounce_timer.setInterval(200)
        self._pagination_debounce_timer.timeout.connect(self._update_pagination_ui)

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
        try:
            system_monitors = get_monitors()
            _ = sorted(system_monitors, key=lambda m: m.x)
            self.monitors = system_monitors
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
            self.monitors = []
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout_container.addWidget(
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
            drop_widget = MonitorDropWidget(monitor, monitor_id)

            real_name = drop_widget.get_real_monitor_name()
            if real_name:
                drop_widget.set_hardware_name(real_name)

            drop_widget.other_monitors = [
                (mid, name) for mid, name in monitor_info_list if mid != monitor_id
            ]

            drop_widget.images_dropped.connect(self.on_images_dropped)
            drop_widget.double_clicked.connect(
                lambda m_id=monitor_id: self.handle_monitor_double_click(m_id)
            )
            drop_widget.clear_requested_id.connect(self.handle_clear_monitor_queue)
            drop_widget.swap_requested_id.connect(self.swap_monitors)
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
                    self.monitor_layout_container.addWidget(
                        monitor_id_to_widget[monitor_id]
                    )

        self.monitors_updated.emit(self.monitors)

    def _get_rotated_map_for_ui(self, raw_paths: Dict[int, str]) -> Dict[str, str]:
        mapped = {}
        for idx, path in raw_paths.items():
            mapped[str(idx)] = path
        return mapped

    def _get_current_system_image_paths_for_all(self) -> Dict[str, Optional[str]]:
        system = platform.system()
        num_monitors = len(self.monitors)
        current_paths = {}
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

    def populate_scan_image_gallery(self, directory: str):
        if self.background_type == "Solid Color":
            return

        self.scanned_dir = directory
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
        if not hasattr(self, "main_scroll_area") or not self.isVisible():
            return

        vbar = self.main_scroll_area.verticalScrollBar()
        if not vbar or not vbar.isVisible():
            return

        viewport = self.main_scroll_area.viewport()
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
                    vbar = self.main_scroll_area.verticalScrollBar()
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

    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        self.handle_full_image_preview(image_path)

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
            self.scan_directory_path.setText(directory)
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
        self.handle_set_wallpaper_click()

    @Slot(int, int, str, bool, bool)
    def update_slideshow_settings_qml(
        self, interval_min, style, random_order, include_subdirs
    ):
        self.interval_min_spinbox.setValue(interval_min)
        self.style_combo.setCurrentText(style)
        self.request_monitors_qml()

    @Slot(str)
    def drop_image_qml(self, path):
        self.set_wallpaper_qml(path, "All")
