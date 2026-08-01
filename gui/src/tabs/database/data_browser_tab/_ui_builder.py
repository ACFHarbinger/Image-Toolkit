"""Full UI construction for ``DataBrowserTab``.

Extracted the same way every other tab in this package is -- pure
composition, no logic beyond widget construction and wiring.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ....styles import apply_shadow_effect
from ._er_view import _ERViewMixin


class _UIBuilderMixin(_ERViewMixin):
    """Builds the table picker, WHERE filter, grid, pagination, export, and
    Schema/ER sub-view controls."""

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        picker_group = QGroupBox("Table")
        picker_layout = QHBoxLayout(picker_group)

        self.table_combo = QComboBox()
        self.table_combo.setMinimumWidth(200)
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        picker_layout.addWidget(self.table_combo)

        self.btn_refresh_tables = QPushButton("Refresh")
        apply_shadow_effect(
            self.btn_refresh_tables, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_refresh_tables.clicked.connect(self.refresh_table_list)
        picker_layout.addWidget(self.btn_refresh_tables)

        self.row_count_label = QLabel("Not connected.")
        self.row_count_label.setStyleSheet("color: #aaa; font-style: italic;")
        picker_layout.addWidget(self.row_count_label)
        picker_layout.addStretch()

        layout.addWidget(picker_group)

        self.view_tabs = QTabWidget()
        self.view_tabs.addTab(self._build_grid_view(), "Grid")
        self.view_tabs.addTab(self._build_er_view(), "Schema")
        layout.addWidget(self.view_tabs)

        self.setLayout(layout)
        self._set_controls_enabled(False)

    def _build_grid_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- WHERE filter ---
        filter_layout = QHBoxLayout()
        self.where_edit = QLineEdit()
        self.where_edit.setPlaceholderText(
            "Optional WHERE clause, e.g. file_path LIKE '%.png' (read-only; "
            "no INSERT/UPDATE/DELETE/DROP/etc.)"
        )
        self.where_edit.returnPressed.connect(self._apply_filter)
        filter_layout.addWidget(self.where_edit)

        self.btn_apply_filter = QPushButton("Apply")
        apply_shadow_effect(
            self.btn_apply_filter, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_apply_filter.clicked.connect(self._apply_filter)
        filter_layout.addWidget(self.btn_apply_filter)

        self.btn_clear_filter = QPushButton("Clear")
        self.btn_clear_filter.clicked.connect(self._clear_filter)
        filter_layout.addWidget(self.btn_clear_filter)

        layout.addLayout(filter_layout)

        # --- Grid + reverse-references side panel ---
        self.data_table = QTableWidget()
        self.data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.data_table.setSortingEnabled(True)
        self.data_table.cellClicked.connect(self._on_cell_clicked)
        self.data_table.itemSelectionChanged.connect(self._on_row_selection_changed)

        refs_panel = QWidget()
        refs_layout = QVBoxLayout(refs_panel)
        refs_layout.setContentsMargins(0, 0, 0, 0)
        refs_label = QLabel("Referenced By")
        refs_label.setStyleSheet("font-weight: bold;")
        refs_layout.addWidget(refs_label)
        self.refs_hint_label = QLabel("Select a row to see incoming references.")
        self.refs_hint_label.setWordWrap(True)
        self.refs_hint_label.setStyleSheet("color: #aaa; font-style: italic;")
        refs_layout.addWidget(self.refs_hint_label)
        self.refs_list = QListWidget()
        self.refs_list.itemClicked.connect(self._on_reverse_ref_clicked)
        refs_layout.addWidget(self.refs_list)

        grid_splitter = QSplitter()
        grid_splitter.addWidget(self.data_table)
        grid_splitter.addWidget(refs_panel)
        grid_splitter.setStretchFactor(0, 4)
        grid_splitter.setStretchFactor(1, 1)
        layout.addWidget(grid_splitter)

        # --- Pagination + export ---
        bottom_layout = QHBoxLayout()

        self.btn_prev_page = QPushButton("◀ Prev")
        self.btn_prev_page.clicked.connect(self._prev_page)
        bottom_layout.addWidget(self.btn_prev_page)

        self.page_label = QLabel("Page 1")
        bottom_layout.addWidget(self.page_label)

        self.btn_next_page = QPushButton("Next ▶")
        self.btn_next_page.clicked.connect(self._next_page)
        bottom_layout.addWidget(self.btn_next_page)

        bottom_layout.addStretch()

        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.clicked.connect(self.export_csv)
        bottom_layout.addWidget(self.btn_export_csv)

        self.btn_export_json = QPushButton("Export JSON")
        self.btn_export_json.clicked.connect(self.export_json)
        bottom_layout.addWidget(self.btn_export_json)

        layout.addLayout(bottom_layout)
        return container

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.table_combo, self.where_edit, self.btn_apply_filter,
            self.btn_clear_filter, self.btn_prev_page, self.btn_next_page,
            self.btn_export_csv, self.btn_export_json,
        ):
            widget.setEnabled(enabled)


__all__ = ["_UIBuilderMixin"]
