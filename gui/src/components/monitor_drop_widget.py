import os

from typing import Optional
from screeninfo import Monitor
from PySide6.QtCore import Qt, Signal, QMimeData, QTimer
from PySide6.QtGui import (
    QPixmap,
    QDragEnterEvent,
    QDropEvent,
    QDragMoveEvent,
    QDragLeaveEvent,
    QMouseEvent,
    QDrag,
    QResizeEvent,
)
from PySide6.QtWidgets import QLabel, QMenu, QApplication
from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS


class MonitorDropWidget(QLabel):
    """
    A custom QLabel that acts as a drop target for images,
    displays monitor info, and shows a preview of the dropped image.
    """

    # Emits (monitor_id, [image_paths]) when images are successfully dropped
    images_dropped = Signal(str, list)

    # Emits monitor_id when the widget is double-clicked
    double_clicked = Signal(str)

    # Emits monitor_id when the 'Clear Monitor' right-click action is selected
    clear_requested_id = Signal(str)

    # Emits (source_id, target_id) when a 'Swap Wallpapers' target is selected
    swap_requested_id = Signal(str, str)

    # Emits (source_id, target_id) when a 'Swap Wallpaper Graph' target is selected
    swap_graph_requested_id = Signal(str, str)

    # Emits (monitor_id, menu) to allow parent to add dynamic items
    context_menu_requested = Signal(str, QMenu)

    # Emits monitor_id when the widget is clicked
    clicked = Signal(str)

    def __init__(self, monitor: Monitor, monitor_id: str, hardware_name: Optional[str] = None):
        super().__init__()
        self.monitor = monitor
        self.monitor_id = monitor_id
        self.hardware_name = hardware_name
        self.image_path: Optional[str] = None
        self.drag_start_position = None
        self.other_monitors: list[tuple[str, str]] = []  # Added for multi-monitor swap

        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._handle_single_click)

        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)

        # Dynamic size based on display orientation (landscape vs portrait)
        width, height = self.get_resolved_dimensions()
        if height > width:
            self.setFixedSize(160, 220)
        else:
            self.setFixedSize(220, 160)

        # Setup child labels for top monitor port and bottom real full name
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.top_label = QLabel(self)
        self.top_label.setAlignment(Qt.AlignCenter)
        self.top_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                background-color: rgba(44, 62, 80, 200);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)

        self.bottom_label = QLabel(self)
        self.bottom_label.setAlignment(Qt.AlignCenter)
        self.bottom_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 10px;
                background-color: rgba(44, 62, 80, 200);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)

        layout.addWidget(self.top_label, 0, Qt.AlignTop)
        layout.addStretch(1)
        layout.addWidget(self.bottom_label, 0, Qt.AlignBottom)

        self.update_text()
        self.default_style = """
            QLabel {
                background-color: #36393f;
                border: 2px dashed #4f545c;
                border-radius: 8px;
                color: #b9bbbe;
                font-size: 14px;
            }
            QLabel[dragging="true"] {
                border: 2px solid #5865f2;
                background-color: #40444b;
            }
        """
        self.setStyleSheet(self.default_style)

    def text(self) -> str:
        # Support QTest/Pytest assertions by providing combined text representation
        top_txt = self.top_label.text() if hasattr(self, "top_label") else ""
        return f"{top_txt} {super().text()}"

    def get_real_monitor_name(self) -> Optional[str]:
        import platform
        if platform.system() != "Linux":
            return None
            
        import glob
        import re
        port_name = self.monitor.name
        if not isinstance(port_name, str) or not port_name:
            return None

        def parse_edid(edid_bytes):
            if not edid_bytes or len(edid_bytes) < 128:
                return None
            if edid_bytes[:8] != b'\x00\xff\xff\xff\xff\xff\xff\x00':
                return None
            mfg_id_val = int.from_bytes(edid_bytes[8:10], byteorder='big')
            char1 = chr(((mfg_id_val >> 10) & 0x1F) + 64)
            char2 = chr(((mfg_id_val >> 5) & 0x1F) + 64)
            char3 = chr((mfg_id_val & 0x1F) + 64)
            mfg = f'{char1}{char2}{char3}'
            
            monitor_name = None
            for offset in (54, 72, 90, 108):
                desc = edid_bytes[offset:offset+18]
                if desc[0:2] == b'\x00\x00' and desc[2] == 0x00 and desc[3] == 0xfc:
                    name_bytes = desc[5:]
                    name_len = 0
                    for b in name_bytes:
                        if b in (0x0a, 0x00):
                            break
                        name_len += 1
                    monitor_name = name_bytes[:name_len].decode('ascii', errors='ignore').strip()
                    break
                    
            if monitor_name:
                mfg_map = {
                    'LGD': 'LG Electronics',
                    'GSM': 'LG Electronics',
                    'SAM': 'Samsung',
                    'SEC': 'Samsung',
                    'DEL': 'Dell',
                    'ACR': 'Acer',
                    'BEN': 'BenQ',
                    'AOC': 'AOC',
                    'HPQ': 'HP',
                    'HWP': 'HP',
                    'LEN': 'Lenovo',
                    'PHL': 'Philips',
                    'SNY': 'Sony',
                    'APP': 'Apple',
                    'ASU': 'ASUS',
                    'MSI': 'MSI',
                }
                mfg_full = mfg_map.get(mfg, mfg)
                return f'{mfg_full} {monitor_name}'
            return None

        # Try exact match first
        matches = glob.glob(f'/sys/class/drm/*-{port_name}')
        if matches:
            edid_path = os.path.join(matches[0], 'edid')
            if os.path.exists(edid_path):
                try:
                    with open(edid_path, 'rb') as f:
                        edid = f.read()
                    parsed = parse_edid(edid)
                    if parsed:
                        return parsed
                except Exception:
                    pass

        # Try normalized matching (e.g. HDMI-1 -> HDMI-A-1)
        m = re.match(r'([a-zA-Z]+)-?(\d+)', port_name)
        if m:
            prefix, num = m.groups()
            for p in glob.glob('/sys/class/drm/*'):
                dir_name = os.path.basename(p)
                if prefix.lower() in dir_name.lower() and (dir_name.endswith(f'-{num}') or dir_name.endswith(f'-A-{num}')):
                    edid_path = os.path.join(p, 'edid')
                    if os.path.exists(edid_path):
                        try:
                            with open(edid_path, 'rb') as f:
                                edid = f.read()
                            parsed = parse_edid(edid)
                            if parsed:
                                return parsed
                        except Exception:
                            pass
        return None

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

    def _handle_single_click(self):
        self.clicked.emit(self.monitor_id)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._click_timer.stop()
            self.double_clicked.emit(self.monitor_id)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            self._click_timer.start(QApplication.doubleClickInterval())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not self.drag_start_position:
            return
        if (
            event.pos() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        self._click_timer.stop()
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.monitor_id)
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap.scaledToWidth(200, Qt.SmoothTransformation))
        drag.setHotSpot(event.pos())
        drag.exec(Qt.MoveAction)

    def get_resolved_dimensions(self) -> tuple[int, int]:
        # Try to resolve physical screen size from EDID (highest accuracy)
        edid_res = self.get_real_monitor_resolution()
        if edid_res:
            h_active, v_active = edid_res
            active_is_portrait = False
            # Check Qt screens for rotation
            if self.monitor.name:
                for s in QApplication.screens():
                    if s.name() == self.monitor.name:
                        if s.size().width() < s.size().height():
                            active_is_portrait = True
                        break
            # Fallback to monitor object for rotation
            if not active_is_portrait:
                w = getattr(self.monitor, "width", None)
                h = getattr(self.monitor, "height", None)
                if w and h and w < h:
                    active_is_portrait = True
            
            # Align parsed native resolution with current active orientation
            if active_is_portrait and h_active > v_active:
                width, height = v_active, h_active
            elif not active_is_portrait and h_active < v_active:
                width, height = v_active, h_active
            else:
                width, height = h_active, v_active
        else:
            # Fallback to logical size from Qt screen if active, otherwise screeninfo
            width = getattr(self.monitor, "width", None)
            height = getattr(self.monitor, "height", None)
            if self.monitor.name:
                for s in QApplication.screens():
                    if s.name() == self.monitor.name:
                        width = s.size().width()
                        height = s.size().height()
                        break
        # Ensure we don't return MagicMocks in test environments
        if width is not None and not isinstance(width, (int, float)):
            width = None
        if height is not None and not isinstance(height, (int, float)):
            height = None
        return width or 1920, height or 1080

    def update_text(self):
        monitor_name = f"Monitor {self.monitor_id}"
        if self.monitor.name:
            monitor_name = f"{monitor_name} ({self.monitor.name})"
        
        self.top_label.setText(monitor_name)
        
        if self.hardware_name:
            real_name = self.hardware_name
        else:
            real_name = self.get_real_monitor_name()
            
        if not real_name:
            real_name = "Generic Display"
            
        width, height = self.get_resolved_dimensions()
        if width and height:
            real_name = f"{real_name} ({width}x{height})"
            
        self.bottom_label.setText(real_name)
        
        # Center text inside the main label
        self.setText("\n\nDrag and Drop Image Here")

    def set_hardware_name(self, name: str):
        self.hardware_name = name
        self.update_text()

    def get_real_monitor_resolution(self) -> Optional[tuple[int, int]]:
        import platform
        if platform.system() != "Linux":
            return None
            
        import glob
        import re
        port_name = self.monitor.name
        if not isinstance(port_name, str) or not port_name:
            return None

        def parse_resolution(edid_bytes):
            if not edid_bytes or len(edid_bytes) < 128:
                return None
            # Check timing descriptor at offset 54 (Preferred Timing Mode)
            block = edid_bytes[54:72]
            if block[0:2] != b'\x00\x00':  # Pixel clock is non-zero
                h_active = ((block[4] & 0xf0) << 4) | block[2]
                v_active = ((block[7] & 0xf0) << 4) | block[5]
                if h_active > 0 and v_active > 0:
                    return h_active, v_active
            return None

        # Helper to read from path
        def read_resolution(p):
            edid_path = os.path.join(p, 'edid')
            if os.path.exists(edid_path):
                try:
                    with open(edid_path, 'rb') as f:
                        edid = f.read()
                    return parse_resolution(edid)
                except Exception:
                    pass
            return None

        # Try exact match first
        matches = glob.glob(f'/sys/class/drm/*-{port_name}')
        if matches:
            res = read_resolution(matches[0])
            if res:
                return res

        # Try normalized matching
        m = re.match(r'([a-zA-Z]+)-?(\d+)', port_name)
        if m:
            prefix, num = m.groups()
            for p in glob.glob('/sys/class/drm/*'):
                dir_name = os.path.basename(p)
                if prefix.lower() in dir_name.lower() and (dir_name.endswith(f'-{num}') or dir_name.endswith(f'-A-{num}')):
                    res = read_resolution(p)
                    if res:
                        return res
        return None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.ignore()
            return
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.ignore()
            return
        if self.has_valid_image_url(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.setProperty("dragging", False)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("dragging", False)
        self.style().polish(self)
        if self.has_valid_image_url(event.mimeData()):
            urls = event.mimeData().urls()
            valid_paths = []
            for url in urls:
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    valid_paths.append(file_path)

            if valid_paths:
                self.images_dropped.emit(self.monitor_id, valid_paths)
                event.acceptProposedAction()
                return
        event.ignore()

    def has_valid_image_url(self, mime_data: QMimeData) -> bool:
        if not mime_data.hasUrls():
            return False
        url = mime_data.urls()[0]
        if not url.isLocalFile():
            return False
        file_path = url.toLocalFile().lower()
        valid_exts = set(SUPPORTED_IMG_FORMATS).union(SUPPORTED_VIDEO_FORMATS)
        _, ext = os.path.splitext(file_path)
        ext_no_dot = ext.lstrip(".")
        if ext_no_dot in valid_exts or ext in valid_exts:
            return True
        return False

    def handle_custom_drop(self, file_paths: list[str]):
        """
        Handle a drop from the custom drag system.
        Called directly by DraggableLabel when dropped on this widget.
        """
        valid_paths = []
        for file_path in file_paths:
            if os.path.isfile(file_path):
                # Validate file type
                file_path_lower = file_path.lower()
                valid_exts = set(SUPPORTED_IMG_FORMATS).union(SUPPORTED_VIDEO_FORMATS)
                _, ext = os.path.splitext(file_path_lower)
                ext_no_dot = ext.lstrip(".")

                if ext_no_dot in valid_exts or ext in valid_exts:
                    valid_paths.append(file_path)

        if valid_paths:
            self.images_dropped.emit(self.monitor_id, valid_paths)

    def set_image(self, file_path: Optional[str], thumbnail: Optional[QPixmap] = None):
        """
        Sets the widget's pixmap.
        Prioritizes the provided 'thumbnail' QPixmap if available (useful for videos).
        """
        self.image_path = file_path

        if not file_path:
            self.clear()
            return

        is_video = file_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        # 1. Determine the source pixmap
        source_pixmap = None

        if thumbnail and not thumbnail.isNull():
            # Source 1: Provided thumbnail (Async result or cache hit)
            source_pixmap = thumbnail
        else:
            # Source 2: Try to load from file (Only useful for non-video files)
            if not is_video:
                # Use QImageReader logic or simple QPixmap but check file existence first
                if os.path.exists(file_path):
                    temp_pixmap = QPixmap(file_path)
                    if not temp_pixmap.isNull():
                        source_pixmap = temp_pixmap

        # 2. Update internal state and display
        if source_pixmap and not source_pixmap.isNull():
            # Success: Store original pixmap and scale it for display
            self._current_pixmap = source_pixmap
            scaled_pixmap = source_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

            self.setPixmap(scaled_pixmap)
            self.setText(
                ""
            )  # <--- CRITICAL: Clears any previous text, including "Loading..."

            # Apply border style
            if self.property("selected"):
                self.setStyleSheet("""
                    QLabel {
                        background-color: #2d5a3d;
                        border: 3px solid #2ecc71;
                        border-radius: 8px;
                        color: white;
                    }
                """)
            elif is_video:
                self.setStyleSheet(
                    """
                    QLabel { 
                        background-color: #36393f; 
                        border: 2px solid #3498db; 
                        border-radius: 8px;
                    }
                """
                )
            else:
                self.setStyleSheet(self.default_style)
            return

        # 3. Fallback (No thumbnail/image found)
        self._current_pixmap = None
        self.setPixmap(QPixmap())

        if self.property("selected"):
            self.setStyleSheet("""
                QLabel {
                    background-color: #2d5a3d;
                    border: 3px solid #2ecc71;
                    border-radius: 8px;
                    color: white;
                }
            """)
        elif is_video:
            # Video Fallback (If thumbnail is None, or generation failed)
            filename = os.path.basename(file_path)
            self.setText(f"\n\n🎥 VIDEO SET:\n{filename}")
            self.setStyleSheet(
                """
                QLabel { 
                    background-color: #2c3e50; 
                    border: 2px solid #3498db; 
                    color: #ecf0f1; 
                    font-size: 13px; 
                    border-radius: 8px;
                }
            """
            )
        else:
            # Error State or Default Drag and Drop text
            self.image_path = None
            self.update_text()  # Sets the default "Drag and Drop Image Here" text
            self.setStyleSheet(self.default_style)

    def clear(self):
        self.image_path = None
        self._current_pixmap = None  # Clear cached pixmap
        self.setPixmap(QPixmap())
        self.update_text()
        if self.property("selected"):
            self.setStyleSheet("""
                QLabel {
                    background-color: #2d5a3d;
                    border: 3px solid #2ecc71;
                    border-radius: 8px;
                    color: white;
                }
            """)
        else:
            self.setStyleSheet(self.default_style)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        if selected:
            self.setStyleSheet("""
                QLabel {
                    background-color: #2d5a3d;
                    border: 3px solid #2ecc71;
                    border-radius: 8px;
                    color: white;
                }
            """)
        else:
            # Restore standard style based on whether it has image/video
            if self.image_path:
                is_video = self.image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
                if is_video:
                    self.setStyleSheet("""
                        QLabel { 
                            background-color: #36393f; 
                            border: 2px solid #3498db; 
                            border-radius: 8px;
                        }
                    """)
                else:
                    self.setStyleSheet(self.default_style)
            else:
                self.setStyleSheet(self.default_style)
        self.style().polish(self)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

        # --- CRITICAL FIX: Rescale internal pixmap without reloading ---
        if self._current_pixmap and not self._current_pixmap.isNull():
            scaled_pixmap = self._current_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        # --- END CRITICAL FIX ---
