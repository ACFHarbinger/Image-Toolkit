from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from .common.system_display_subtab import SystemDisplaySubTab
from .common.monitor_display_subtab import MonitorDisplaySubTab


class WallpaperTab(QWidget):
    def __init__(self, db_tab_ref):
        super().__init__()
        self._tab_widget = QTabWidget()

        self.system_display = SystemDisplaySubTab(db_tab_ref)
        self.monitor_display = MonitorDisplaySubTab()

        self.system_display.monitors_updated.connect(
            self.monitor_display.update_monitors
        )

        self._tab_widget.addTab(self.system_display, "System Display(s)")
        self._tab_widget.addTab(self.monitor_display, "Monitor Display")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tab_widget)

    def collect(self) -> dict:
        result = self.system_display.collect()
        result["monitor_display_graphs"] = self.monitor_display.collect_graphs()
        return result

    def set_config(self, config: dict):
        self.system_display.set_config(config)
        if "monitor_display_graphs" in config:
            self.monitor_display.restore_graphs(config["monitor_display_graphs"])

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
