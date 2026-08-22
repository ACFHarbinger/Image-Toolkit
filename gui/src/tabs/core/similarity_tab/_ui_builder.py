"""Full UI construction for ``SimilarityTab``.

Extracted from ``SimilarityTab.__init__`` -- pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.src.constants.elements import _SHARED_BUTTON_STYLE

from ....components import OptionalField, VirtualDualGallery
from ....styles import apply_shadow_effect


class _UIBuilderMixin:
    """Builds the directories/settings groups, both galleries, and action buttons."""

    def _build_ui(self):
        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        settings_layout = self._build_directories_and_settings(content_layout)
        self._build_galleries(content_layout)
        self._build_extension_filter(settings_layout)
        self._build_delete_buttons(content_layout)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)
        self.setLayout(main_layout)
        self.clear_galleries()

    def _build_directories_and_settings(self, content_layout) -> QFormLayout:
        # --- 1. Directories Group (Source [required] + Target [optional]) ---
        # Mapping to the engine (kept stable so the inherited delete/list logic
        # keeps working): ``self.target_path`` is the SOURCE — the primary,
        # obligatory directory that is listed, scanned and whose duplicates get
        # selected/deleted (engine.target_dir). ``self.reference_path`` is the
        # optional TARGET — a second corpus to compare against; its files are
        # protected keepers (engine.reference_dir). If the Target is empty the
        # search runs within the Source directory alone.
        from gui.src.windows.settings.app_settings import AppSettings

        target_group = QGroupBox("Directories")
        target_layout = QFormLayout(target_group)

        # Source (required): the directory of images to search / de-duplicate.
        browse_layout = QHBoxLayout()
        self.target_path = QLineEdit()
        self.target_path.setPlaceholderText("Source directory to search (required)...")
        self.target_path.returnPressed.connect(self.browse_and_populate)
        browse_layout.addWidget(self.target_path)
        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        browse_layout.addWidget(btn_browse_scan)
        target_layout.addRow("Source path (required):", browse_layout)

        # Target (optional): a second directory to compare the Source against.
        # Its files are protected keepers in cross-directory de-duplication.
        ref_layout = QHBoxLayout()
        self.reference_path = QLineEdit()
        self.reference_path.setPlaceholderText(
            "Optional — compare Source against another directory (leave empty to "
            "search within Source)...")
        ref_layout.addWidget(self.reference_path)
        btn_browse_ref = QPushButton("Browse...")
        btn_browse_ref.clicked.connect(self.browse_reference_directory)
        apply_shadow_effect(btn_browse_ref, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        ref_layout.addWidget(btn_browse_ref)
        btn_clear_ref = QPushButton("Clear")
        btn_clear_ref.clicked.connect(self._clear_reference_widget)
        ref_layout.addWidget(btn_clear_ref)
        target_layout.addRow("Target path (optional):", ref_layout)

        # Recurse into subdirectories of both Source and Target.
        self.recursive_check = QCheckBox("Include subdirectories (recursive)")
        self.recursive_check.setChecked(AppSettings.recursive_scan())
        target_layout.addRow("", self.recursive_check)
        content_layout.addWidget(target_group)

        # --- 2. Options Group ---
        settings_group = QGroupBox("Scan Settings")
        settings_layout = QFormLayout(settings_group)

        self.scan_method_combo = QComboBox()
        self.scan_method_combo.addItems(
            [
                "Similarity Engine (tiered clusters)",
                "All Files (List Directory Contents)",
                "Exact Match (Same File - Fastest)",
                "Similar: Perceptual Hash (Resized/Color Edits - Fast)",
                "Similar: ORB Feature Matching (Cropped/Rotated - Medium)",
                "Similar: SIFT Feature Matching (Robust - Slow)",
                "Similar: SSIM (High Quality - Slowest)",
            ]
        )
        settings_layout.addRow("Scan Method:", self.scan_method_combo)

        scan_btn_row = QHBoxLayout()
        # Single button: runs the scan when idle, cancels it while running.
        self._scan_label = "🔍 Scan for Similar Images"
        self._cancel_label = "✖ Cancel Scan"
        self.btn_scan = QPushButton(self._scan_label)
        self.btn_scan.setStyleSheet(
            "QPushButton {  color: white; font-weight: bold; "
            "padding: 10px; border-radius: 8px; } QPushButton:hover {  }")
        apply_shadow_effect(self.btn_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_scan.clicked.connect(self.on_scan_button_clicked)
        scan_btn_row.addWidget(self.btn_scan)
        # Reset/Clear: re-display the whole Source directory after a scan filters
        # the gallery down to just the similar images.
        self.btn_reset = QPushButton("🔄 Reset / Show All")
        self.btn_reset.setStyleSheet(
            "QPushButton {  color: white; font-weight: bold; "
            "padding: 10px; border-radius: 8px; } QPushButton:hover {  }")
        apply_shadow_effect(self.btn_reset, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_reset.clicked.connect(self.reset_gallery)
        scan_btn_row.addWidget(self.btn_reset)
        settings_layout.addRow(scan_btn_row)
        content_layout.addWidget(settings_group)

        return settings_layout

    def _build_galleries(self, content_layout) -> None:
        # --- 3. Galleries ---
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setRange(0, 0)
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # A. Found + Selected galleries (virtual-scroll, GUI/UX §2.1 Option A).
        # Replaces the two MarqueeScrollArea + QGridLayout grids; pagination is
        # dropped and selection lives in the dual gallery's selection models.
        self.dual = VirtualDualGallery(self)
        self.dual.found_activated.connect(self._open_preview_for)
        self.dual.found_right_clicked.connect(self._on_found_card_right_clicked)
        self.dual.selected_activated.connect(self._open_preview_for)
        self.dual.selected_right_clicked.connect(self._on_found_card_right_clicked)
        self.dual.selection_changed.connect(self._sync_selection_from_dual)
        content_layout.addWidget(self.dual, 1)

        # Actions for duplicates
        dup_actions_layout = QHBoxLayout()
        self.btn_compare_properties = QPushButton("Compare Properties (0)")
        apply_shadow_effect(self.btn_compare_properties, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_compare_properties.clicked.connect(self.show_comparison_dialog)
        self.btn_compare_properties.setVisible(False)
        dup_actions_layout.addWidget(self.btn_compare_properties)
        self.btn_delete_selected_dups = QPushButton("Delete Selected Duplicates")
        self.btn_delete_selected_dups.setVisible(False)
        content_layout.addLayout(dup_actions_layout)

    def _build_extension_filter(self, settings_layout: QFormLayout) -> None:
        # Extension filter
        self.selected_extensions: "set[str] | None" = None
        if self.dropdown:
            self.selected_extensions = set()
            ext_layout = QVBoxLayout()
            btn_layout = QHBoxLayout()
            self.extension_buttons = {}
            for ext in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(ext)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover {  }")
                apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
                btn.clicked.connect(lambda checked, e=ext: self.toggle_extension(e, checked))
                btn_layout.addWidget(btn)
                self.extension_buttons[ext] = btn
            ext_layout.addLayout(btn_layout)
            all_btn_layout = QHBoxLayout()
            btn_add_all = QPushButton("Add All")
            btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_add_all.clicked.connect(self.add_all_extensions)
            btn_remove_all = QPushButton("Remove All")
            btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(btn_remove_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_remove_all.clicked.connect(self.remove_all_extensions)
            all_btn_layout.addWidget(btn_add_all)
            all_btn_layout.addWidget(btn_remove_all)
            ext_layout.addLayout(all_btn_layout)
            ext_container = QWidget()
            ext_container.setLayout(ext_layout)
            self.extensions_field = OptionalField("Target extensions", ext_container, start_open=False)
            settings_layout.addRow(self.extensions_field)
        else:
            self.target_extensions = QLineEdit()
            self.target_extensions.setPlaceholderText("e.g. .txt .jpg or txt jpg")
            settings_layout.addRow("Target extensions (optional):", self.target_extensions)

        self.confirm_checkbox = QCheckBox("Require confirmation before delete (recommended)")
        self.confirm_checkbox.setChecked(True)
        settings_layout.addRow(self.confirm_checkbox)

    def _build_delete_buttons(self, content_layout) -> None:
        # --- 4. Standard Delete Buttons ---
        content_layout.addStretch(1)
        run_buttons_layout = QHBoxLayout()
        self.btn_delete_files = QPushButton("Delete Selected Files (0)")
        self.btn_delete_files.setStyleSheet(_SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_files.clicked.connect(self.delete_selected_duplicates)
        self.btn_delete_files.setEnabled(False)

        self.btn_delete_directory = QPushButton("Delete Directory and Contents")
        self.btn_delete_directory.setStyleSheet(_SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_directory, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_directory.clicked.connect(lambda: self.start_deletion(mode="directory"))

        run_buttons_layout.addWidget(self.btn_delete_directory)
        run_buttons_layout.addWidget(self.btn_delete_files)
        content_layout.addLayout(run_buttons_layout)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.status_label)


__all__ = ["_UIBuilderMixin"]
