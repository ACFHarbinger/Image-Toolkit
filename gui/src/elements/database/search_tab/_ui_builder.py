"""Full UI construction for ``SearchTab``.

Extracted from ``SearchTab.__init__`` -- pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ....components import MarqueeScrollArea, OptionalField
from ....styles import apply_shadow_effect

_SEARCH_BUTTON_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #667eea, stop:1 #764ba2);
        color: white; font-weight: bold; font-size: 16px;
        padding: 14px; border-radius: 10px; min-height: 44px;
    }
    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #764ba2, stop:1 #667eea); }
    QPushButton:disabled { background: #4f545c; color: #a0a0a0; }
    QPushButton:pressed { background: #5a67d8; }
"""


class _UIBuilderMixin:
    """Builds the search-criteria form, both galleries, and search controls."""

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_group = QGroupBox("Search Database")
        form_layout = QFormLayout(search_group)
        form_layout.setContentsMargins(10, 20, 10, 10)

        self._build_groups_subgroups(form_layout)
        self._build_filename_and_formats(form_layout)
        self._build_tag_filters(form_layout)

        layout.addWidget(search_group)
        self._build_search_button(layout)
        self._build_semantic_search_section(layout)
        self._build_galleries(layout)

        # **Assign Base Class References**
        self.found_gallery_scroll = self.results_scroll
        self.found_gallery_layout = self.results_layout

        self.selected_gallery_scroll = self.selected_scroll
        self.selected_gallery_layout = self.selected_layout_grid

        self.setLayout(layout)

        # Enable widget to receive keyboard events for shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Update enabled state based on DB connection
        self.update_search_button_state()

        # Initial cleanup
        self.clear_galleries()

    def _build_groups_subgroups(self, form_layout: QFormLayout) -> None:
        # Refresh button for groups/subgroups
        self.btn_refresh_groups = QPushButton("Refresh Groups")
        self.btn_refresh_groups.setFixedWidth(140)
        apply_shadow_effect(
            self.btn_refresh_groups, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_refresh_groups.clicked.connect(self._refresh_groups_from_db)

        # --- Groups (checkable list) ---
        self.groups_list_widget = QListWidget()
        self.groups_list_widget.setMinimumHeight(200)
        self.groups_list_widget.setStyleSheet(
            "QListWidget::item { padding: 4px; } "
            "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 8px; }"
        )
        self.groups_list_widget.itemChanged.connect(self._on_group_selection_changed)

        # --- Subgroups (checkable list, filtered by selected groups) ---
        self.subgroups_list_widget = QListWidget()
        self.subgroups_list_widget.setMinimumHeight(200)
        self.subgroups_list_widget.setStyleSheet(
            "QListWidget::item { padding: 4px; } "
            "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 8px; }"
        )
        # Internal store: list of (group_name, subgroup_name)
        self._all_subgroups_detailed: list = []

        # Containers for side-by-side Groups/Subgroups layout
        groups_container = QWidget()
        groups_layout = QHBoxLayout(groups_container)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_layout.setSpacing(15)

        # Groups Column
        groups_col = QWidget()
        groups_col_layout = QVBoxLayout(groups_col)
        groups_col_layout.setContentsMargins(0, 0, 0, 0)

        groups_header_layout = QHBoxLayout()
        groups_label = QLabel("Groups:")
        groups_label.setStyleSheet("font-weight: bold;")
        groups_header_layout.addWidget(groups_label)
        groups_header_layout.addStretch()
        groups_header_layout.addWidget(self.btn_refresh_groups)

        groups_col_layout.addLayout(groups_header_layout)
        groups_col_layout.addWidget(self.groups_list_widget)

        # Subgroups Column
        subgroups_col = QWidget()
        subgroups_col_layout = QVBoxLayout(subgroups_col)
        subgroups_col_layout.setContentsMargins(0, 0, 0, 0)

        subgroups_label = QLabel("Subgroups:")
        subgroups_label.setStyleSheet("font-weight: bold;")
        subgroups_col_layout.addWidget(subgroups_label)
        subgroups_col_layout.addWidget(self.subgroups_list_widget)

        groups_layout.addWidget(groups_col)
        groups_layout.addWidget(subgroups_col)

        form_layout.addRow(groups_container)

    def _build_filename_and_formats(self, form_layout: QFormLayout) -> None:
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("e.g., *.png, img_001, etc (Optional)")
        self.filename_field = OptionalField(
            "Filename pattern", self.filename_edit, start_open=False
        )
        form_layout.addRow(self.filename_field)

        # --- Input formats ---
        if self.dropdown:
            self.selected_formats = set()
            formats_layout = QVBoxLayout()
            btn_layout = QHBoxLayout()
            self.format_buttons = {}
            for fmt in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(fmt)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
                apply_shadow_effect(
                    btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3
                )
                btn.clicked.connect(
                    lambda checked, f=fmt: self.toggle_format(f, checked)
                )
                btn_layout.addWidget(btn)
                self.format_buttons[fmt] = btn
            formats_layout.addLayout(btn_layout)

            all_btn_layout = QHBoxLayout()
            self.btn_add_all = QPushButton("Add All")
            self.btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(
                self.btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )
            self.btn_add_all.clicked.connect(self.add_all_formats)

            self.btn_remove_all = QPushButton("Remove All")
            self.btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(
                self.btn_remove_all,
                color_hex="#000000",
                radius=8,
                x_offset=0,
                y_offset=3,
            )
            self.btn_remove_all.clicked.connect(self.remove_all_formats)

            all_btn_layout.addWidget(self.btn_add_all)
            all_btn_layout.addWidget(self.btn_remove_all)
            formats_layout.addLayout(all_btn_layout)

            formats_container = QWidget()
            formats_container.setLayout(formats_layout)
            self.formats_field = OptionalField(
                "Input formats", formats_container, start_open=False
            )
            form_layout.addRow(self.formats_field)
        else:
            self.input_formats_edit = QLineEdit()
            self.input_formats_edit.setPlaceholderText("e.g. jpg png gif (optional)")
            form_layout.addRow("Input formats:", self.input_formats_edit)

    def _build_tag_filters(self, form_layout: QFormLayout) -> None:
        # --- Tag Type Filter (checkable; all start checked) ---
        # --- Refresh Tags Button ---
        self.btn_refresh_tags = QPushButton("Refresh Tags")
        self.btn_refresh_tags.setFixedWidth(120)
        apply_shadow_effect(
            self.btn_refresh_tags, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_refresh_tags.clicked.connect(self._setup_tag_checkboxes)

        # --- Tag Type Filter (checkable; all start checked) ---
        self.tag_types_list_widget = QListWidget()
        self.tag_types_list_widget.setMinimumHeight(200)
        self.tag_types_list_widget.setStyleSheet(
            "QListWidget::item { padding: 4px; } "
            "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 8px; }"
        )
        self.tag_types_list_widget.itemChanged.connect(self._on_tag_type_changed)

        # --- Tags (List Widget) ---
        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setMinimumHeight(200)
        self.tags_list_widget.setStyleSheet(
            "QListWidget::item { padding: 5px; } "
            "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 8px; }"
        )

        # Containers for side-by-side Tag Types/Tags layout
        tags_container = QWidget()
        tags_layout = QHBoxLayout(tags_container)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(15)

        # Tag Types Column
        tag_types_col = QWidget()
        tag_types_col_layout = QVBoxLayout(tag_types_col)
        tag_types_col_layout.setContentsMargins(0, 0, 0, 0)

        tag_types_header_layout = QHBoxLayout()
        tag_types_label = QLabel("Tag Types:")
        tag_types_label.setStyleSheet("font-weight: bold;")
        tag_types_header_layout.addWidget(tag_types_label)
        tag_types_header_layout.addStretch()
        tag_types_header_layout.addWidget(self.btn_refresh_tags)

        tag_types_col_layout.addLayout(tag_types_header_layout)
        tag_types_col_layout.addWidget(self.tag_types_list_widget)

        # Tags Column
        tags_col = QWidget()
        tags_col_layout = QVBoxLayout(tags_col)
        tags_col_layout.setContentsMargins(0, 0, 0, 0)

        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet("font-weight: bold;")
        tags_col_layout.addWidget(tags_label)
        tags_col_layout.addWidget(self.tags_list_widget)

        tags_layout.addWidget(tag_types_col)
        tags_layout.addWidget(tags_col)

        form_layout.addRow(tags_container)

    def _build_search_button(self, layout: QVBoxLayout) -> None:
        # Search button
        self.search_button = QPushButton("Search Database")
        self.search_button.setStyleSheet(_SEARCH_BUTTON_STYLE)
        apply_shadow_effect(
            self.search_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.search_button.clicked.connect(self.toggle_search)
        layout.addWidget(self.search_button)

        # Progress Bar (for search query, not image loading)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Connect Enter key to search
        self.filename_edit.returnPressed.connect(self.toggle_search)
        if not self.dropdown:
            self.input_formats_edit.returnPressed.connect(self.toggle_search)

    def _build_galleries(self, layout: QVBoxLayout) -> None:
        # --- GALLERY AREA ---

        # 1. Search Results (Found Gallery) - Direct Layout
        results_header_layout = QHBoxLayout()

        # Title Label (Replacing GroupBox title)
        results_title_label = QLabel(
            "Search Results (Ctrl+A: Select All | Ctrl+D: Deselect All)"
        )
        results_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        results_header_layout.addWidget(results_title_label)

        results_header_layout.addStretch()

        self.results_count_label = QLabel("Not connected to database.")
        self.results_count_label.setStyleSheet("color: #aaa; font-style: italic;")
        results_header_layout.addWidget(self.results_count_label)

        layout.addLayout(results_header_layout)

        self.results_scroll = MarqueeScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setMinimumHeight(600)
        self.results_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        # Connect Marquee Selection
        self.results_scroll.selection_changed.connect(self.handle_marquee_selection)

        self.results_widget = QWidget()
        self.results_widget.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.results_layout = QGridLayout(self.results_widget)
        self.results_layout.setSpacing(3)
        self.results_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.results_scroll.setWidget(self.results_widget)

        # Add shared search input (Lazy Search) for Found Results
        layout.addWidget(self.found_search_input)

        # Add directly to main layout with stretch
        layout.addWidget(self.results_scroll, stretch=1)

        # Pagination Widget (Found)
        if hasattr(self, "found_pagination_widget"):
            layout.addWidget(
                self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        # 2. Selected Images Gallery - Direct Layout
        selected_header_layout = QHBoxLayout()
        selected_title_label = QLabel("Selected Images")
        selected_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        selected_header_layout.addWidget(selected_title_label)
        selected_header_layout.addStretch()
        layout.addLayout(selected_header_layout)

        self.selected_scroll = MarqueeScrollArea()
        self.selected_scroll.setWidgetResizable(True)
        self.selected_scroll.setMinimumHeight(400)
        self.selected_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )

        self.selected_widget_container = QWidget()
        self.selected_widget_container.setStyleSheet(
            "QWidget { background-color: #2c2f33; }"
        )
        self.selected_layout_grid = QGridLayout(self.selected_widget_container)
        self.selected_layout_grid.setSpacing(3)
        self.selected_layout_grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.selected_scroll.setWidget(self.selected_widget_container)

        # Add directly to main layout with stretch
        layout.addWidget(self.selected_scroll, stretch=1)

        # Pagination Widget (Selected)
        if hasattr(self, "selected_pagination_widget"):
            layout.addWidget(
                self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )


__all__ = ["_UIBuilderMixin"]
