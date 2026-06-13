import os
import sys

from PySide6.QtCore import Qt, QSize, QSettings, QTimer
from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import (
    QSizePolicy,
    QPushButton,
    QStyle,
    QComboBox,
    QLabel,
    QWidget,
    QTabWidget,
    QScrollArea,
    QVBoxLayout,
    QHBoxLayout,
    QApplication,
    QMessageBox,
    QStatusBar,
    QSystemTrayIcon,
    QMenu,
)
from .settings_window import SettingsWindow
from ..styles.style import (
    DARK_QSS,
    LIGHT_QSS,
    DARK_ACCENT_COLOR,
    LIGHT_ACCENT_COLOR,
    load_qss_with_overrides,
    load_user_qss_override,
    compute_accent_vars,
    COMPACT_DENSITY_QSS,
    SPACIOUS_DENSITY_QSS,
)
from ..constants import NEW_LIMIT_MB
from ..utils.lru_image_cache import LRUImageCache
from backend.src.core.vault_manager import VaultManager


def show_tray_notification(title: str, message: str, timeout_ms: int = 4000) -> None:
    """Post a tray balloon notification from anywhere in the app (§2.12B)."""
    for w in QApplication.topLevelWidgets():
        if hasattr(w, "tray_notify"):
            w.tray_notify(title, message, timeout_ms)
            return


def show_main_status(message: str, timeout_ms: int = 3000) -> None:
    """Post *message* to the MainWindow status bar from anywhere in the app (§2.10C).

    Finds the first MainWindow in QApplication.topLevelWidgets(); silently
    does nothing when called before the window exists (e.g. during tests).
    """
    for w in QApplication.topLevelWidgets():
        if hasattr(w, "show_status"):
            w.show_status(message, timeout_ms)
            return


