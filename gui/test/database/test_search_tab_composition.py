"""Tests for SearchTab mixin-to-composition migration (ui-arch-23, #544)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.classes import AbstractClassTwoGalleries
from gui.src.tabs.database.search_tab import SearchTab
from gui.src.tabs.database.search_tab._config import SearchConfigController
from gui.src.tabs.database.search_tab._file_actions import SearchFileActionsController
from gui.src.tabs.database.search_tab._format_filters import SearchFormatFiltersController
from gui.src.tabs.database.search_tab._gallery_cards import SearchGalleryCardsController
from gui.src.tabs.database.search_tab._group_filters import SearchGroupFiltersController
from gui.src.tabs.database.search_tab._qml_wrappers import SearchQmlController
from gui.src.tabs.database.search_tab._search_worker import SearchWorkerController
from gui.src.tabs.database.search_tab._semantic_search import SearchSemanticController
from gui.src.tabs.database.search_tab._tab_communication import SearchTabCommunicationController
from gui.src.tabs.database.search_tab._tag_filters import SearchTagFiltersController
from gui.src.tabs.database.search_tab._ui_builder import SearchUIBuilder

pytestmark = pytest.mark.gui


def _make_tab():
    return SearchTab(database_service=MagicMock(db=None))


class TestSearchTabComposition:
    def test_search_tab_direct_bases_have_no_mixins(self, q_app):
        bases = SearchTab.__bases__
        assert bases == (AbstractClassTwoGalleries,)
        for cls in bases:
            assert not cls.__name__.endswith("Mixin")
        assert issubclass(SearchTab, QWidget)

    def test_controllers_are_composed(self, q_app):
        tab = _make_tab()
        assert isinstance(tab.ui_builder, SearchUIBuilder)
        assert tab.ui_builder.tab is tab
        assert isinstance(tab.gallery_cards, SearchGalleryCardsController)
        assert isinstance(tab.search_worker, SearchWorkerController)
        assert isinstance(tab.semantic, SearchSemanticController)
        assert isinstance(tab.qml, SearchQmlController)
        assert isinstance(tab.format_filters, SearchFormatFiltersController)
        assert isinstance(tab.tag_filters, SearchTagFiltersController)
        assert isinstance(tab.group_filters, SearchGroupFiltersController)
        assert isinstance(tab.tab_communication, SearchTabCommunicationController)
        assert isinstance(tab.file_actions, SearchFileActionsController)
        assert isinstance(tab.config_controller, SearchConfigController)
        tab.close()

    def test_facade_delegates_toggle_selection(self, q_app, tmp_path):
        tab = _make_tab()
        paths = []
        for i in range(4):
            p = tmp_path / f"img_{i}.png"
            p.write_bytes(b"x")
            paths.append(str(p))
        tab.start_loading_thumbnails(paths)
        tab.toggle_selection(paths[1])
        assert paths[1] in tab.selected_files
        tab.close()

    def test_get_default_config_keys(self, q_app):
        tab = _make_tab()
        cfg = tab.get_default_config()
        assert set(cfg) >= {"group_names", "subgroup_names", "filename_pattern", "input_formats", "tags"}
        tab.close()


def test_no_compat_mixin_aliases():
    """#544 closure: COMPAT mixin-name aliases must not remain (mirrors PR #609)."""
    import importlib
    import pkgutil

    pkg = importlib.import_module("gui.src.tabs.database.search_tab")
    leftover = []
    modules = [pkg]
    for info in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        modules.append(importlib.import_module(info.name))
    for mod in modules:
        leftover.extend(name for name in dir(mod) if name.endswith("Mixin") and not name.startswith("__"))
        leftover.extend(name for name in getattr(mod, "__all__", []) if str(name).endswith("Mixin"))
    assert leftover == []
