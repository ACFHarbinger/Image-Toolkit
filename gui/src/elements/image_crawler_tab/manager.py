"""``ImageCrawlTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Property, Signal
from PySide6.QtWidgets import QWidget

from ...constants import SCREENSHOTS_DIR
from ...windows.logging import LogWindow
from ._action_builder import _ActionBuilderMixin
from ._board_settings import _BoardSettingsMixin
from ._config import _ConfigMixin
from ._crawl_worker import _CrawlWorkerMixin
from ._directory_browse import _DirectoryBrowseMixin
from ._ui_builder import _UIBuilderMixin
from ._webdriver import _WebDriverMixin


class ImageCrawlTab(
    _UIBuilderMixin,
    _ActionBuilderMixin,
    _BoardSettingsMixin,
    _DirectoryBrowseMixin,
    _CrawlWorkerMixin,
    _WebDriverMixin,
    _ConfigMixin,
    QWidget,
):
    def __init__(self):
        super().__init__()
        self.worker = None

        # --- Log Window Initialization ---
        self.log_window = LogWindow(tab_name="Web Crawler", parent=self)
        self.log_window.hide()

        self.last_browsed_download_dir = LOCAL_SOURCE_PATH
        self.last_browsed_screenshot_dir = SCREENSHOTS_DIR

        # QML Integration State
        self._is_crawling = False
        self._log_output = ""
        self._gen_headless = True
        self._save_screenshots = False
        self._screenshot_dir = SCREENSHOTS_DIR

        self._build_ui()

    # --- QML Properties and Slots ---
    qml_crawling_changed = Signal()
    qml_log_changed = Signal()
    qml_settings_changed = Signal()

    @Property(bool, notify=qml_crawling_changed)
    def is_crawling(self):
        return self._is_crawling

    @Property(str, notify=qml_log_changed)
    def log_output(self):
        return self._log_output

    @Property(str, notify=qml_settings_changed)
    def screenshot_dir(self):
        return self.screenshot_dir_path.text()

    @Property(bool, notify=qml_settings_changed)
    def gen_headless(self):
        return self._gen_headless

    @gen_headless.setter
    def gen_headless(self, val):
        if self._gen_headless != val:
            self._gen_headless = val
            self.qml_settings_changed.emit()

    @Property(bool, notify=qml_settings_changed)
    def save_screenshots(self):
        return self._save_screenshots

    @save_screenshots.setter
    def save_screenshots(self, val):
        if self._save_screenshots != val:
            self._save_screenshots = val
            self.qml_settings_changed.emit()


__all__ = ["ImageCrawlTab"]
