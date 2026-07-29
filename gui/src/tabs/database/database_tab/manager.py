"""``DatabaseTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional

from backend.src.database.unified.facade import UnifiedImageDatabase as ImageDatabase
from PySide6.QtCore import Property, Signal
from PySide6.QtWidgets import QGroupBox, QScrollArea, QVBoxLayout, QWidget

from ._auto_populate import _AutoPopulateMixin
from ._bulk_import import _BulkImportMixin
from ._config import _ConfigMixin
from ._connection_stats import _ConnectionStatsMixin
from ._context_menus import _ContextMenusMixin
from ._crud import _CrudMixin
from ._refresh_edit import _RefreshEditMixin
from ._ui_connection import _UIConnectionMixin
from ._ui_groups import _UIGroupsMixin
from ._ui_registry import _UIRegistryMixin
from ._ui_subgroups import _UISubgroupsMixin
from ._ui_tags import _UITagsMixin


class DatabaseTab(
    QWidget,
    _UIConnectionMixin,
    _UIGroupsMixin,
    _UISubgroupsMixin,
    _UITagsMixin,
    _UIRegistryMixin,
    _ConnectionStatsMixin,
    _BulkImportMixin,
    _CrudMixin,
    _RefreshEditMixin,
    _ContextMenusMixin,
    _ConfigMixin,
    _AutoPopulateMixin,
):
    """
    Library maintenance: statistics display and tag/group population on the
    unified library database (Phase DB, DB.6 — the PostgreSQL connection is
    gone; the store opens with the vault session).
    """

    def __init__(self, vault_manager=None):
        super().__init__()
        self.vault_manager = vault_manager
        self.db: Optional[ImageDatabase] = None
        self._stats_text = "Not Connected"

        # --- Tab References ---
        # These are assigned by MainWindow after all tabs are initialized
        self.scan_tab_ref = None
        self.search_tab_ref = None
        self.merge_tab_ref = None
        self.delete_tab_ref = None
        self.wallpaper_tab_ref = None

        self.old_edit_value = None

        main_layout = QVBoxLayout(self)

        self._build_connection_section(main_layout)

        self.populate_group = QGroupBox("Populate Database")
        populate_layout = QVBoxLayout(self.populate_group)

        self._build_groups_section(populate_layout)
        self._build_subgroups_section(populate_layout)
        self._build_tags_section(populate_layout)
        self._build_registry_section(populate_layout)

        populate_scroll_area = QScrollArea()
        populate_scroll_area.setWidgetResizable(True)
        populate_scroll_area.setWidget(self.populate_group)
        populate_scroll_area.setStyleSheet("QScrollArea { border: none; }")

        main_layout.addWidget(populate_scroll_area)

        self.update_button_states(connected=False)

        # Open automatically when the vault is already unlocked (it is, at
        # normal startup — the session was created at login/first use).
        if self.vault_manager is not None:
            self.connect_database(silent=True)

    # --- QML Integration ---
    qml_stats_changed = Signal()

    @Property(str, notify=qml_stats_changed)
    def statsText(self):
        return self._stats_text


__all__ = ["DatabaseTab"]