class MainWindow(QWidget):
    def __init__(
        self,
        vault_manager: VaultManager,
        dropdown=True,
        app_icon=None,
        enable_manager=False,
    ):
        super().__init__()
        from ..tabs import (
            ConvertTab,
            DeleteTab,
            ScanMetadataTab,
            SearchTab,
            ImageExtractorTab,
            ListingsTab,
            MergeTab,
            StitchFeedbackTab,
            ImageCrawlTab,
            DriveSyncTab,
            WallpaperTab,
            WebRequestsTab,
            DatabaseTab,
            ReverseImageSearchTab,
            UnifiedTrainTab,
            UnifiedGenerateTab,
            R3GANEvaluateTab,
            MetaCLIPInferenceTab,
            ComfyUITab,
            EditTab,
        )

        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        self.enable_manager = enable_manager

        self.setWindowTitle("Image Database and Edit Toolkit")
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)

        # --- LOAD THEME AND ACCOUNT INFO FROM VAULT (LOAD 1 OF 1) ---
        account_name = "Authenticated User"
        initial_theme = "dark"

        # Load credentials once to get theme and account name
        self.cached_creds = {}

        if self.vault_manager:
            try:
                self.cached_creds = self.vault_manager.load_account_credentials()
                account_name = self.cached_creds.get(
                    "account_name", "Authenticated User"
                )
                initial_theme = self.cached_creds.get("theme", "dark")
            except Exception as e:
                print(f"Warning: Failed to load account credentials or theme: {e}")

        # GUI/UX §2.8 — Option C: follow OS color scheme when no vault preference is stored.
        # cached_creds may be empty on first launch; fall back to OS preference in that case.
        if not self.cached_creds.get("theme"):
            try:
                from PySide6.QtCore import Qt as _Qt
                from PySide6.QtGui import QGuiApplication as _QGA
                os_scheme = _QGA.styleHints().colorScheme()
                if os_scheme == _Qt.ColorScheme.Light:
                    initial_theme = "light"
                else:
                    initial_theme = "dark"
            except Exception:
                pass

        self.current_theme = initial_theme

        vbox = QVBoxLayout()
        self.settings_window = None

        # --- Application Header ---
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet(
            "background-color: #2d2d30; padding: 10px; border-bottom: 2px solid #00bcd4;"
        )
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)

        self.title_label = QLabel(f"Image Database and Toolkit - {account_name}")
        self.title_label.setStyleSheet(
            "color: white; font-size: 18pt; font-weight: bold;"
        )
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        # --- Settings button ---
        self.settings_button = QPushButton()
        if app_icon and os.path.exists(app_icon):
            settings_icon = QIcon(app_icon)
            self.settings_button.setIcon(settings_icon)
        else:
            settings_icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton
            )
            self.settings_button.setIcon(settings_icon)

        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setFixedSize(QSize(36, 36))
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setToolTip("Open Settings")
        self.settings_button.setDefault(True)

        self.settings_button.setStyleSheet(
            """
            QPushButton#settings_button {
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 18px; 
            }
        """
        )
        header_layout.addWidget(self.settings_button)

        vbox.addWidget(header_widget)

        # --- Tab Initialization ---
        self.database_tab = DatabaseTab()
        self.search_tab = SearchTab(self.database_tab, dropdown=dropdown)
        self.scan_metadata_tab = ScanMetadataTab(self.database_tab)
        self.convert_tab = ConvertTab(dropdown=dropdown)
        self.merge_tab = MergeTab()
        self.delete_tab = DeleteTab(dropdown=dropdown)
        self.crawler_tab = ImageCrawlTab()
        self.reverse_search_tab = ReverseImageSearchTab()
        self.drive_sync_tab = DriveSyncTab(vault_manager)
        self.wallpaper_tab = WallpaperTab(self.database_tab)
        self.web_requests_tab = WebRequestsTab()
        self.image_extractor_tab = ImageExtractorTab()
        self.listings_tab = ListingsTab(vault_manager=vault_manager)
        self.train_tab = UnifiedTrainTab()
        self.generate_tab = UnifiedGenerateTab()
        self.eval_tab = R3GANEvaluateTab()
        self.inference_tab = MetaCLIPInferenceTab()
        self.comfyui_tab = ComfyUITab(enable_manager=enable_manager)
        self.stitch_tab = EditTab()
        self.stitch_feedback_tab = StitchFeedbackTab()

        # --- LINK TABS (Critical for Cross-Tab Communication) ---
        self.database_tab.scan_tab_ref = self.scan_metadata_tab
        self.database_tab.search_tab_ref = self.search_tab
        self.database_tab.merge_tab_ref = self.merge_tab
        self.database_tab.delete_tab_ref = self.delete_tab
        self.database_tab.wallpaper_tab_ref = self.wallpaper_tab

        self.all_tabs = {
            "System Tools": {
                "Convert": self.convert_tab,
                "Merge": self.merge_tab,
                "Delete": self.delete_tab,
                "Extractor": self.image_extractor_tab,
                "Display Wallpaper": self.wallpaper_tab,
                "Listings": self.listings_tab,
            },
            "Database Management": {
                "Database Configuration": self.database_tab,
                "Search Images": self.search_tab,
                "Scan Metadata": self.scan_metadata_tab,
            },
            "Web Integration": {
                "Web Crawler": self.crawler_tab,
                "Web Requests": self.web_requests_tab,
                "Cloud Synchronization": self.drive_sync_tab,
                "Reverse Search": self.reverse_search_tab,
            },
            "Deep Learning": {
                "Training": self.train_tab,
                "Generation": self.generate_tab,
                "Evaluation": self.eval_tab,
                "Inference": self.inference_tab,
                "ComfyUI": self.comfyui_tab,
            },
            "Image Edit": {
                "Stitch": self.stitch_tab.stitch_panel,
                "Graph": self.stitch_tab.graph_panel,
                "Adjust": self.stitch_tab.adjust_panel,
                "Canvas": self.stitch_tab.canvas_panel,
                "Statistics": self.stitch_tab.stats_panel,
                "Sequence Builder": self.stitch_tab.seq_builder_panel,
                "Hybrid Stitch": self.stitch_tab.hybrid_stitch_panel,
                "Anim Clusters": self.stitch_tab.anim_clusters_panel,
                "Stitch Feedback": self.stitch_feedback_tab,
            },
        }

        # --- APPLY ACTIVE DEFAULT CONFIGURATIONS ---
        # Note: We wait to apply these configs until after startup preferences are applied

        # --- Command Selection (built after all_tabs so the list is always in sync) ---
        command_layout = QHBoxLayout()
        command_label = QLabel("Select Category:")
        command_label.setStyleSheet("font-weight: 600;")
        command_layout.addWidget(command_label)

        self.command_combo = QComboBox()
        self.command_combo.addItems(list(self.all_tabs.keys()))
        self.command_combo.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        command_layout.addWidget(self.command_combo)
        command_layout.addStretch()
        vbox.addLayout(command_layout)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        # Connect after populating so the initial currentTextChanged fires correctly.
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        self.on_command_changed(self.command_combo.currentText())

        # GUI/UX §2.16 — wire vault preferences to runtime at startup
        self._apply_startup_preferences()
        
        # Apply tab configs after global preferences so profile settings take priority
        self._apply_active_tab_configs()

        self.settings_button.clicked.connect(self.open_settings_window)

        # §2.10C — non-blocking status bar at the bottom of the main window
        self._status_bar = QStatusBar()
        self._status_bar.setSizeGripEnabled(False)
        self._status_bar.setMaximumHeight(24)
        vbox.addWidget(self._status_bar)

        self.setLayout(vbox)
        self.set_application_theme(self.current_theme)

        # §2.12A — System tray icon
        self._tray_icon: QSystemTrayIcon | None = None
        self._minimize_to_tray: bool = False
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._setup_tray_icon(app_icon)

        # GUI/UX §2.8 — live OS color-scheme changes (e.g. user toggles dark mode in KDE/Windows)
        try:
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtGui import QGuiApplication as _QGA

            def _on_os_scheme_changed(scheme):
                if not self.cached_creds.get("theme"):
                    new = "light" if scheme == _Qt.ColorScheme.Light else "dark"
                    self.set_application_theme(new)

            _QGA.styleHints().colorSchemeChanged.connect(_on_os_scheme_changed)
        except Exception:
            pass

        # §3.17 — restore saved window geometry (before showMaximized so it can override)
        _geom = QSettings("ImageToolkit", "ImageToolkit").value("mainwindow/geometry")
        if _geom:
            self.restoreGeometry(_geom)
        else:
            self.showMaximized()
        QTimer.singleShot(0, self._restore_session_recovery)

    def on_command_changed(self, new_command: str):
        """
        Dynamically changes the tabs.
        Rescues widgets from ScrollAreas before clearing to prevent Segfaults.
        """
        count = self.tabs.count()
        for i in range(count):
            scroll_area = self.tabs.widget(i)
            if isinstance(scroll_area, QScrollArea):
                # takeWidget() unparents the widget and passes ownership back to us
                # preventing it from being destroyed.
                scroll_area.takeWidget()

        self.tabs.clear()

        tab_map = self.all_tabs.get(new_command, {})

        for tab_name, tab_widget in tab_map.items():
            scroll_wrapper = QScrollArea()
            scroll_wrapper.setWidgetResizable(True)
            scroll_wrapper.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll_wrapper.setWidget(tab_widget)
            self.tabs.addTab(scroll_wrapper, tab_name)

    def update_header(self):
        try:
            self.cached_creds = self.vault_manager.load_account_credentials()
            account_name = self.cached_creds.get("account_name", "Authenticated User")
        except Exception:
            account_name = "Authenticated User"
        self.title_label.setText(f"Image Database and Toolkit - {account_name}")
        self.set_application_theme(self.current_theme)

    def _sanitize_config_if_needed(self, config_data: dict) -> dict:
        """Removes local directory/file path fields from tab configurations if restore_last_dir is False."""
        if not config_data or not isinstance(config_data, dict):
            return config_data
        if not self.cached_creds:
            return config_data
        prefs = self.cached_creds.get("preferences", {})
        if prefs.get("restore_last_dir", True):
            return config_data

        import copy
        sanitized = copy.deepcopy(config_data)

        # Clear or reset fields representing local directories or paths
        keys_to_clear = [
            "scan_directory", "source_directory", "extraction_directory",
            "download_dir", "screenshot_dir", "local_path", "input_path",
            "output_path", "scan_dir", "lora_path", "checkpoint_path",
            "image_path"
        ]
        for key in keys_to_clear:
            if key in sanitized:
                sanitized[key] = ""

        return sanitized

    def _apply_active_tab_configs(self) -> None:
        """Applies the active configuration for each tab dynamically."""
        active_configs = self.cached_creds.get("active_tab_configs", {})
        saved_tab_configs = self.cached_creds.get("tab_configurations", {})

        for category, tabs_in_category in self.all_tabs.items():
            for tab_instance in tabs_in_category.values():
                tab_class_name = type(tab_instance).__name__

                if tab_class_name in active_configs:
                    config_name = active_configs[tab_class_name]
                    
                    if (
                        tab_class_name in saved_tab_configs
                        and config_name in saved_tab_configs[tab_class_name]
                    ):
                        config_data = saved_tab_configs[tab_class_name][config_name]
                        config_data = self._sanitize_config_if_needed(config_data)

                        if hasattr(tab_instance, "set_config") and callable(
                            tab_instance.set_config
                        ):
                            try:
                                tab_instance.set_config(config_data)
                                print(f"Applied active config '{config_name}' to {tab_class_name}")
                            except Exception as e:
                                print(f"Error applying config to {tab_class_name}: {e}")

    def _apply_startup_preferences(self) -> None:
        """Apply vault-stored preferences to gallery tabs at startup (GUI/UX §2.16 A/B/C/E)."""
        prefs = self.cached_creds.get("preferences", {})
        if not prefs:
            return

        # §2.16A — thumbnail size and page size
        thumb_size = int(prefs.get("thumbnail_size", 180))
        page_size = int(prefs.get("page_size", 100))
        # §2.16B — LRU cache sizes
        found_cache = int(prefs.get("found_cache_maxsize", 300))
        selected_cache = int(prefs.get("selected_cache_maxsize", 200))
        initial_cache = int(prefs.get("initial_cache_maxsize", 300))

        # NEW: Extractor seek interval & recent extractions count
        extractor_seek_ms = int(prefs.get("extractor_seek_ms", 100))
        recent_extractions_count = int(prefs.get("recent_extractions_count", 10))

        restore_last_dir = prefs.get("restore_last_dir", True)
        from backend.src.constants import LOCAL_SOURCE_PATH
        default_dir = str(LOCAL_SOURCE_PATH)

        for cat_tabs in self.all_tabs.values():
            for tab in cat_tabs.values():
                # Thumbnail & page size (§2.16A)
                if hasattr(tab, "thumbnail_size"):
                    tab.thumbnail_size = thumb_size
                    if hasattr(tab, "padding_width"):
                        tab.approx_item_width = thumb_size + tab.padding_width + 20
                for attr in ("found_page_size", "selected_page_size", "page_size"):
                    if hasattr(tab, attr):
                        setattr(tab, attr, page_size)
                # LRU caches (§2.16B)
                if hasattr(tab, "_found_pixmap_cache"):
                    tab._found_pixmap_cache = LRUImageCache(maxsize=found_cache)
                if hasattr(tab, "_selected_pixmap_cache"):
                    tab._selected_pixmap_cache = LRUImageCache(maxsize=selected_cache)
                if hasattr(tab, "_initial_pixmap_cache"):
                    tab._initial_pixmap_cache = LRUImageCache(maxsize=initial_cache)

                # Reset directory to default if restore is disabled
                if not restore_last_dir:
                    for obj in (tab, getattr(tab, "format_tab", None)):
                        if obj is not None:
                            if hasattr(obj, "last_browsed_scan_dir"):
                                obj.last_browsed_scan_dir = default_dir
                            if hasattr(obj, "last_browsed_dir"):
                                obj.last_browsed_dir = default_dir

                # Apply Extractor seek interval
                if hasattr(tab, "wheel_seek_ms"):
                    tab.wheel_seek_ms = extractor_seek_ms

                # Apply Extractor recent limit
                if hasattr(tab, "recent_extractions_limit"):
                    tab.recent_extractions_limit = recent_extractions_count
                    if hasattr(tab, "_apply_new_extractions_limit") and callable(tab._apply_new_extractions_limit):
                        tab._apply_new_extractions_limit()

        # §2.16C — startup category
        startup_cat = prefs.get("startup_category", "")
        if startup_cat and startup_cat in self.all_tabs:
            self.command_combo.setCurrentText(startup_cat)

        # §2.16E — slideshow defaults to WallpaperTab
        if hasattr(self, "wallpaper_tab"):
            wt = self.wallpaper_tab
            try:
                wt.interval_min_spinbox.setValue(int(prefs.get("slideshow_interval_min", 5)))
                wt.interval_sec_spinbox.setValue(int(prefs.get("slideshow_interval_sec", 0)))
                order = prefs.get("slideshow_order", "Sequential")
                wt.playback_order_combo.setCurrentText(order)
            except Exception:
                pass

    def restart_application(self):
        self.close()
        QApplication.instance().quit()
        print("Application attempting relaunch...")
        try:
            os.execv(sys.executable, ["python"] + sys.argv)
        except OSError as e:
            QMessageBox.critical(
                self,
                "Relaunch Error",
                f"Failed to execute relaunch command:\n{e}\nPlease restart manually.",
            )
            print(f"FATAL: os.execv failed: {e}")

    # --- §2.10C — Non-blocking status bar API ---
    def show_status(self, message: str, timeout_ms: int = 3000) -> None:
        """Display *message* in the status bar for *timeout_ms* ms (0 = persistent)."""
        if hasattr(self, "_status_bar"):
            self._status_bar.showMessage(message, timeout_ms)

    # --- §2.12A/B/C — System Tray ---
    def _setup_tray_icon(self, app_icon=None) -> None:
        icon = app_icon
        if icon is None or not isinstance(icon, QIcon):
            _asset = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "..", "assets", "images", "image_toolkit_icon.png",
            )
            _asset = os.path.normpath(_asset)
            if os.path.exists(_asset):
                icon = QIcon(_asset)
            else:
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self._tray_icon = QSystemTrayIcon(icon, parent=self)
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._tray_show_window)

        tray_menu.addSeparator()

        daemon_action = tray_menu.addAction("Toggle Daemon")
        daemon_action.triggered.connect(self._tray_toggle_daemon)

        next_wp_action = tray_menu.addAction("Next Wallpaper")
        next_wp_action.triggered.connect(self._tray_next_wallpaper)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.setToolTip("Image Toolkit")
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _tray_show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_toggle_daemon(self) -> None:
        wt = getattr(self, "wallpaper_tab", None)
        if wt and hasattr(wt, "toggle_daemon"):
            current = getattr(wt, "btn_daemon_toggle", None)
            checked = current.isChecked() if current else False
            wt.toggle_daemon(not checked)

    def _tray_next_wallpaper(self) -> None:
        wt = getattr(self, "wallpaper_tab", None)
        if wt and hasattr(wt, "_cycle_slideshow_wallpaper"):
            wt._cycle_slideshow_wallpaper(increment=True)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_show_window()

    def tray_notify(self, title: str, message: str, timeout_ms: int = 4000) -> None:
        """Show a tray balloon notification (§2.12B). No-op when tray is unavailable."""
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, timeout_ms
            )

    def set_minimize_to_tray(self, enabled: bool) -> None:
        """Toggle minimize-to-tray behaviour (§2.12C). Controlled via settings."""
        self._minimize_to_tray = enabled

    # --- §2.16C — Ctrl+T tab search popup ---
    def _open_tab_search(self) -> None:
        """Show a floating tab-name filter popup (§2.16C)."""
        from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout as _VBox

        all_entries: list[tuple[str, str, str]] = []
        for category, tabs_in_cat in self.all_tabs.items():
            for tab_name in tabs_in_cat:
                all_entries.append((category, tab_name, f"{tab_name}  —  {category}"))

        dlg = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dlg.setWindowTitle("Go to Tab")
        dlg.setFixedWidth(400)
        layout = _VBox(dlg)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to filter tabs…")
        layout.addWidget(search_input)

        list_widget = QListWidget()
        list_widget.setMaximumHeight(260)
        layout.addWidget(list_widget)

        def _populate(text: str) -> None:
            list_widget.clear()
            q = text.strip().lower()
            for category, tab_name, label in all_entries:
                if not q or q in tab_name.lower() or q in category.lower():
                    item = QListWidgetItem(label)
                    item.setData(Qt.ItemDataRole.UserRole, (category, tab_name))
                    list_widget.addItem(item)
            if list_widget.count():
                list_widget.setCurrentRow(0)

        def _activate(item=None) -> None:
            if item is None:
                item = list_widget.currentItem()
            if item is None:
                return
            category, tab_name = item.data(Qt.ItemDataRole.UserRole)
            self.command_combo.setCurrentText(category)
            QTimer.singleShot(0, lambda: self._select_tab_by_name(tab_name))
            dlg.accept()

        search_input.textChanged.connect(_populate)
        search_input.returnPressed.connect(_activate)
        list_widget.itemActivated.connect(_activate)
        list_widget.itemDoubleClicked.connect(_activate)

        _populate("")
        dlg.exec()

    def _select_tab_by_name(self, tab_name: str) -> None:
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_name:
                self.tabs.setCurrentIndex(i)
                return

    # --- §2.25A — Keyboard shortcut discovery overlay (Ctrl+/ or F1) ---
    def _open_shortcut_overlay(self) -> None:
        from PySide6.QtWidgets import (
            QDialog, QTableWidget, QTableWidgetItem,
            QVBoxLayout as _VBox, QLineEdit, QHeaderView,
        )
        from PySide6.QtCore import Qt as _Qt
        from ..utils.shortcut_manager import get_registry

        reg = get_registry()
        all_actions = reg.get_all()

        dlg = QDialog(self)
        dlg.setWindowTitle("Keyboard Shortcuts  (Ctrl+/)")
        dlg.resize(560, 460)
        layout = _VBox(dlg)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        search = QLineEdit()
        search.setPlaceholderText("Filter shortcuts…")
        layout.addWidget(search)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Scope", "Action", "Key"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        def _populate(text: str = "") -> None:
            q = text.strip().lower()
            table.setRowCount(0)
            for entry in all_actions:
                if q and q not in entry["description"].lower() and q not in entry["current"].lower() and q not in entry["scope"].lower():
                    continue
                row = table.rowCount()
                table.insertRow(row)
                for col, val in enumerate([entry["scope"], entry["description"], entry["current"]]):
                    item = QTableWidgetItem(val)
                    item.setFlags(_Qt.ItemFlag.ItemIsEnabled | _Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row, col, item)

        search.textChanged.connect(_populate)
        _populate()
        dlg.exec()

    def set_application_theme(self, theme_name):
        prefs = {}
        if hasattr(self, "cached_creds") and self.cached_creds:
            prefs = self.cached_creds.get("preferences", {})

        density = prefs.get("ui_density", "Comfortable")

        if theme_name == "dark":
            accent_color = prefs.get("accent_color_dark", DARK_ACCENT_COLOR)
            overrides = compute_accent_vars(accent_color, "DARK")
            qss = load_qss_with_overrides("dark.qss", overrides)
            self.current_theme = "dark"
            hover_bg = "#5f646c"
            pressed_bg = accent_color
            header_label_color = "white"
            header_widget_bg = "#2d2d30"
        elif theme_name == "light":
            accent_color = prefs.get("accent_color_light", LIGHT_ACCENT_COLOR)
            overrides = compute_accent_vars(accent_color, "LIGHT")
            qss = load_qss_with_overrides("light.qss", overrides)
            self.current_theme = "light"
            hover_bg = "#cccccc"
            pressed_bg = accent_color
            header_label_color = "#1e1e1e"
            header_widget_bg = "#ffffff"
        else:
            return

        if density == "Compact":
            qss += COMPACT_DENSITY_QSS
        elif density == "Spacious":
            qss += SPACIOUS_DENSITY_QSS

        font_scale = prefs.get("font_scale", 100)
        if font_scale != 100:
            from PySide6.QtGui import QFont
            scaled_pt = max(7, int(10 * font_scale / 100))
            QApplication.instance().setFont(QFont("Segoe UI", scaled_pt))

        # §3.16 — append user custom QSS override if present
        qss += load_user_qss_override()

        QApplication.instance().setStyleSheet(qss)

        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            header_widget.setStyleSheet(
                f"background-color: {header_widget_bg}; padding: 10px; border-bottom: 2px solid {accent_color};"
            )
            title_label = self.title_label
            if title_label:
                account_name = self.cached_creds.get(
                    "account_name", "Authenticated User"
                )
                title_label.setText(f"Image Database and Toolkit - {account_name}")
                title_label.setStyleSheet(
                    f"color: {header_label_color}; font-size: 18pt; font-weight: bold;"
                )

        self.settings_button.setStyleSheet(
            f"""
            QPushButton#settings_button {{
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 18px; 
            }}
            QPushButton#settings_button:hover {{
                background-color: {hover_bg}; 
            }}
            QPushButton#settings_button:pressed {{
                background-color: {pressed_bg}; 
            }}
        """
        )

    def open_settings_window(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow(self)
            self.settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.settings_window.destroyed.connect(
                lambda: self._reset_settings_window_ref()
            )
        self.settings_window.show()
        self.settings_window.activateWindow()

    def _reset_settings_window_ref(self):
        self.settings_window = None

    def showEvent(self, event):
        super().showEvent(event)
        self._shown = True

    def _restore_session_recovery(self) -> None:
        """Restores the previously opened tab and configurations on startup."""
        if not self.vault_manager or not self.cached_creds:
            return

        prefs = self.cached_creds.get("preferences", {})
        recovery_level = prefs.get("session_recovery_level", "None")
        if recovery_level == "Currrent Tab":
            recovery_level = "Current Tab"

        if recovery_level == "None":
            return

        username = getattr(self.vault_manager, "account_name", None)
        if not username:
            return

        recovery_data = {}
        for recovery_dir in ("/home/pkhunter/.image-toolkit/recovery", os.path.expanduser("~/.image-toolkit/recovery")):
            enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
            if os.path.exists(enc_file_path):
                try:
                    import json
                    SecureJsonVault = self.vault_manager.SecureJsonVault
                    secret_key = self.vault_manager.secret_key
                    temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                    java_string = temp_file_vault.loadData()
                    decrypted_json = str(java_string)
                    recovery_data = json.loads(decrypted_json)
                    break
                except Exception as e:
                    print(f"Warning: Failed to decrypt recovery file {enc_file_path}: {e}")

        if not recovery_data:
            # Fallback to cached_creds if no file was decrypted (backward compatibility)
            recovery_data = self.cached_creds.get("session_recovery_data")

        if not recovery_data:
            return

        active_category = recovery_data.get("active_category")
        active_tab_name = recovery_data.get("active_tab")
        tab_configs = recovery_data.get("tab_configs", {})

        # Apply config information depending on the level of recovery configured
        if recovery_level == "All Tabs":
            for category, tabs_in_category in self.all_tabs.items():
                for tab_instance in tabs_in_category.values():
                    tab_class_name = type(tab_instance).__name__
                    if tab_class_name in tab_configs:
                        if hasattr(tab_instance, "set_config") and callable(tab_instance.set_config):
                            try:
                                sanitized_cfg = self._sanitize_config_if_needed(tab_configs[tab_class_name])
                                tab_instance.set_config(sanitized_cfg)
                            except Exception as e:
                                print(f"Warning: Failed to restore config to {tab_class_name} during session recovery: {e}")
        elif recovery_level == "Current Tab":
            if active_category and active_tab_name:
                tab_instance = self.all_tabs.get(active_category, {}).get(active_tab_name)
                if tab_instance:
                    tab_class_name = type(tab_instance).__name__
                    if tab_class_name in tab_configs:
                        if hasattr(tab_instance, "set_config") and callable(tab_instance.set_config):
                            try:
                                sanitized_cfg = self._sanitize_config_if_needed(tab_configs[tab_class_name])
                                tab_instance.set_config(sanitized_cfg)
                            except Exception as e:
                                print(f"Warning: Failed to restore config to active tab {tab_class_name} during session recovery: {e}")

        # Transfer user to the previously opened tab
        if active_category and active_category in self.all_tabs:
            self.command_combo.setCurrentText(active_category)
            if active_tab_name:
                for index in range(self.tabs.count()):
                    if self.tabs.tabText(index) == active_tab_name:
                        self.tabs.setCurrentIndex(index)
                        break

    def _save_session_recovery(self) -> None:
        """Saves current active tab and tab configurations for session recovery."""
        if not self.vault_manager:
            return

        try:
            import json
            # Load current credentials/preferences from the vault
            creds = self.vault_manager.load_account_credentials()
            if not creds:
                return

            prefs = creds.get("preferences", {})
            recovery_level = prefs.get("session_recovery_level", "None")
            if recovery_level == "Currrent Tab":
                recovery_level = "Current Tab"

            username = getattr(self.vault_manager, "account_name", None)
            if not username:
                return

            recovery_data = {}
            if recovery_level != "None":
                active_category = self.command_combo.currentText()
                active_tab_index = self.tabs.currentIndex()
                active_tab_name = self.tabs.tabText(active_tab_index) if active_tab_index >= 0 else None

                tab_configs = {}
                if recovery_level == "All Tabs":
                    for category, tabs_in_category in self.all_tabs.items():
                        for tab_instance in tabs_in_category.values():
                            if hasattr(tab_instance, "collect") and callable(tab_instance.collect):
                                try:
                                    tab_configs[type(tab_instance).__name__] = tab_instance.collect()
                                except Exception as e:
                                    print(f"Warning: Failed to collect config from {type(tab_instance).__name__}: {e}")
                elif recovery_level == "Current Tab":
                    if active_category and active_tab_name:
                        tab_instance = self.all_tabs.get(active_category, {}).get(active_tab_name)
                        if tab_instance and hasattr(tab_instance, "collect") and callable(tab_instance.collect):
                            try:
                                tab_configs[type(tab_instance).__name__] = tab_instance.collect()
                            except Exception as e:
                                print(f"Warning: Failed to collect config from active tab {type(tab_instance).__name__}: {e}")

                recovery_data = {
                    "active_category": active_category,
                    "active_tab": active_tab_name,
                    "tab_configs": tab_configs
                }

                # Save session recovery data to the encrypted file
                for recovery_dir in ("/home/pkhunter/.image-toolkit/recovery", os.path.expanduser("~/.image-toolkit/recovery")):
                    try:
                        os.makedirs(recovery_dir, exist_ok=True)
                        enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
                        SecureJsonVault = self.vault_manager.SecureJsonVault
                        secret_key = self.vault_manager.secret_key
                        temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                        temp_file_vault.saveData(json.dumps(recovery_data))
                        break
                    except Exception as e:
                        print(f"Warning: Failed to save recovery data to {recovery_dir}: {e}")

                # Keep vault backup in sync
                creds["session_recovery_data"] = recovery_data
            else:
                creds["session_recovery_data"] = {}
                # Delete recovery file if recovery level is set to None
                for recovery_dir in ("/home/pkhunter/.image-toolkit/recovery", os.path.expanduser("~/.image-toolkit/recovery")):
                    enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
                    if os.path.exists(enc_file_path):
                        try:
                            os.remove(enc_file_path)
                        except Exception as e:
                            print(f"Warning: Failed to remove recovery file: {e}")

            self.vault_manager.save_data(json.dumps(creds))
        except Exception as e:
            print(f"Warning: Failed to save session recovery data: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._save_session_recovery()
            if self.vault_manager:
                self.vault_manager.shutdown()
            QApplication.quit()
        elif (
            event.key() == Qt.Key.Key_T
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            self._open_tab_search()
            event.accept()
        elif (
            event.key() == Qt.Key.Key_Slash
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ) or event.key() == Qt.Key.Key_F1:
            self._open_shortcut_overlay()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # §2.12C — minimize to tray instead of quitting (opt-in)
        if getattr(self, "_minimize_to_tray", False) and self._tray_icon and self._tray_icon.isVisible():
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                "Image Toolkit",
                "Minimised to tray. Double-click the icon to reopen.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            return

        # §3.17 — persist window geometry so next launch restores it
        QSettings("ImageToolkit", "ImageToolkit").setValue(
            "mainwindow/geometry", self.saveGeometry()
        )
        self._save_session_recovery()

        if self.settings_window:
            self.settings_window.close()

        # Close all instantiated tabs to trigger their cleanup logic (cancellation of workers/timers)
        if hasattr(self, "all_tabs"):
            for category in self.all_tabs.values():
                for tab in category.values():
                    if tab:
                        try:
                            tab.close()
                        except Exception:
                            pass

        if self.vault_manager:
            self.vault_manager.shutdown()

        super().closeEvent(event)
