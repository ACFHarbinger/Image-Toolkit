"""``DataBrowserTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from ._edit import _EditMixin
from ._export import _ExportMixin
from ._filters import _FiltersMixin
from ._navigation import _NavigationMixin
from ._query import _QueryMixin
from ._ui_builder import _UIBuilderMixin


class DataBrowserTab(
    QWidget,
    _UIBuilderMixin,
    _QueryMixin,
    _NavigationMixin,
    _FiltersMixin,
    _EditMixin,
    _ExportMixin,
):
    """DB.9: raw-table browser over the unified library store.

    Table picker, paginated raw rows, a WHERE box + per-column filters,
    FK-cell navigation + reverse-references, a schema/ER view, CSV/JSON
    export, and a gated, session-only cell-edit mode (see
    docs/moon/roadmaps/unified_database.md, DB.9).
    """

    PAGE_SIZE = 100

    def __init__(self, vault_manager=None):
        super().__init__()
        self.vault_manager = vault_manager
        self.browser_repo = None  # backend.src.database.unified.browser_repo.BrowserRepo
        self.current_table: Optional[str] = None
        self.current_offset: int = 0
        self.current_row_count: int = 0
        self.current_columns: list = []
        self.current_rows: list = []
        self.current_fks: list = []
        self.fk_columns_by_index: dict = {}
        self.pk_column_index: Optional[int] = None
        self.column_filter_edits: list = []
        self.edit_mode_enabled: bool = False

        self._build_ui()

        # Open automatically when the vault is already unlocked (it is, at
        # normal startup -- the session was created at login/first use),
        # same convention as DatabaseTab.
        if self.vault_manager is not None:
            self.connect_browser(silent=True)


__all__ = ["DataBrowserTab"]
