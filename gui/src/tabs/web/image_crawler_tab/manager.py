"""``ImageCrawlTab`` -- composed from controllers (#544)."""

from __future__ import annotations

from typing import Any

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QWidget

from ....constants import SCREENSHOTS_DIR
from ....windows.logging import LogWindow
from ._action_builder import ImageCrawlActionController, _ActionBuilderMixin
from ._board_settings import ImageCrawlBoardController, _BoardSettingsMixin
from ._config import ImageCrawlConfigController, _ConfigMixin
from ._crawl_worker import ImageCrawlWorkerController, _CrawlWorkerMixin
from ._directory_browse import ImageCrawlDirectoryController, _DirectoryBrowseMixin
from ._ui_builder import ImageCrawlUIBuilder, _UIBuilderMixin
from ._webdriver import ImageCrawlWebDriverController, _WebDriverMixin


class ImageCrawlTab(QWidget):
    """Web crawler management tab composed of dedicated controllers."""

    # --- QML Integration Signals ---
    qml_crawling_changed = Signal()
    qml_log_changed = Signal()
    qml_settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
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

        # Composed controllers
        self.action_controller = ImageCrawlActionController(self)
        self.board_controller = ImageCrawlBoardController(self)
        self.config_controller = ImageCrawlConfigController(self)
        self.crawl_worker_controller = ImageCrawlWorkerController(self)
        self.directory_controller = ImageCrawlDirectoryController(self)
        self.ui_builder = ImageCrawlUIBuilder(self)
        self.webdriver_controller = ImageCrawlWebDriverController(self)

        self._build_ui()

    # --- QML Properties and Slots ---
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

    # --- Facade delegation ---
    # UI Builder
    def _build_ui(self) -> None:
        self.ui_builder.build_ui()

    def setup_general_page(self) -> None:
        self.ui_builder.setup_general_page()

    def setup_board_page(self) -> None:
        self.ui_builder.setup_board_page()

    # Directory browse
    @Slot()
    def browse_download_directory(self) -> None:
        self.directory_controller.browse_download_directory()

    @Slot()
    def browse_screenshot_directory(self) -> None:
        self.directory_controller.browse_screenshot_directory()

    # Board settings
    def update_board_auth_labels(self, index: int) -> None:
        self.board_controller.update_board_auth_labels(index)

    def on_crawler_type_changed(self, index: int) -> None:
        self.board_controller.on_crawler_type_changed(index)

    # WebDriver
    def toggle_webdriver(self) -> None:
        self.webdriver_controller.toggle_webdriver()

    def on_webdriver_stdout(self) -> None:
        self.webdriver_controller.on_webdriver_stdout()

    def on_webdriver_stderr(self) -> None:
        self.webdriver_controller.on_webdriver_stderr()

    def on_webdriver_finished(self) -> None:
        self.webdriver_controller.on_webdriver_finished()

    # Config
    def collect(self) -> dict[str, Any]:
        return self.config_controller.collect()

    def get_default_config(self) -> dict[str, Any]:
        return self.config_controller.get_default_config()

    def set_config(self, config: dict[str, Any]) -> None:
        self.config_controller.set_config(config)

    # Action builder
    def show_context_menu(self, pos) -> None:
        self.action_controller.show_context_menu(pos)

    def edit_action_parameter(self) -> None:
        self.action_controller.edit_action_parameter()

    def move_action_up(self) -> None:
        self.action_controller.move_action_up()

    def move_action_down(self) -> None:
        self.action_controller.move_action_down()

    def add_action(self) -> None:
        self.action_controller.add_action()

    def remove_action(self) -> None:
        self.action_controller.remove_action()

    # Crawl worker
    @Slot()
    def start_crawl(self) -> None:
        self.crawl_worker_controller.start_crawl()

    @Slot()
    def cancel_crawl(self) -> None:
        self.crawl_worker_controller.cancel_crawl()

    def _delete_pruned_file(self, clean_path: str) -> None:
        self.crawl_worker_controller._delete_pruned_file(clean_path)

    def on_crawl_done(self, count: int, message: str) -> None:
        self.crawl_worker_controller.on_crawl_done(count, message)


__all__ = [
    "ImageCrawlTab",
    "_ActionBuilderMixin",
    "_BoardSettingsMixin",
    "_ConfigMixin",
    "_CrawlWorkerMixin",
    "_DirectoryBrowseMixin",
    "_UIBuilderMixin",
    "_WebDriverMixin",
]
