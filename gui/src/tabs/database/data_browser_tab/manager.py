"""``DataBrowserTab`` -- composed controllers over ``QWidget`` (#544)."""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtWidgets import QListWidgetItem, QWidget

from ._edit import DataBrowserEditController
from ._er_view import DataBrowserERViewController, _TableCardItem
from ._export import DataBrowserExportController
from ._filters import DataBrowserFiltersController
from ._navigation import DataBrowserNavigationController
from ._query import DataBrowserQueryController
from ._ui_builder import DataBrowserUIBuilder


class DataBrowserTab(QWidget):
    """DB.9: raw-table browser over the unified library store.

    Table picker, paginated raw rows, a WHERE box + per-column filters,
    FK-cell navigation + reverse-references, a schema/ER view, CSV/JSON
    export, and a gated, session-only cell-edit mode (see
    docs/moon/roadmaps/unified_database.md, DB.9).

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
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

        self.ui_builder = DataBrowserUIBuilder(self)
        self.er_view_controller = DataBrowserERViewController(self)
        self.query_controller = DataBrowserQueryController(self)
        self.navigation_controller = DataBrowserNavigationController(self)
        self.filters_controller = DataBrowserFiltersController(self)
        self.edit_controller = DataBrowserEditController(self)
        self.export_controller = DataBrowserExportController(self)

        self.ui_builder._build_ui()

        # Open automatically when the vault is already unlocked (it is, at
        # normal startup -- the session was created at login/first use),
        # same convention as DatabaseTab.
        if self.vault_manager is not None:
            self.connect_browser(silent=True)

    # ------------------------------------------------------------------
    # Query & Lifecycle facade
    # ------------------------------------------------------------------
    def connect_browser(self, silent: bool = False) -> None:
        return self.query_controller.connect_browser(silent=silent)

    def refresh_table_list(self) -> None:
        return self.query_controller.refresh_table_list()

    def _on_table_changed(self, table_name: str) -> None:
        return self.query_controller._on_table_changed(table_name)

    def _refresh_row_count(self) -> None:
        return self.query_controller._refresh_row_count()

    def _apply_filter(self) -> None:
        return self.query_controller._apply_filter()

    def _clear_filter(self) -> None:
        return self.query_controller._clear_filter()

    def _prev_page(self) -> None:
        return self.query_controller._prev_page()

    def _next_page(self) -> None:
        return self.query_controller._next_page()

    def _run_query(self) -> None:
        return self.query_controller._run_query()

    def _populate_grid(self, columns: list, rows: list) -> None:
        return self.query_controller._populate_grid(columns, rows)

    # ------------------------------------------------------------------
    # Navigation & FK facade
    # ------------------------------------------------------------------
    def _refresh_fk_metadata(self) -> None:
        return self.navigation_controller._refresh_fk_metadata()

    def _style_fk_cells(self) -> None:
        return self.navigation_controller._style_fk_cells()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        return self.navigation_controller._on_cell_clicked(row, col)

    def _on_row_selection_changed(self) -> None:
        return self.navigation_controller._on_row_selection_changed()

    def _on_reverse_ref_clicked(self, item: QListWidgetItem) -> None:
        return self.navigation_controller._on_reverse_ref_clicked(item)

    def _navigate_to(self, table: str, column: str, value: Any) -> None:
        return self.navigation_controller._navigate_to(table, column, value)

    # ------------------------------------------------------------------
    # Filter facade
    # ------------------------------------------------------------------
    def _clear_column_filters(self) -> None:
        return self.filters_controller._clear_column_filters()

    def _rebuild_column_filters(self, columns: List[str]) -> None:
        return self.filters_controller._rebuild_column_filters(columns)

    def _compose_where(self) -> Optional[str]:
        return self.filters_controller._compose_where()

    # ------------------------------------------------------------------
    # Edit facade
    # ------------------------------------------------------------------
    def _on_edit_mode_toggled(self, checked: bool) -> None:
        return self.edit_controller._on_edit_mode_toggled(checked)

    def _apply_cell_edit_flags(self) -> None:
        return self.edit_controller._apply_cell_edit_flags()

    def _on_cell_changed(self, row: int, col: int) -> None:
        return self.edit_controller._on_cell_changed(row, col)

    def _revert_cell(self, row: int, col: int, original_text: str) -> None:
        return self.edit_controller._revert_cell(row, col, original_text)

    # ------------------------------------------------------------------
    # Export facade
    # ------------------------------------------------------------------
    def export_csv(self) -> None:
        return self.export_controller.export_csv()

    def export_json(self) -> None:
        return self.export_controller.export_json()

    # ------------------------------------------------------------------
    # ER / Schema facade
    # ------------------------------------------------------------------
    def _build_er_view(self) -> QWidget:
        return self.er_view_controller._build_er_view()

    def _refresh_er_view(self) -> None:
        return self.er_view_controller._refresh_er_view()

    def _draw_relationship(self, src_card: _TableCardItem, dst_card: _TableCardItem) -> None:
        return self.er_view_controller._draw_relationship(src_card, dst_card)

    def _on_er_table_clicked(self, table_name: str) -> None:
        return self.er_view_controller._on_er_table_clicked(table_name)

    # ------------------------------------------------------------------
    # UI Builder facade
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        return self.ui_builder._build_ui()

    def _build_grid_view(self) -> QWidget:
        return self.ui_builder._build_grid_view()

    def _set_controls_enabled(self, enabled: bool) -> None:
        return self.ui_builder._set_controls_enabled(enabled)


__all__ = ["DataBrowserTab"]
