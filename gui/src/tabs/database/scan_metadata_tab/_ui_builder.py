"""Full UI construction for ``ScanMetadataTab``.

Extracted from ``ScanMetadataTab.__init__`` -- pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

import contextlib
import os

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ....components import MarqueeScrollArea
from ....styles import apply_shadow_effect


class _UIBuilderMixin:
    """Builds the scan-directory bar, both galleries, metadata group, and action buttons."""

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Scrollable Content Setup ---
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._build_scan_directory_section(content_layout)
        self._build_scan_gallery_section(content_layout)
        self._build_selected_gallery_section(content_layout)
        self._build_metadata_group(content_layout)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll, 1)

        self._build_action_buttons(main_layout)

        self.setLayout(main_layout)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.update_button_states(connected=False)
        self.populate_selected_images_gallery()

    def _build_scan_directory_section(self, content_layout) -> None:
        scan_group = QGroupBox("Scan Directory")
        scan_layout = QVBoxLayout()
        scan_layout.setContentsMargins(10, 20, 10, 10)

        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan...")
        self.scan_directory_path.returnPressed.connect(
            self.handle_scan_directory_return
        )

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )

        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        scan_layout.addLayout(scan_dir_layout)
        scan_group.setLayout(scan_layout)
        content_layout.addWidget(scan_group)
        try:
            self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
        except Exception:
            self.last_browsed_scan_dir = os.getcwd()

    def _build_scan_gallery_section(self, content_layout) -> None:
        # A. Top Gallery: Scan Results
        self.scan_scroll_area = MarqueeScrollArea()
        self.scan_scroll_area.setWidgetResizable(True)
        self.scan_scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.scan_scroll_area.setMinimumHeight(600)

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet("background-color: #2c2f33;")
        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        self.scan_scroll_area.setWidget(self.scan_thumbnail_widget)
        self.scan_scroll_area.selection_changed.connect(self.handle_marquee_selection)

        # Connect Scroll Bar for Lazy Loading
        self.scan_scroll_area.verticalScrollBar().valueChanged.connect(
            self._on_scroll_event
        )

        # Scan Pagination Controls
        (
            self.scan_pag_widget,
            self.scan_pag_combo,
            self.scan_pag_prev,
            self.scan_pag_next,
            self.scan_pag_btn,
        ) = self._create_pagination_controls("scan")

        # Add shared search input (Lazy Search) for Scan Results
        content_layout.addWidget(self.found_search_input)

        content_layout.addWidget(self.scan_scroll_area, 1)
        # Fix: Add alignment flag to center the widget itself
        content_layout.addWidget(self.scan_pag_widget, 0, Qt.AlignmentFlag.AlignCenter)

    def _build_selected_gallery_section(self, content_layout) -> None:
        # B. Bottom Gallery: Selected Images
        self.selected_images_area = MarqueeScrollArea()
        self.selected_images_area.setWidgetResizable(True)
        self.selected_images_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_images_area.setMinimumHeight(400)
        self.selected_images_area.setVisible(True)
        self.selected_images_area.selection_changed.connect(
            self.handle_marquee_selection
        )

        self.selected_images_widget = QWidget()
        self.selected_images_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_grid_layout = QGridLayout(self.selected_images_widget)
        self.selected_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        self.selected_images_area.setWidget(self.selected_images_widget)

        # Selected Pagination Controls
        (
            self.sel_pag_widget,
            self.sel_pag_combo,
            self.sel_pag_prev,
            self.sel_pag_next,
            self.sel_pag_btn,
        ) = self._create_pagination_controls("selected")

        content_layout.addWidget(self.selected_images_area, 1)
        # Fix: Add alignment flag to center the widget itself
        content_layout.addWidget(self.sel_pag_widget, 0, Qt.AlignmentFlag.AlignCenter)

    def _build_metadata_group(self, content_layout) -> None:
        # --- Metadata Group Box ---
        self.metadata_group = QGroupBox(
            "Batch Metadata (Applies to ALL Selected Images)"
        )
        self.metadata_group.setVisible(False)
        metadata_vbox = QVBoxLayout(self.metadata_group)

        form_layout = QFormLayout()

        group_layout = QHBoxLayout()
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setPlaceholderText("Enter or select Group/Series name...")
        # pyrefly: ignore [missing-attribute]
        self.group_combo.lineEdit().returnPressed.connect(
            lambda: self.upsert_button.click()
        )
        group_layout.addWidget(self.group_combo)
        form_layout.addRow("Group Name:", group_layout)

        subgroup_layout = QHBoxLayout()
        self.subgroup_combo = QComboBox()
        self.subgroup_combo.setEditable(True)
        self.subgroup_combo.setPlaceholderText("Enter or select Subgroup name...")
        # pyrefly: ignore [missing-attribute]
        self.subgroup_combo.lineEdit().returnPressed.connect(
            lambda: self.upsert_button.click()
        )
        subgroup_layout.addWidget(self.subgroup_combo)
        form_layout.addRow("Subgroup Name:", subgroup_layout)

        self.tags_list_widget = QListWidget()
        self.tags_list_widget.setMinimumHeight(400)
        self.tags_list_widget.setStyleSheet(
            "QListWidget::item { padding: 5px; } "
            "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 8px; }"
        )
        self._setup_tag_checkboxes()

        form_layout.addRow("Tags:", self.tags_list_widget)
        metadata_vbox.addLayout(form_layout)
        content_layout.addWidget(self.metadata_group)

    def _build_action_buttons(self, main_layout) -> None:
        self.view_new_only_button = QPushButton("👁️ Show Only New (Not in DB)")
        self.view_new_only_button.setCheckable(True)
        self.view_new_only_button.setChecked(False)
        apply_shadow_effect(
            self.view_new_only_button,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.view_new_only_button.toggled.connect(self.toggle_new_only_view)

        self.view_in_db_only_button = QPushButton("💾 Show Only In DB")
        self.view_in_db_only_button.setCheckable(True)
        self.view_in_db_only_button.setChecked(False)
        apply_shadow_effect(
            self.view_in_db_only_button,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.view_in_db_only_button.toggled.connect(self.toggle_in_db_only_view)

        self.upsert_button = QPushButton("Add/Update Database Data")
        self.upsert_button.setStyleSheet(
            "background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;"
        )
        apply_shadow_effect(
            self.upsert_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.upsert_button.clicked.connect(self.perform_upsert_operation)

        self.delete_selected_button = QPushButton("Delete Images Data from Database")
        self.delete_selected_button.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; padding: 10px;"
        )
        apply_shadow_effect(
            self.delete_selected_button,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.delete_selected_button.clicked.connect(self.delete_selected_images)

        scan_action_layout = QHBoxLayout()
        scan_action_layout.addWidget(self.view_new_only_button)
        scan_action_layout.addWidget(self.view_in_db_only_button)
        scan_action_layout.addWidget(self.upsert_button)
        scan_action_layout.addWidget(self.delete_selected_button)

        main_layout.addLayout(scan_action_layout)

    def _create_pagination_controls(self, prefix: str):
        # Use the common method from AbstractClassTwoGalleries to ensure consistent styling
        container, controls = self.common_create_pagination_ui()

        # Center alignment: Explicitly set horizontal center alignment
        if container.layout():
            container.layout().setAlignment(Qt.AlignmentFlag.AlignHCenter)  # pyrefly: ignore [missing-attribute]

        combo = controls["combo"]
        btn_prev = controls["btn_prev"]
        btn_next = controls["btn_next"]
        btn_page = controls["btn_page"]

        # FIX: Force the button to display as a dropdown (InstantPopup style).
        # We also set a dummy menu immediately. This forces the UI to render the
        # dropdown arrow and reserve the correct spacing/size even before data is loaded.
        with contextlib.suppress(AttributeError):
            btn_page.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)  # pyrefly: ignore [missing-attribute]

        # Explicitly attaching a menu ensures the arrow style appears
        btn_page.setMenu(QMenu(self))

        # Set default values
        combo.setCurrentText("100")

        # Connect signals locally
        if prefix == "scan":
            combo.currentTextChanged.connect(self._on_scan_page_size_changed)
            btn_prev.clicked.connect(self._on_scan_prev)
            btn_next.clicked.connect(self._on_scan_next)
            # The page button uses a menu, managed in _update_pagination_ui
        else:
            combo.currentTextChanged.connect(self._on_sel_page_size_changed)
            btn_prev.clicked.connect(self._on_sel_prev)
            btn_next.clicked.connect(self._on_sel_next)

        return container, combo, btn_prev, btn_next, btn_page


__all__ = ["_UIBuilderMixin"]
