"""Tests for ImageCrawlTab mixin-to-composition migration (ui-arch-23, #544)."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.tabs.web.image_crawler_tab import ImageCrawlTab
from gui.src.tabs.web.image_crawler_tab._action_builder import (
    ImageCrawlActionController,
    _ActionBuilderMixin,
)
from gui.src.tabs.web.image_crawler_tab._board_settings import (
    ImageCrawlBoardController,
    _BoardSettingsMixin,
)
from gui.src.tabs.web.image_crawler_tab._config import (
    ImageCrawlConfigController,
    _ConfigMixin,
)
from gui.src.tabs.web.image_crawler_tab._crawl_worker import (
    ImageCrawlWorkerController,
    _CrawlWorkerMixin,
)
from gui.src.tabs.web.image_crawler_tab._directory_browse import (
    ImageCrawlDirectoryController,
    _DirectoryBrowseMixin,
)
from gui.src.tabs.web.image_crawler_tab._ui_builder import (
    ImageCrawlUIBuilder,
)
from gui.src.tabs.web.image_crawler_tab._webdriver import (
    ImageCrawlWebDriverController,
    _WebDriverMixin,
)

pytestmark = pytest.mark.gui


class TestImageCrawlComposition:
    def test_image_crawl_tab_direct_bases_have_no_mixins(self, q_app):
        bases = ImageCrawlTab.__bases__
        assert bases == (QWidget,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(ImageCrawlTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        with patch("gui.src.tabs.web.image_crawler_tab.manager.LogWindow"):
            tab = ImageCrawlTab()
            assert isinstance(tab.action_controller, ImageCrawlActionController)
            assert tab.action_controller.tab is tab
            assert isinstance(tab.board_controller, ImageCrawlBoardController)
            assert tab.board_controller.tab is tab
            assert isinstance(tab.config_controller, ImageCrawlConfigController)
            assert tab.config_controller.tab is tab
            assert isinstance(tab.crawl_worker_controller, ImageCrawlWorkerController)
            assert tab.crawl_worker_controller.tab is tab
            assert isinstance(tab.directory_controller, ImageCrawlDirectoryController)
            assert tab.directory_controller.tab is tab
            assert isinstance(tab.ui_builder, ImageCrawlUIBuilder)
            assert tab.ui_builder.tab is tab
            assert isinstance(tab.webdriver_controller, ImageCrawlWebDriverController)
            assert tab.webdriver_controller.tab is tab
            tab.close()

    def test_compat_mixin_aliases(self):
        assert _ActionBuilderMixin is ImageCrawlActionController
        assert _BoardSettingsMixin is ImageCrawlBoardController
        assert _ConfigMixin is ImageCrawlConfigController
        assert _CrawlWorkerMixin is ImageCrawlWorkerController
        assert _DirectoryBrowseMixin is ImageCrawlDirectoryController
        assert _WebDriverMixin is ImageCrawlWebDriverController

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        with patch("gui.src.tabs.web.image_crawler_tab.manager.LogWindow"):
            tab = ImageCrawlTab()
            tab.custom_proxy_test = "crawler_test_value"
            assert tab.directory_controller.custom_proxy_test == "crawler_test_value"
            tab.close()

    def test_config_facade_roundtrip(self, q_app):
        with patch("gui.src.tabs.web.image_crawler_tab.manager.LogWindow"):
            tab = ImageCrawlTab()
            cfg = tab.get_default_config()
            assert isinstance(cfg, dict)
            assert cfg["crawler_type_index"] == 0
            cfg["gen_login_url"] = "https://example.com/test-login"
            tab.set_config(cfg)
            collected = tab.collect()
            assert collected["gen_login_url"] == "https://example.com/test-login"
            tab.close()
