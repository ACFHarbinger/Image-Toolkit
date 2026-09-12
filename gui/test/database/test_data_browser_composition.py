"""Tests for DataBrowserTab mixin-to-composition migration (ui-arch-23, #544)."""

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.tabs.database.data_browser_tab import DataBrowserTab
from gui.src.tabs.database.data_browser_tab._edit import DataBrowserEditController
from gui.src.tabs.database.data_browser_tab._er_view import DataBrowserERViewController
from gui.src.tabs.database.data_browser_tab._export import DataBrowserExportController
from gui.src.tabs.database.data_browser_tab._filters import DataBrowserFiltersController
from gui.src.tabs.database.data_browser_tab._navigation import DataBrowserNavigationController
from gui.src.tabs.database.data_browser_tab._query import DataBrowserQueryController
from gui.src.tabs.database.data_browser_tab._ui_builder import DataBrowserUIBuilder

pytestmark = pytest.mark.gui


class TestDataBrowserComposition:
    def test_data_browser_tab_direct_bases_have_no_mixins(self, q_app):
        bases = DataBrowserTab.__bases__
        assert bases == (QWidget,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(DataBrowserTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = DataBrowserTab()
        assert isinstance(tab.ui_builder, DataBrowserUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.er_view_controller, DataBrowserERViewController)
        assert tab.er_view_controller.tab is tab
        assert isinstance(tab.query_controller, DataBrowserQueryController)
        assert tab.query_controller.tab is tab
        assert isinstance(tab.navigation_controller, DataBrowserNavigationController)
        assert tab.navigation_controller.tab is tab
        assert isinstance(tab.filters_controller, DataBrowserFiltersController)
        assert tab.filters_controller.tab is tab
        assert isinstance(tab.edit_controller, DataBrowserEditController)
        assert tab.edit_controller.tab is tab
        assert isinstance(tab.export_controller, DataBrowserExportController)
        assert tab.export_controller.tab is tab
        tab.close()

    def test_tab_bound_controller_attribute_proxy(self, q_app):
        tab = DataBrowserTab()
        assert tab.query_controller.PAGE_SIZE == tab.PAGE_SIZE
        tab.custom_test_attr = 42
        assert tab.edit_controller.custom_test_attr == 42
        tab.close()


def test_no_compat_mixin_aliases():
    """#544 closure: COMPAT mixin-name aliases must not remain (mirrors PR #609)."""
    import importlib
    import pkgutil

    pkg = importlib.import_module("gui.src.tabs.database.data_browser_tab")
    leftover = []
    modules = [pkg]
    for info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        modules.append(importlib.import_module(info.name))
    for mod in modules:
        leftover.extend(name for name in dir(mod) if name.endswith("Mixin") and not name.startswith("__"))
        leftover.extend(name for name in getattr(mod, "__all__", []) if str(name).endswith("Mixin"))
    assert leftover == []
