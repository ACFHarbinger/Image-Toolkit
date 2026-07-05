from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .elements.monitor_display_subtab import MonitorDisplaySubTab
from .elements.system_display_subtab import SystemDisplaySubTab


class WallpaperTab(QWidget):
    def __init__(self, db_tab_ref):
        super().__init__()
        self._tab_widget = QTabWidget()

        self.system_display = SystemDisplaySubTab(db_tab_ref)
        self.monitor_display = MonitorDisplaySubTab()

        # Link them for updates
        self.system_display.linked_tabs = [self.monitor_display]
        self.monitor_display.linked_tabs = [self.system_display]

        # Share state dictionaries
        self.monitor_display.monitor_image_paths = self.system_display.monitor_image_paths
        self.monitor_display.monitor_slideshow_queues = self.system_display.monitor_slideshow_queues
        self.monitor_display.monitor_current_index = self.system_display.monitor_current_index
        self.monitor_display.monitor_history = self.system_display.monitor_history
        self.monitor_display._initial_pixmap_cache = self.system_display._initial_pixmap_cache

        self.monitor_display.set_system_display_ref(self.system_display)
        self.system_display.set_system_display_ref(self.monitor_display)

        self.system_display.monitors_updated.connect(
            self.monitor_display.update_monitors
        )

        if self.system_display.monitors:
            self.monitor_display.update_monitors(self.system_display.monitors)

        # Sync layout reordering
        self.system_display.monitor_layout_container.layout_changed.connect(
            self._sync_layout_system_to_monitor
        )
        self.monitor_display.monitor_layout_container.layout_changed.connect(
            self._sync_layout_monitor_to_system
        )



        self._tab_widget.addTab(self.system_display, "System Display(s)")
        self._tab_widget.addTab(self.monitor_display, "Monitor Display")

        self.system_display.directory_scanned.connect(
            lambda directory: self.monitor_display.populate_scan_image_gallery(directory, emit_signal=False)
        )
        self.monitor_display.directory_scanned.connect(
            lambda directory: self.system_display.populate_scan_image_gallery(directory, emit_signal=False)
        )

        # System Display -> Monitor Display Settings Sync
        self.system_display.sync_page_changed.connect(self.monitor_display.sync_update_page)
        self.system_display.sync_page_size_changed.connect(self.monitor_display.sync_update_page_size)
        self.system_display.sync_thumb_size_changed.connect(self.monitor_display.sync_update_thumb_size)
        self.system_display.sync_sort_combo_changed.connect(self.monitor_display.sync_update_sort_combo)
        self.system_display.sync_sort_dir_changed.connect(self.monitor_display.sync_update_sort_dir)

        # Monitor Display -> System Display Settings Sync
        self.monitor_display.sync_page_changed.connect(self.system_display.sync_update_page)
        self.monitor_display.sync_page_size_changed.connect(self.system_display.sync_update_page_size)
        self.monitor_display.sync_thumb_size_changed.connect(self.system_display.sync_update_thumb_size)
        self.monitor_display.sync_sort_combo_changed.connect(self.system_display.sync_update_sort_combo)
        self.monitor_display.sync_sort_dir_changed.connect(self.system_display.sync_update_sort_dir)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tab_widget)

    def closeEvent(self, event):
        # QWidget.close() does not cascade to child widgets, so the nested
        # subtabs' own closeEvent (and the windows they spawned, e.g. the
        # Wallpaper Queue windows) would otherwise never be closed on app exit.
        self.system_display.close()
        self.monitor_display.close()
        super().closeEvent(event)

    def _sync_layout_system_to_monitor(self):
        container = self.monitor_display.monitor_layout_container
        container.blockSignals(True)
        struct = self.system_display.monitor_layout_container.get_layout_structure()
        container.set_layout_structure(struct, self.monitor_display.monitor_widgets)
        container.blockSignals(False)
        # Preserve selected monitor highlight
        if self.monitor_display._current_monitor_id:
            self.monitor_display._select_monitor(self.monitor_display._current_monitor_id)

    def _sync_layout_monitor_to_system(self):
        container = self.system_display.monitor_layout_container
        container.blockSignals(True)
        struct = self.monitor_display.monitor_layout_container.get_layout_structure()
        container.set_layout_structure(struct, self.system_display.monitor_widgets)
        container.blockSignals(False)



    def collect(self) -> dict:
        result = self.system_display.collect()
        result["monitor_display_graphs"] = self.monitor_display.collect_graphs()
        result["active_subtab_index"] = self._tab_widget.currentIndex()
        return result

    def set_config(self, config: dict):
        self.system_display.set_config(config)
        # Explicitly sync the monitor layout to MonitorDisplay after config restore,
        # since set_layout_structure does not emit layout_changed (only user drag does).
        self._sync_layout_system_to_monitor()
        if "monitor_display_graphs" in config:
            self.monitor_display.restore_graphs(config["monitor_display_graphs"])
        if "active_subtab_index" in config:
            idx = config["active_subtab_index"]
            if 0 <= idx < self._tab_widget.count():
                self._tab_widget.setCurrentIndex(idx)

    def get_default_config(self) -> dict:
        d = self.system_display.get_default_config()
        d["monitor_display_graphs"] = {}
        return d

    # Proxy QML signals for external callers that connected to WallpaperTab directly
    @property
    def qml_monitors_changed(self):
        return self.system_display.qml_monitors_changed

    @property
    def qml_status_changed(self):
        return self.system_display.qml_status_changed
