import os
import platform
import subprocess
import os
from pathlib import Path

# --- External Libs ---
from PIL import Image
from typing import Dict, List
from screeninfo import get_monitors, Monitor

# --- PySide6 Imports ---
from PySide6.QtCore import (
    Qt, QThreadPool, QThread, QMimeData, QUrl
)
from PySide6.QtGui import QPixmap, QDrag
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QWidget, QLabel, QPushButton, QMessageBox, QApplication,
    QLineEdit, QFileDialog, QScrollArea, QGridLayout
)

# --- Project Imports ---
from .base_tab import BaseTab
from ..components import MonitorDropWidget
from ..styles import apply_shadow_effect
# Import workers from the same location as ScanFSETab
try:
    from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
except ImportError:
    print("WARNING: Could not import workers. Scanning in WallpaperTab will not work.")
    ImageScannerWorker, BatchThumbnailLoaderWorker = None, None


# --- NEW: Draggable Thumbnail Label ---
class DraggableImageLabel(QLabel):
    """
    A simple QLabel that displays a thumbnail and can be dragged.
    The drag operation carries the file path.
    """
    def __init__(self, path: str, size: int):
        super().__init__()
        self.file_path = path
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Loading...")
        self.setStyleSheet("border: 1px dashed #4f545c; color: #b9bbbe;")

    def mouseMoveEvent(self, event):
        """Initiates a drag-and-drop operation."""
        if not self.file_path or self.pixmap().isNull():
            return # Don't drag if not a valid image

        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set the file path as a URL
        mime_data.setUrls([QUrl.fromLocalFile(self.file_path)])
        
        drag.setMimeData(mime_data)
        
        # Set a pixmap for the drag preview
        drag.setPixmap(self.pixmap().scaled(
            self.width() // 2, self.height() // 2, 
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
        
        drag.exec(Qt.MoveAction)


# --- Main Tab ---
class WallpaperTab(BaseTab):
    def __init__(self, db_tab_ref, dropdown=True): # Keep signature consistent
        super().__init__()
        # Reference to the main DatabaseTab (in case it's needed later)
        self.db_tab_ref = db_tab_ref
        
        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropWidget] = {}
        self.monitor_image_paths: Dict[str, str] = {}
        
        layout = QVBoxLayout(self)
        
        # --- Monitor Layout Group ---
        layout_group = QGroupBox("Monitor Layout (Drop images here)")
        layout_group.setStyleSheet("""
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
        """)
        
        self.monitor_layout_container = QWidget()
        self.monitor_layout = QHBoxLayout(self.monitor_layout_container)
        self.monitor_layout.setSpacing(15)
        self.monitor_layout.setAlignment(Qt.AlignCenter)
        
        layout_group.setLayout(self.monitor_layout)
        layout.addWidget(layout_group) # Removed stretch factor to balance layout

        # --- NEW: Scan Directory Section (Copied from ScanFSETab) ---
        scan_group = QGroupBox("Scan Directory (Drag images from here)")
        scan_group.setStyleSheet("""
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
        """)
        
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10) 
        
        # Directory path selection
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        
        btn_browse_scan.setStyleSheet("QPushButton { background-color: #4f545c; padding: 6px 12px; } QPushButton:hover { background-color: #5865f2; }")
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # --- NEW: Thumbnail Gallery Scroll Area ---
        self.thumbnail_size = 120
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width

        self.scan_scroll_area = QScrollArea() 
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        
        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        
        layout.addWidget(self.scan_scroll_area, 1) # Give this stretch
        
        # --- Action Buttons (Original) ---
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.refresh_btn = QPushButton("Refresh Layout")
        self.refresh_btn.setStyleSheet("background-color: #f1c40f; color: black; padding: 10px; border-radius: 8px; font-weight: bold;")
        apply_shadow_effect(self.refresh_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.refresh_btn.clicked.connect(self.populate_monitor_layout)
        action_layout.addWidget(self.refresh_btn)
        
        self.set_wallpaper_btn = QPushButton("Set Wallpaper")
        self.set_wallpaper_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 16px;
                padding: 14px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #4f545c; color: #a0a000; }
            QPushButton:pressed { background: #5a67d8; }
        """)
        apply_shadow_effect(self.set_wallpaper_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.set_wallpaper_btn.clicked.connect(self.set_wallpaper)
        action_layout.addWidget(self.set_wallpaper_btn, 1) # Give it stretch
        
        layout.addLayout(action_layout)
        
        self.setLayout(layout)

        # --- NEW: State for scanner ---
        self.threadpool = QThreadPool.globalInstance()
        self.scanned_dir = None
        try:
            # Try to find a sensible default 'data' dir
            base_dir = Path.cwd()
            while base_dir.name != 'Image-Toolkit' and base_dir.parent != base_dir:
                base_dir = base_dir.parent
            if base_dir.name == 'Image-Toolkit':
                self.last_browsed_scan_dir = str(base_dir / 'data')
            else:
                self.last_browsed_scan_dir = str(Path.cwd() / 'data')
        except Exception:
             self.last_browsed_scan_dir = os.getcwd() # Fallback
        
        self.scan_image_list: list[str] = []
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {}
        
        # Initial setup (Original)
        self.populate_monitor_layout()
        self.check_dependencies()
        self.check_all_monitors_set() # Initially disable button

    # --- Original Methods ---
    def check_dependencies(self):
        """Checks for external dependencies and OS support."""
        if platform.system() == "Windows":
            QMessageBox.warning(self, "Unsupported OS",
                                "This wallpaper tab currently only supports Linux with GNOME (gsettings).\n"
                                "Setting wallpaper on Windows requires a different implementation (e.g., using ctypes).")
            self.set_wallpaper_btn.setEnabled(False)
            self.set_wallpaper_btn.setText("Unsupported OS")
        
        elif Image is None:
            QMessageBox.warning(self, "Missing Dependency",
                                "The 'Pillow' (PIL) library is not installed.\n"
                                "Cannot create spanned wallpaper.\n"
                                "Please run: pip install Pillow")
            self.set_wallpaper_btn.setEnabled(False)
            self.set_wallpaper_btn.setText("Missing Pillow")
        
        elif "Mock" in get_monitors()[0].name:
             QMessageBox.warning(self, "Missing Dependency",
                                "The 'screeninfo' library is not installed or failed to load.\n"
                                "Cannot detect monitor layout.\n"
                                "Please run: pip install screeninfo")
             self.set_wallpaper_btn.setEnabled(False)
             self.set_wallpaper_btn.setText("Missing screeninfo")
        
        elif ImageScannerWorker is None:
             QMessageBox.warning(self, "Missing Helpers",
                                "The ImageScannerWorker or BatchThumbnailLoaderWorker could not be imported.\n"
                                "Directory scanning will be disabled.")

    
    def populate_monitor_layout(self):
        """
        Clears and recreates the monitor drop widgets based on
        the current system monitor layout.
        """
        # Clear existing layout
        for i in reversed(range(self.monitor_layout.count())): 
            widget = self.monitor_layout.takeAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.monitor_widgets.clear()
        
        try:
            self.monitors = sorted(get_monitors(), key=lambda m: m.x)
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
             self.monitors = []
             
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout.addWidget(QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?"))
            return

        for i, monitor in enumerate(self.monitors):
            monitor_id = str(i + 1) 
            drop_widget = MonitorDropWidget(monitor, monitor_id)
            drop_widget.image_dropped.connect(self.on_image_dropped)
            
            if monitor_id in self.monitor_image_paths:
                drop_widget.set_image(self.monitor_image_paths[monitor_id])
                
            self.monitor_layout.addWidget(drop_widget)
            self.monitor_widgets[monitor_id] = drop_widget
        
        self.check_all_monitors_set()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        """Slot to store the path of the dropped image."""
        self.monitor_image_paths[monitor_id] = image_path
        self.check_all_monitors_set()
        
    def check_all_monitors_set(self):
        """Enables the 'Set' button only if all monitors have an image."""
        if not self.set_wallpaper_btn.text() in ["Unsupported OS", "Missing Pillow", "Missing screeninfo"]:
            all_set = len(self.monitor_image_paths) == len(self.monitors)
            self.set_wallpaper_btn.setEnabled(all_set)
            
            if all_set:
                self.set_wallpaper_btn.setText("Set Wallpaper")
            else:
                missing = len(self.monitors) - len(self.monitor_image_paths)
                self.set_wallpaper_btn.setText(f"Set Wallpaper ({missing} more)")
            
    def set_wallpaper(self):
        """
        Gathers images, stitches them with Pillow, and uses gsettings
        to apply the spanned wallpaper.
        """
        if len(self.monitor_image_paths) != len(self.monitors):
            QMessageBox.warning(self, "Incomplete", "Please drag an image onto every monitor.")
            return

        self.set_wallpaper_btn.setEnabled(False)
        self.set_wallpaper_btn.setText("Applying...")
        QApplication.processEvents() 
        
        try:
            monitors = self.monitors
            image_paths = [self.monitor_image_paths[str(i+1)] for i in range(len(monitors))]

            images = []
            total_width = 0
            max_height = 0
            
            for i, monitor in enumerate(monitors):
                img = Image.open(image_paths[i])
                img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                images.append(img)
                total_width += monitor.width
                if monitor.height > max_height:
                    max_height = monitor.height

            spanned_image = Image.new('RGB', (total_width, max_height))
            
            current_x = 0
            for img in images:
                spanned_image.paste(img, (current_x, 0))
                current_x += img.width

            home_dir = os.path.expanduser('~')
            save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
            spanned_image.save(save_path, "JPEG", quality=95)
            
            file_uri = f"file://{save_path}"

            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "'spanned'"],
                check=True, capture_output=True, text=True, shell=True 
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
                check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
                check=True, capture_output=True, text=True
            )
            
            QMessageBox.information(self, "Success", "Wallpaper has been updated!")

        except FileNotFoundError:
             QMessageBox.critical(self, "Error", 
                                  "Could not set wallpaper. Is 'gsettings' installed?\n"
                                  "This is required for GNOME desktops.")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", f"Failed to set wallpaper via gsettings:\n{e.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")
        
        finally:
            self.check_all_monitors_set()

    # --- NEW: Methods adapted from ScanFSETab ---
    def browse_scan_directory(self):
        """Select directory to scan and display image thumbnails."""
        if ImageScannerWorker is None:
            self.check_dependencies() # Re-show warning
            return
            
        start_dir = self.last_browsed_scan_dir
        options = QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select directory to scan", 
            start_dir, 
            options
        )
        
        if directory:
            self.last_browsed_scan_dir = directory
            self.scan_directory_path.setText(directory)
            self.populate_scan_image_gallery(directory)

    def populate_scan_image_gallery(self, directory: str):
        """Initiates scanning on a separate thread and sets up the gallery structure."""
        self.scanned_dir = directory
        self.clear_scan_image_gallery()
        
        loading_label = QLabel("Scanning directory, please wait...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(loading_label, 0, 0, 1, 10) 
        
        self.worker = ImageScannerWorker(directory)
        self.thread = QThread() 
        self.worker.moveToThread(self.thread) 
        
        self.thread.started.connect(self.worker.run_scan)
        self.worker.scan_finished.connect(self.display_scan_results)
        self.worker.scan_error.connect(self.handle_scan_error)
        
        self.worker.scan_finished.connect(self.thread.quit)
        self.worker.scan_finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def display_scan_results(self, image_paths: list[str]):
        """
        Receives image paths from the worker thread, creates placeholders, and starts 
        a single BatchThumbnailLoaderWorker to progressively load and display images.
        """
        self.clear_scan_image_gallery() 
        self.scan_image_list = image_paths
        
        columns = self.calculate_columns()
        
        if not self.scan_image_list:
            no_images_label = QLabel("No supported images found.")
            no_images_label.setAlignment(Qt.AlignCenter)
            no_images_label.setStyleSheet("color: #b9bbbe;")
            self.scan_thumbnail_layout.addWidget(no_images_label, 0, 0, 1, columns)
            return
        
        worker = BatchThumbnailLoaderWorker(self.scan_image_list, self.thumbnail_size)
        thread = QThread()

        self.current_thumbnail_loader_worker = worker
        self.current_thumbnail_loader_thread = thread
        
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run_load_batch)
        worker.create_placeholder.connect(self._create_thumbnail_placeholder)
        worker.thumbnail_loaded.connect(self._update_thumbnail_slot)
        
        worker.loading_finished.connect(thread.quit)
        worker.loading_finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._cleanup_thumbnail_thread_ref)
        
        thread.start()

    def _create_thumbnail_placeholder(self, index: int, path: str):
        """
        Slot executed on the main thread to create and add a single placeholder.
        Uses the new DraggableImageLabel.
        """
        columns = self.calculate_columns()
        row = index // columns
        col = index % columns

        # Use the NEW DraggableImageLabel
        draggable_label = DraggableImageLabel(path, self.thumbnail_size) 

        self.scan_thumbnail_layout.addWidget(draggable_label, row, col)
        self.path_to_label_map[path] = draggable_label 
        
        self.scan_thumbnail_widget.update()
        QApplication.processEvents()

    def _update_thumbnail_slot(self, index: int, pixmap: QPixmap, path: str):
        """
        Slot executed on the main thread to update a specific thumbnail widget
        with the loaded image.
        """
        label = self.path_to_label_map.get(path)
        
        if label is None:
            return

        if not pixmap.isNull():
            label.setPixmap(pixmap) 
            label.setText("") 
            label.setStyleSheet("border: 1px solid #4f545c;")
        else:
            label.setText("Load Error")
            label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; font-size: 8px;")

    def _cleanup_thumbnail_thread_ref(self):
        """Slot to clear the QThread and QObject references after the thread finishes its work."""
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None

    def clear_scan_image_gallery(self):
        """Removes all widgets from the scan gallery layout and cleans up the single active thread."""
        
        if self.current_thumbnail_loader_thread and self.current_thumbnail_loader_thread.isRunning():
            self.current_thumbnail_loader_thread.quit()
        
        self.current_thumbnail_loader_thread = None
        self.current_thumbnail_loader_worker = None
        self.path_to_label_map = {} 

        while self.scan_thumbnail_layout.count():
            item = self.scan_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        self.scan_image_list = []

    def handle_scan_error(self, message: str):
        """Handles and displays errors that occurred during the background scan."""
        self.clear_scan_image_gallery() 
        QMessageBox.warning(self, "Error Scanning", message)
        ready_label = QLabel("Browse for a directory.")
        ready_label.setAlignment(Qt.AlignCenter)
        ready_label.setStyleSheet("color: #b9bbbe;")
        self.scan_thumbnail_layout.addWidget(ready_label, 0, 0, 1, 1)

    def calculate_columns(self) -> int:
        """Calculates the maximum number of thumbnail columns that fit in the widget."""
        widget_width = self.scan_thumbnail_widget.width()
        if widget_width <= 0:
            widget_width = self.scan_thumbnail_widget.parentWidget().width()
        
        if widget_width <= 0:
            return 4 
        
        columns = widget_width // self.approx_item_width
        return max(1, columns)

    # --- Original collect() method ---
    def collect(self) -> dict:
        """Collect current state (for consistency with other tabs)."""
        return {
            "monitor_images": self.monitor_image_paths,
            "scan_directory": self.scan_directory_path.text().strip() or None
        }
