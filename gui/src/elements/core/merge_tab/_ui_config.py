"""Input/output/merge-settings UI section builder for ``MergeTab``.

Extracted from ``MergeTab.__init__`` -- pure code motion, no logic change,
to keep the file under the codebase's 500-code-line convention (§5.17).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ....styles import apply_shadow_effect


class _UIConfigMixin:
    """Builds the Input/Output/Merge-Settings config sections."""

    def _build_input_output_sections(self, content_layout) -> None:
        # === 1. Input Configuration ===
        target_group = QGroupBox("Input Configuration")
        target_layout = QFormLayout(target_group)

        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText(
            "Path to directory containing images for merging…"
        )
        self.scan_directory_path.returnPressed.connect(
            self.handle_scan_directory_return
        )
        btn_browse_scan = QPushButton("Browse Input…")
        btn_browse_scan.clicked.connect(self.browse_and_scan_directory)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        target_layout.addRow("Input path:", scan_dir_layout)
        content_layout.addWidget(target_group)

        # === 2. Output Configuration ===
        output_group = QGroupBox("Output Configuration")
        output_layout = QFormLayout(output_group)

        out_dir_layout = QHBoxLayout()
        self.output_directory_path = QLineEdit()
        self.output_directory_path.setPlaceholderText(
            "(Optional) Select output folder. If empty, you will be prompted to save after merge."
        )
        self.output_directory_path.textChanged.connect(self._update_output_dir_state)
        btn_browse_out = QPushButton("Browse Output…")
        btn_browse_out.clicked.connect(self.browse_output_directory)
        apply_shadow_effect(
            btn_browse_out, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        out_dir_layout.addWidget(self.output_directory_path)
        out_dir_layout.addWidget(btn_browse_out)
        output_layout.addRow("Output Folder:", out_dir_layout)

        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText(
            "merged_image (Extension added automatically)"
        )
        output_layout.addRow("Filename:", self.output_filename_input)
        content_layout.addWidget(output_group)

    def _build_merge_settings_section(self, content_layout) -> None:
        # === 3. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        self.direction.addItems(
            [
                "canvas",
                "horizontal",
                "vertical",
                "grid",
                "panorama",
                "sequential",
                "gif",
            ]
        )
        self.direction.currentTextChanged.connect(self.handle_direction_change)
        config_layout.addRow("Mode:", self.direction)

        self.lbl_spacing = QLabel("Spacing (px):")
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow(self.lbl_spacing, self.spacing)

        self.lbl_align = QLabel("Alignment/Resize:")
        self.align_mode = QComboBox()
        self.align_mode.addItems(
            [
                "Default (Top/Center)",
                "Align Top/Left",
                "Align Bottom/Right",
                "Center",
                "Scaled (Grow Smallest)",
                "Squish (Shrink Largest)",
            ]
        )
        config_layout.addRow(self.lbl_align, self.align_mode)

        self.lbl_duration = QLabel("Duration (ms/frame):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 10000)
        self.duration_spin.setValue(500)
        self.duration_spin.setSingleStep(50)
        config_layout.addRow(self.lbl_duration, self.duration_spin)
        self.lbl_duration.hide()
        self.duration_spin.hide()

        self.grid_group = QGroupBox("Grid Size")
        grid_layout = QHBoxLayout()
        self.grid_rows = QSpinBox()
        self.grid_rows.setRange(1, 100)
        self.grid_cols = QSpinBox()
        self.grid_cols.setRange(1, 100)
        grid_layout.addWidget(QLabel("Rows:"))
        grid_layout.addWidget(self.grid_rows)
        grid_layout.addWidget(QLabel("Cols:"))
        grid_layout.addWidget(self.grid_cols)
        self.grid_group.setLayout(grid_layout)
        config_layout.addRow(self.grid_group)
        self.grid_group.hide()

        self._build_engine_options(config_layout)

        self.engine_combo.currentIndexChanged.connect(self._update_engine_visibility)
        content_layout.addWidget(config_group)

    def _build_engine_options(self, config_layout) -> None:
        """Panorama-engine picker + per-engine options groups (OpenCV/Hugin/Overmix/ASP)."""
        # --- Panorama Engine Settings ---
        self.lbl_engine = QLabel("Engine:")
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("OpenCV", "opencv")
        self.engine_combo.addItem("Hugin Toolchain", "hugin")
        self.engine_combo.addItem("Overmix", "overmix")
        self.engine_combo.addItem("Anime Stitch Pipeline", "asp")
        self.engine_combo.setToolTip(
            "OpenCV: Stitcher (Panorama/SCANS modes)\n"
            "Hugin Toolchain: pto_gen/cpfind/autooptimiser/nona/enblend (system hugin-tools)\n"
            "Overmix: external Overmix CLI (recursive align + average/statistics render)\n"
            "Anime Stitch Pipeline: BiRefNet + LoFTR + ECC full research pipeline"
        )
        config_layout.addRow(self.lbl_engine, self.engine_combo)

        # OpenCV engine options
        self.opencv_group = QGroupBox("OpenCV Options")
        opencv_layout = QFormLayout(self.opencv_group)
        self.opencv_stitcher_mode_combo = QComboBox()
        self.opencv_stitcher_mode_combo.addItem("0 — Panorama", 0)
        self.opencv_stitcher_mode_combo.addItem("1 — SCANS", 1)
        self.opencv_stitcher_mode_combo.setToolTip(
            "Panorama: rotating-camera/perspective transform.\n"
            "SCANS: affine/flat — small pan shots, near-duplicate frames."
        )
        opencv_layout.addRow("Stitcher mode:", self.opencv_stitcher_mode_combo)
        self.opencv_registration_resol_spin = QDoubleSpinBox()
        self.opencv_registration_resol_spin.setRange(0.1, 1.0)
        self.opencv_registration_resol_spin.setSingleStep(0.05)
        self.opencv_registration_resol_spin.setValue(0.6)
        self.opencv_registration_resol_spin.setToolTip(
            "Keypoint registration resolution. Higher finds more keypoints — "
            "helps with small-overlap or near-duplicate frames."
        )
        opencv_layout.addRow("Registration resolution:", self.opencv_registration_resol_spin)
        config_layout.addRow(self.opencv_group)

        # Hugin engine options
        self.hugin_group = QGroupBox("Hugin Options")
        hugin_layout = QFormLayout(self.hugin_group)
        self.hugin_projection_combo = QComboBox()
        self.hugin_projection_combo.addItem("Rectilinear", 0)
        self.hugin_projection_combo.addItem("Cylindrical", 1)
        self.hugin_projection_combo.addItem("Equirectangular", 2)
        hugin_layout.addRow("Projection:", self.hugin_projection_combo)
        self.hugin_linear_match_checkbox = QCheckBox("Linear sequence matching")
        self.hugin_linear_match_checkbox.setChecked(True)
        self.hugin_linear_match_checkbox.setToolTip(
            "cpfind --linearmatch — for a scrolling pan/scan sequence. "
            "Uncheck for a rotating-camera panorama (--multirow)."
        )
        hugin_layout.addRow(self.hugin_linear_match_checkbox)
        config_layout.addRow(self.hugin_group)

        # Overmix engine options
        self.overmix_group = QGroupBox("Overmix Options")
        overmix_layout = QFormLayout(self.overmix_group)
        self.overmix_aligner_combo = QComboBox()
        self.overmix_aligner_combo.addItems(["Recursive", "Average", "Linear"])
        overmix_layout.addRow("Aligner:", self.overmix_aligner_combo)
        self.overmix_render_combo = QComboBox()
        self.overmix_render_combo.addItems(["average", "median", "min", "max", "difference"])
        self.overmix_render_combo.setToolTip(
            "average: Overmix's dedicated average render.\n"
            "median/min/max/difference: statistics render."
        )
        overmix_layout.addRow("Render statistic:", self.overmix_render_combo)
        config_layout.addRow(self.overmix_group)

        # Anime Stitch Pipeline engine options
        self.ai_options_group = QGroupBox("Anime Stitch Pipeline Options")
        ai_layout = QVBoxLayout()

        self.use_birefnet_checkbox = QCheckBox("Character-Aware Seams (BiRefNet)")
        self.use_birefnet_checkbox.setChecked(True)

        self.renderer_combo = QComboBox()
        self.renderer_combo.addItems(["blend", "median", "first"])
        self.renderer_combo.setToolTip(
            "blend: Multi-band seamless (robust)\nmedian: Temporal denoising (sharpest)\nfirst: No blending (fast)"
        )

        self.use_basic_checkbox = QCheckBox("Use BaSiC (Luma Correction)")
        self.use_basic_checkbox.setChecked(True)
        self.use_loftr_checkbox = QCheckBox("Use LoFTR (Dense Matching)")
        self.use_loftr_checkbox.setChecked(True)
        self.use_ecc_checkbox = QCheckBox("Use ECC (Sub-pixel Align)")
        self.use_ecc_checkbox.setChecked(True)
        self.composite_fg_checkbox = QCheckBox("Composite Foreground")
        self.composite_fg_checkbox.setChecked(True)

        self.motion_model_combo = QComboBox()
        self.motion_model_combo.addItem("Translation", "translation")
        self.motion_model_combo.addItem("Affine 4-DOF", "affine")

        self.lbl_edge_crop = QLabel("Edge Crop (px):")
        self.edge_crop_spinbox = QSpinBox()
        self.edge_crop_spinbox.setRange(0, 500)
        self.edge_crop_spinbox.setValue(30)
        self.edge_crop_spinbox.setToolTip(
            "Crops left/right edges to neutralize vignettes before stitching."
        )

        self.lbl_pyramid_levels = QLabel("Pyramid Levels:")
        self.pyramid_levels_spinbox = QSpinBox()
        self.pyramid_levels_spinbox.setRange(1, 12)
        self.pyramid_levels_spinbox.setValue(8)
        self.pyramid_levels_spinbox.setToolTip(
            "Number of Laplacian bands used for the multi-band seam blend."
        )

        ai_layout.addWidget(QLabel("Renderer:"))
        ai_layout.addWidget(self.renderer_combo)
        ai_layout.addWidget(QLabel("Motion model:"))
        ai_layout.addWidget(self.motion_model_combo)
        ai_layout.addWidget(self.use_basic_checkbox)
        ai_layout.addWidget(self.use_loftr_checkbox)
        ai_layout.addWidget(self.use_ecc_checkbox)
        ai_layout.addWidget(self.composite_fg_checkbox)
        ai_layout.addWidget(self.use_birefnet_checkbox)
        ai_form = QFormLayout()
        ai_form.addRow(self.lbl_edge_crop, self.edge_crop_spinbox)
        ai_form.addRow(self.lbl_pyramid_levels, self.pyramid_levels_spinbox)
        ai_layout.addLayout(ai_form)

        self.ai_options_group.setLayout(ai_layout)
        config_layout.addRow(self.ai_options_group)


__all__ = ["_UIConfigMixin"]
