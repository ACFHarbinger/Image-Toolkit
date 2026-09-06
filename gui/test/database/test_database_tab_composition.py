"""Tests for DatabaseTab migration from 12 mixins to composition (ui-arch-23, #544)."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.modules.events import EventHub, FilterByTagIntent, NavigateIntent
from gui.src.tabs.database.database_tab import DatabaseTab
from gui.src.tabs.database.database_tab._auto_populate import DatabaseAutoPopulateController
from gui.src.tabs.database.database_tab._bulk_import import DatabaseBulkImportController
from gui.src.tabs.database.database_tab._config import DatabaseConfigController
from gui.src.tabs.database.database_tab._connection_stats import DatabaseConnectionController
from gui.src.tabs.database.database_tab._context_menus import DatabaseContextMenuController
from gui.src.tabs.database.database_tab._crud import DatabaseCrudController
from gui.src.tabs.database.database_tab._refresh_edit import DatabaseRefreshController
from gui.src.tabs.database.database_tab.ui_builder import DatabaseUIBuilder

pytestmark = pytest.mark.gui


class TestDatabaseTabComposition:
    def test_database_tab_mro_clean(self, q_app):
        """Verify DatabaseTab has only QWidget in its inheritance chain (no mixins)."""
        mro_names = [cls.__name__ for cls in DatabaseTab.__mro__]
        # Must only contain DatabaseTab, QWidget, QPaintDevice (if present), QObject, object
        for name in mro_names:
            assert not name.endswith("Mixin"), f"Found mixin in MRO: {name}"
            assert not name.startswith("_UI"), f"Found UI mixin in MRO: {name}"

        assert issubclass(DatabaseTab, QWidget)
        assert DatabaseTab.__mro__[0] is DatabaseTab
        assert DatabaseTab.__mro__[1] is QWidget

    def test_controllers_composition(self, q_app):
        """Verify all dedicated controllers are instantiated and bound to tab."""
        tab = DatabaseTab()
        assert isinstance(tab.connection_controller, DatabaseConnectionController)
        assert tab.connection_controller.tab is tab

        assert isinstance(tab.crud_controller, DatabaseCrudController)
        assert tab.crud_controller.tab is tab

        assert isinstance(tab.refresh_controller, DatabaseRefreshController)
        assert tab.refresh_controller.tab is tab

        assert isinstance(tab.bulk_import_controller, DatabaseBulkImportController)
        assert tab.bulk_import_controller.tab is tab

        assert isinstance(tab.auto_populate_controller, DatabaseAutoPopulateController)
        assert tab.auto_populate_controller.tab is tab

        assert isinstance(tab.context_menu_controller, DatabaseContextMenuController)
        assert tab.context_menu_controller.tab is tab

        assert isinstance(tab.config_controller, DatabaseConfigController)
        assert tab.config_controller.tab is tab

        assert isinstance(tab.ui_builder, DatabaseUIBuilder)
        assert tab.ui_builder.tab is tab

    def test_ui_elements_attached_via_builder(self, q_app):
        """Verify all expected UI controls are built and attached to tab."""
        tab = DatabaseTab()
        assert hasattr(tab, "btn_connect")
        assert hasattr(tab, "btn_reset_db")
        assert hasattr(tab, "btn_vacuum")
        assert hasattr(tab, "btn_reindex")
        assert hasattr(tab, "btn_embed_backfill")
        assert hasattr(tab, "groups_table")
        assert hasattr(tab, "subgroups_table")
        assert hasattr(tab, "tags_table")
        assert hasattr(tab, "image_registry_table")
        assert hasattr(tab, "new_group_name_edit")
        assert hasattr(tab, "new_subgroup_name_edit")
        assert hasattr(tab, "new_tag_name_edit")

    def test_crud_facade_delegates_to_controller(self, q_app):
        """Verify CRUD operations delegate from DatabaseTab facade to DatabaseCrudController."""
        tab = DatabaseTab()
        tab.db = MagicMock()
        tab.new_group_name_edit.setText("Art, Fantasy")
        tab.refresh_groups_list = MagicMock()
        tab.update_statistics = MagicMock()

        with patch("gui.src.tabs.database.database_tab._crud.QMessageBox.information"):
            tab.create_new_group()

        assert tab.db.add_group.call_count == 2
        tab.db.add_group.assert_any_call("Art")
        tab.db.add_group.assert_any_call("Fantasy")
        tab.refresh_groups_list.assert_called_once()
        tab.update_statistics.assert_called_once()

    def test_config_persistence_through_controller(self, q_app):
        """Verify config persistence methods operate through DatabaseConfigController."""
        tab = DatabaseTab()
        tab.db = MagicMock()
        assert tab.collect() == {"auto_open": True}
        assert tab.get_default_config() == {"auto_open": True}

        tab.db = None
        tab.connect_database = MagicMock()
        tab.set_config({"auto_open": True})
        tab.connect_database.assert_called_once_with(silent=True)

    def test_event_hub_intents_intact(self, q_app):
        """Verify tag search still emits FilterByTagIntent and NavigateIntent through EventHub."""
        hub = EventHub(q_app)
        tab = DatabaseTab(event_hub=hub)
        tab.tags_table.setRowCount(1)
        from PySide6.QtWidgets import QTableWidgetItem

        tab.tags_table.setItem(0, 0, QTableWidgetItem("portrait"))
        tab.tags_table.setCurrentCell(0, 0)

        events = []
        hub.subscribe(FilterByTagIntent, events.append)
        hub.subscribe(NavigateIntent, events.append)

        with patch("gui.src.tabs.database.database_tab._crud.QMessageBox.information"):
            tab.search_images_with_selected_tag()

        assert len(events) == 2
        assert isinstance(events[0], FilterByTagIntent)
        assert events[0].tag_name == "portrait"
        assert isinstance(events[1], NavigateIntent)
        assert events[1].module_id == "library.search"
