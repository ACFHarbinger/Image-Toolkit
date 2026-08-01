"""``DataBrowserTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QWidget

from ._export import _ExportMixin
from ._query import _QueryMixin
from ._ui_builder import _UIBuilderMixin


class DataBrowserTab(
    QWidget,
    _UIBuilderMixin,
    _QueryMixin,
    _ExportMixin,
):
    """DB.9: read-only raw-table browser over the unified library store.

    Scoped down from the roadmap's full spec to the table-grid slice --
    table picker, paginated raw rows, a WHERE-clause filter, CSV/JSON
    export. The schema/ER graphics view and gated cell-edit mode are not
    implemented (see moon/roadmaps/unified_database.md, DB.9).
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

        self._build_ui()

        # Open automatically when the vault is already unlocked (it is, at
        # normal startup -- the session was created at login/first use),
        # same convention as DatabaseTab.
        if self.vault_manager is not None:
            self.connect_browser(silent=True)


__all__ = ["DataBrowserTab"]
