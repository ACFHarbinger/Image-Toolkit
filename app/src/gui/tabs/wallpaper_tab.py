import os
import ctypes
import winreg
import platform
import subprocess

from PIL import Image
from pathlib import Path
from typing import Dict, List
from screeninfo import get_monitors, Monitor
from PySide6.QtCore import Qt, QThreadPool, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QWidget, QLabel, QPushButton, QMessageBox, QApplication,
    QLineEdit, QFileDialog, QScrollArea, QGridLayout
)
from .base_tab import BaseTab
from ..components import MonitorDropWidget, DraggableImageLabel
from ..helpers import ImageScannerWorker, BatchThumbnailLoaderWorker
from ..utils.styles import apply_shadow_effect


class WallpaperTab(BaseTab):
    def __init__(self, db_tab_ref, dropdown=True): # Keep signature consistent
        super().__init__()
        # Reference to the main DatabaseTab (in case it's needed later)
        self.db_tab_ref = db_tab_ref
        
        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropWidget] = {}
        # Stores image path for the monitor ID (1-based index)
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

    # --- check_dependencies Method (Unchanged) ---
    def check_dependencies(self):
        """Checks for external dependencies and OS support."""
        
        if Image is None:
            QMessageBox.warning(self, "Missing Dependency",
                                "The 'Pillow' (PIL) library is not installed.\n"
                                "Cannot load or resize images.\n"
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
             
        # Enable the button if all checks passed
        if not self.set_wallpaper_btn.text() in ["Missing Pillow", "Missing screeninfo", "Missing Helpers"]:
             self.set_wallpaper_btn.setText("Set Wallpaper")
             self.set_wallpaper_btn.setEnabled(True) 

    
    # --- REVISED populate_monitor_layout Method ---
    def populate_monitor_layout(self):
        """
        Clears and recreates the monitor drop widgets based on
        the current system monitor layout, showing only one for Windows.
        """
        # Clear existing layout
        for i in reversed(range(self.monitor_layout.count())): 
            widget = self.monitor_layout.takeAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.monitor_widgets.clear()
        
        try:
            # Sort by x-position to match left-to-right visual order
            self.monitors = sorted(get_monitors(), key=lambda m: m.x) 
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
             self.monitors = []
             
        if not self.monitors or "Mock" in self.monitors[0].name:
            self.monitor_layout.addWidget(QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?"))
            return

        monitors_to_show = self.monitors

        # CHECK 1: If Windows, only show the first monitor
        if platform.system() == "Windows":
             monitors_to_show = [self.monitors[0]]
             # Show a message to explain the limitation
             label = QLabel("Windows only supports one wallpaper across all screens.")
             label.setStyleSheet("color: #7289da;")
             self.monitor_layout.addWidget(label)


        for i, monitor in enumerate(monitors_to_show):
            # Monitor ID is 1-based index based on the sorted list
            # Note: On Windows, i will always be 0, monitor_id will be '1'
            monitor_index_in_original_list = self.monitors.index(monitor)
            monitor_id = str(monitor_index_in_original_list + 1) 

            drop_widget = MonitorDropWidget(monitor, monitor_id)
            drop_widget.image_dropped.connect(self.on_image_dropped)
            
            # Restore image path if available
            if monitor_id in self.monitor_image_paths:
                drop_widget.set_image(self.monitor_image_paths[monitor_id])
                
            self.monitor_layout.addWidget(drop_widget)
            self.monitor_widgets[monitor_id] = drop_widget
        
        self.check_all_monitors_set()

    def on_image_dropped(self, monitor_id: str, image_path: str):
        """Slot to store the path of the dropped image."""
        self.monitor_image_paths[monitor_id] = image_path
        self.check_all_monitors_set()
        
    # --- REVISED check_all_monitors_set Method ---
    def check_all_monitors_set(self):
        """Enables the 'Set' button only if all *visible* monitors have an image."""
        if not self.set_wallpaper_btn.text() in ["Missing Pillow", "Missing screeninfo", "Missing Helpers"]:
            
            # Use the number of currently visible widgets to determine the target count
            target_monitor_ids = set(self.monitor_widgets.keys())
            
            # Check how many of the required monitors have paths
            set_count = 0
            for monitor_id in target_monitor_ids:
                if monitor_id in self.monitor_image_paths and self.monitor_image_paths[monitor_id]:
                    set_count += 1

            all_set = set_count == len(target_monitor_ids)
            self.set_wallpaper_btn.setEnabled(all_set)
            
            if all_set:
                self.set_wallpaper_btn.setText("Set Wallpaper")
            else:
                missing = len(target_monitor_ids) - set_count
                self.set_wallpaper_btn.setText(f"Set Wallpaper ({missing} more)")

    def set_wallpaper(self):
        """
        Applies a single image to all monitors on Windows (using Monitor 1's image), 
        or attempts per-monitor application on Linux (KDE).
        """
        # Determine the number of targets based on visible widgets
        # We check the keys of monitor_widgets, which accurately reflect the visible monitors
        target_monitor_ids = list(self.monitor_widgets.keys()) 
        set_count = 0
        for monitor_id in target_monitor_ids:
            if monitor_id in self.monitor_image_paths and self.monitor_image_paths[monitor_id]:
                set_count += 1
        
        if set_count != len(target_monitor_ids):
            QMessageBox.warning(self, "Incomplete", f"Please drag an image onto every visible monitor ({len(target_monitor_ids)} needed).")
            return

        self.set_wallpaper_btn.setEnabled(False)
        self.set_wallpaper_btn.setText("Applying...")
        QApplication.processEvents() 
        
        # FIX: Prepare the list of image paths only for the required monitors
        if platform.system() == "Windows":
             # On Windows, only Monitor 1 is needed (key '1')
             # We assume '1' is always in target_monitor_ids if set_count passed
             required_image_paths = [self.monitor_image_paths['1']]
        else:
             # On Linux, all detected monitors are targets
             required_image_paths = [self.monitor_image_paths[str(i+1)] for i in range(len(self.monitors))]
        
        try:
            if platform.system() == "Windows":
                # --- Windows Implementation (Single Wallpaper enforced) ---
                
                # Use the single image path (which is Monitor 1's)
                single_image_path = required_image_paths[0] 
                
                # Ensure the path is fully resolved and converted to a string suitable for ctypes
                save_path = str(Path(single_image_path).resolve())

                QMessageBox.information(self, "Windows Note",
                    "Windows only supports a single wallpaper file via this tool.\n"
                    f"Applying the image assigned to Monitor 1: {Path(save_path).name}"
                )
                
                # Set Windows Registry Keys to use 'Fill' or 'Stretch' for better scaling
                # 0=Tile, 1=Center, 2=Stretch, 3=Fit, 4=Fill, 5=Span
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                     "Control Panel\\Desktop", 0, winreg.KEY_SET_VALUE)
                # Set to Fill (4) and Tile off (0) for a standard modern look
                winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "4") 
                winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0") 
                winreg.CloseKey(key)

                # Constants for SystemParametersInfoW
                SPI_SETDESKWALLPAPER = 20
                SPIF_UPDATEINIFILE = 0x01
                SPIF_SENDWININICHANGE = 0x02
                
                # Apply the single image
                ctypes.windll.user32.SystemParametersInfoW(
                    SPI_SETDESKWALLPAPER, 
                    0, 
                    save_path, 
                    SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
                )
                
            elif platform.system() == "Linux":
                
                # --- Linux (KDE) Implementation (Per-Monitor) ---
                try:
                    # Check if 'qdbus' is available, which is the KDE way
                    subprocess.run(["which", "qdbus6"], check=True, capture_output=True)
                    
                    # KDE Plasma per-monitor application using DBus script
                    for i, path in enumerate(required_image_paths):
                        
                        file_uri = f"file://{Path(path).resolve()}"
                        
                        # Apply to the i-th desktop/monitor in KDE's list
                        qdbus_command = (
                            f"qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript \"desktops()[{i}].currentConfigGroup = Array(\"Wallpaper\", \"org.kde.image\", \"General\"); desktops()[{i}].writeConfig(\"Image\", \"{file_uri}\"); desktops()[{i}].writeConfig(\"FillMode\", 1); desktops()[{i}].reloadConfig();\""
                        )
                        subprocess.run(qdbus_command, shell=True, check=True, capture_output=True)
                        
                    
                except FileNotFoundError:
                    # --- Linux (GNOME/Other) Fallback (Reverting to Spanned) ---
                    QMessageBox.warning(self, "Linux Note", 
                                        "KDE Plasma ('qdbus6') not detected. Falling back to GNOME 'spanned' method.\n"
                                        "This will stitch all images into a single file and apply it across all monitors.")
                    
                    # Stitching logic for GNOME spanning (needed because GNOME lacks a simple per-monitor API)
                    total_width = sum(m.width for m in self.monitors)
                    max_height = max(m.height for m in self.monitors)
                    spanned_image = Image.new('RGB', (total_width, max_height))
                    
                    current_x = 0
                    for i, monitor in enumerate(self.monitors):
                        img = Image.open(required_image_paths[i]) # Use required_image_paths here
                        img = img.resize((monitor.width, monitor.height), Image.Resampling.LANCZOS)
                        spanned_image.paste(img, (current_x, 0))
                        current_x += img.width

                    home_dir = os.path.expanduser('~')
                    save_path = os.path.join(home_dir, ".spanned_wallpaper.jpg")
                    spanned_image.save(save_path, "JPEG", quality=95)
                    file_uri = f"file://{save_path}"

                    # GNOME/gsettings
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "spanned"],
                        check=True, capture_output=True, text=True
                    )
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
                        check=True, capture_output=True, text=True
                    )
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
                        check=True, capture_output=True, text=True
                    )
                except subprocess.CalledProcessError as e:
                    # Handle Linux errors
                    QMessageBox.critical(self, "Error", 
                                         f"Failed to set wallpaper on Linux.\nError: {e.stderr}")
                    raise
                
            else:
                 QMessageBox.warning(self, "Unsupported OS", 
                                  f"Wallpaper setting for {platform.system()} is not supported.")
                 return

            QMessageBox.information(self, "Success", "Wallpaper has been updated!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")
        
        finally:
            self.check_all_monitors_set()

    # --- Other Methods (Unchanged) ---
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
