"""Advanced configuration dialog for Anime Stitch Pipeline (ASP).

Exposes the full schema of registered ``ASP_*`` configuration parameters
(73 keys) with a clean 20-key primary curated profile surface and expandable
category drawers, live type/bound validation, preset profiles, and JSON/TOML export.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# Canonical 20-flag primary curated profile keys (M2 surface)
PRIMARY_CURATED_KEYS = [
    "ASP_HOLD_THRESHOLD",
    "ASP_HOLD_DHASH_THRESH",
    "ASP_BLUR_REJECT_THRESH",
    "ASP_VIDEO_PROXY_SCALE",
    "ASP_USE_SAM2",
    "ASP_LOFTR_BG_RATIO_MIN",
    "ASP_SIMILARITY_MODE",
    "ASP_ALIGN_GATE_DX",
    "ASP_BA_F_SCALE",
    "ASP_FG_REGISTER",
    "ASP_FLOW_ENGINE",
    "ASP_ARAP_PUSH",
    "ASP_FG_EXCLUDE_MEDIAN",
    "ASP_ADAPTIVE_RENDER_GAIN",
    "ASP_MASKED_MEDIAN",
    "ASP_COV_MIN_MULTI_PCT",
    "ASP_PHASE_COMPOSITE",
    "ASP_BLOCKS_GAIN_COMP",
    "ASP_JOINT_GAIN_SOLVE",
    "ASP_SP_SOFT_PX",
]

# Fallback schema if submodule ASP config is not directly importable
_FALLBACK_SCHEMA: dict[str, tuple] = {
    # Frame selection
    "ASP_HOLD_THRESHOLD": (float, 0.0, 1.0, "MAD hold-detection threshold [0, 1]"),
    "ASP_HOLD_DHASH_THRESH": (int, 0, 64, "dHash Hamming floor for hold detection (0=off)"),
    "ASP_DHASH_EXACT_DROP": (int, 0, 1, "Drop exact dHash duplicates before selection"),
    "ASP_HIGH_HOLD_RESPONSE": (float, 0.0, 1.0, "phaseCorrelate response floor for hold merge"),
    "ASP_HOLD_AVERAGE": (int, 0, 1, "Overmix-style ECC sub-pixel averaging within hold blocks"),
    "ASP_HOLD_BG_SUB": (int, 0, 1, "EXPERIMENTAL, default-off: unaligned-median background plate for hold detection; not validated under camera pan (M4 owns keep/delete)"),
    "ASP_BLUR_REJECT_THRESH": (float, 0.0, None, "Laplacian-variance floor for blurry-frame rejection (0=off)"),
    "ASP_CONTRAST_THRESH": (float, 0.0, None, "Pixel-std floor for low-contrast frame rejection (0=off)"),
    "ASP_NEAR_DUP_LUMA": (float, 0.0, 255.0, "Near-dup luma dedup ceiling (0=off)"),
    "ASP_TEMPORAL_VAR_THRESH": (float, 0.0, 1.0, "Static-frame temporal variance floor (0=off)"),
    "ASP_OTSU_BG_CORR": (int, 0, 1, "Per-pair Otsu bg mask for phase correlation"),
    "ASP_TWO_CHANNEL_SELECT": (int, 0, 1, "BiRefNet two-channel camera/animation selection (experimental)"),
    "ASP_POSE_WINDOW_PX": (int, 0, None, "DINOv2 pose-consistent selection window (0=off, experimental)"),
    "ASP_PHASE_AWARE_SELECT": (int, 0, 1, "§2.4 Pass-2 bias toward same-phase candidates"),
    "ASP_PHASE_CROSS_PENALTY": (float, 0.0, 1.0, "§2.4 tie-break penalty applied to cross-phase candidate"),
    # Video ingestion
    "ASP_VIDEO_MAX_FRAMES": (int, 1, None, "Max frames decoded from a video input"),
    "ASP_VIDEO_PROXY_SCALE": (float, 0.05, 1.0, "Proxy decode scale for selection pass"),
    "ASP_VIDEO_TELECINE_MAD": (float, 0.0, None, "Telecine duplicate MAD threshold"),
    "ASP_VIDEO_KEYFRAMES_ONLY": (int, 0, 1, "Decode only keyframes in proxy pass"),
    # Masking
    "ASP_USE_SAM2": (int, 0, 1, "Use SAM-2 video predictor instead of BiRefNet"),
    # Matching / alignment
    "ASP_MATCH_SPREAD_CEIL": (float, 0.0, None, "Max MAD of per-match displacements (0=off)"),
    "ASP_LOFTR_BG_RATIO_MIN": (float, 0.0, 1.0, "Min fraction of LoFTR matches on background (0=off)"),
    "ASP_SIMILARITY_MODE": (int, 0, 1, "4-DOF similarity constraint for per-pair affines"),
    "ASP_ALIGN_GATE_DX": (float, 0.0, None, "75th-pct |dx| gate for vertical-scroll alignment"),
    "ASP_BA_F_SCALE": (float, 0.0, None, "Cauchy loss f_scale (px) in bundle adjustment"),
    "ASP_GNC_OUTER": (int, 1, 32, "GNC outer continuation iterations in BA"),
    "ASP_DY_CV_MAX": (float, 0.0, None, "dy_cv gate: SCANS fallback above this step-CV (0=off)"),
    # Foreground registration
    "ASP_FG_REGISTER": (int, 0, 1, "Enable Stage 8.5 foreground pose registration"),
    "ASP_FLOW_ENGINE": (str, None, None, "Dense flow engine: searaft | dis"),
    "ASP_ARAP_PUSH": (int, 0, 1, "ARAP Push phase before Regularise"),
    "ASP_FG_MAX_RESIDUAL": (float, 0.0, None, "Max animation residual (px) to warp; above → single-pose"),
    # Rendering
    "ASP_FG_EXCLUDE_MEDIAN": (int, 0, 1, "Foreground-excluded temporal median (A5)"),
    "ASP_BG_AVERAGE": (int, 0, 1, "Overmix-style mean/median blend for confirmed-bg samples"),
    "ASP_BG_AVERAGE_FULL_AT": (int, 3, None, "Sample count for full mean weight"),
    "ASP_MASKED_MEDIAN": (int, 0, 1, "Leave always-fg pixels black instead of ghost-averaging"),
    "ASP_ADAPTIVE_RENDER_GAIN": (int, 0, 1, "Adaptive gain clamp in sequential render normalisation"),
    "ASP_GAIN_DRIFT_MAX": (float, 0.0, None, "Max cumulative gain fold-change before reset (0=off)"),
    "ASP_GPU_MEDIAN": (int, 0, 1, "GPU temporal median via base (UMat)"),
    "ASP_COV_MIN_MULTI_PCT": (float, 0.0, 1.0, "Min multi-frame canvas coverage before SCANS fallback"),
    # Compositing
    "ASP_PHASE_COMPOSITE": (int, 0, 1, "Phase-consistent compositing: escalate to single-pose at boundaries"),
    "ASP_COHERENCE_V2": (int, 0, 1, "M3 default-off §9.2 Stage 2 compositor candidate: one pose per foreground overlap region; not wired into the live seam loop"),
    "ASP_GRAPHCUT_SEAM": (int, 0, 1, "GraphCut global multi-image seam"),
    "ASP_GC_FEATHER_PX": (int, 0, None, "Feather width at GraphCut ownership boundaries"),
    "ASP_BLOCKS_GAIN_COMP": (int, 0, 1, "32×32 blocks BGR gain compensation in blend zones"),
    "ASP_BLOCKS_LUM_COMP": (int, 0, 1, "LAB-L blocks gain compensation in blend zones"),
    "ASP_GLOBAL_GAIN_COMP": (int, 0, 1, "Pre-seam sequential global gain equalization"),
    "ASP_JOINT_GAIN_SOLVE": (int, 0, 1, "Brown-Lowe joint gain solve"),
    "ASP_JOINT_GAIN_SIGMA_N": (float, 0.01, None, "Joint gain solve noise sigma"),
    "ASP_JOINT_GAIN_SIGMA_G": (float, 0.001, None, "Joint gain solve gain-prior sigma"),
    "ASP_JOINT_GAIN_ROBUST": (int, 0, 1, "Reject isolated overlap ratios before joint solve"),
    "ASP_SP_SOFT_PX": (int, 0, None, "Single-pose soft-edge half-width (px)"),
    "ASP_BG_NORM_MIN_PX": (int, 0, None, "Min bg pixels for normalisation gain estimate"),
    "ASP_POST_SEAM_WARN_THRESH": (float, 0.0, None, "Post-composite seam lum-step warning threshold"),
    # C++ acceleration
    "ASP_BATCH_GPU": (int, 0, 1, "GPU dispatch for C++ base kernels"),
    # Bundle adjustment
    "ASP_ST_INLIER_THRESHOLD": (float, 0.0, None, "Max allowed disagreement (px) vs spanning-tree reference"),
    # Affine validation
    "ASP_ROT_TIGHT": (float, 0.0, None, "Tight rotation threshold (high variance)"),
    "ASP_ROT_LOOSE": (float, 0.0, None, "Loose rotation threshold (near-identical rotation)"),
    "ASP_SC_TIGHT": (float, 0.0, None, "Tight scale threshold (high variance)"),
    "ASP_SC_LOOSE": (float, 0.0, None, "Loose scale threshold (near-identical scale)"),
    "ASP_MONO_TAU_MIN": (float, 0.0, 1.0, "Min |Kendall tau| for translation monotonicity"),
    "ASP_ROT_SCALE_CONSISTENCY_THRESH": (float, 0.0, None, "Consistency threshold for adaptive tight/loose"),
    # Frame selection: hold / pose refinement
    "ASP_MAX_SKIPPABLE_HOLD_SIZE": (int, 1, None, "Max hold-block size (frames) for animation hold"),
    "ASP_POSE_REFINE_LOOK_RANGE": (int, 0, None, "Pass-2 pose refinement search window (+-N slots)"),
    "ASP_POSE_REFINE_MIN_GAIN": (float, 0.0, 1.0, "Min similarity improvement to swap candidates"),
    "ASP_POSE_REFINE_MIN_ADV_FRAC": (float, 0.0, None, "Min frame-advance fraction constraint"),
    "ASP_POSE_REFINE_MAX_ADV_FRAC": (float, 0.0, None, "Max frame-advance fraction constraint"),
    "ASP_POSE_REFINE_SAME_HOLD_PENALTY": (float, 0.0, 1.0, "Penalty for staying in same hold block"),
    "ASP_POSE_PATH_SELECT": (int, 0, 1, "Experimental dynamic-programming pose path selection"),
    "ASP_POSE_PATH_SAFE": (int, 0, 1, "Reject experimental pose paths with structural-risk diagnostics"),
}


def get_active_schema() -> dict[str, tuple]:
    """Retrieves the live schema from submodules.ASP if available, otherwise fallback."""
    try:
        from submodules.ASP.backend.src.core.config import _CONFIG_SCHEMA
        return dict(_CONFIG_SCHEMA)
    except Exception:
        return dict(_FALLBACK_SCHEMA)


CATEGORY_MAPPING = {
    "Frame Selection": [
        "ASP_HOLD_THRESHOLD", "ASP_HOLD_DHASH_THRESH", "ASP_DHASH_EXACT_DROP",
        "ASP_HIGH_HOLD_RESPONSE", "ASP_HOLD_AVERAGE", "ASP_HOLD_BG_SUB",
        "ASP_BLUR_REJECT_THRESH",
        "ASP_CONTRAST_THRESH", "ASP_NEAR_DUP_LUMA", "ASP_TEMPORAL_VAR_THRESH",
        "ASP_OTSU_BG_CORR", "ASP_TWO_CHANNEL_SELECT", "ASP_POSE_WINDOW_PX",
        "ASP_PHASE_AWARE_SELECT", "ASP_PHASE_CROSS_PENALTY", "ASP_MAX_SKIPPABLE_HOLD_SIZE",
        "ASP_POSE_REFINE_LOOK_RANGE", "ASP_POSE_REFINE_MIN_GAIN", "ASP_POSE_REFINE_MIN_ADV_FRAC",
        "ASP_POSE_REFINE_MAX_ADV_FRAC", "ASP_POSE_REFINE_SAME_HOLD_PENALTY",
        "ASP_POSE_PATH_SELECT", "ASP_POSE_PATH_SAFE"
    ],
    "Video Ingestion": [
        "ASP_VIDEO_MAX_FRAMES", "ASP_VIDEO_PROXY_SCALE", "ASP_VIDEO_TELECINE_MAD",
        "ASP_VIDEO_KEYFRAMES_ONLY"
    ],
    "Masking & Segmentation": [
        "ASP_USE_SAM2"
    ],
    "Matching & Alignment": [
        "ASP_MATCH_SPREAD_CEIL", "ASP_LOFTR_BG_RATIO_MIN", "ASP_SIMILARITY_MODE",
        "ASP_ALIGN_GATE_DX", "ASP_BA_F_SCALE", "ASP_GNC_OUTER", "ASP_DY_CV_MAX",
        "ASP_ST_INLIER_THRESHOLD", "ASP_ROT_TIGHT", "ASP_ROT_LOOSE", "ASP_SC_TIGHT",
        "ASP_SC_LOOSE", "ASP_MONO_TAU_MIN", "ASP_ROT_SCALE_CONSISTENCY_THRESH"
    ],
    "Foreground Registration": [
        "ASP_FG_REGISTER", "ASP_FLOW_ENGINE", "ASP_ARAP_PUSH", "ASP_FG_MAX_RESIDUAL"
    ],
    "Rendering & Temporal Median": [
        "ASP_FG_EXCLUDE_MEDIAN", "ASP_BG_AVERAGE", "ASP_BG_AVERAGE_FULL_AT",
        "ASP_MASKED_MEDIAN", "ASP_ADAPTIVE_RENDER_GAIN", "ASP_GAIN_DRIFT_MAX",
        "ASP_GPU_MEDIAN", "ASP_COV_MIN_MULTI_PCT"
    ],
    "Compositing & Gain Compensation": [
        "ASP_PHASE_COMPOSITE", "ASP_COHERENCE_V2", "ASP_GRAPHCUT_SEAM", "ASP_GC_FEATHER_PX",
        "ASP_BLOCKS_GAIN_COMP", "ASP_BLOCKS_LUM_COMP", "ASP_GLOBAL_GAIN_COMP",
        "ASP_JOINT_GAIN_SOLVE", "ASP_JOINT_GAIN_SIGMA_N", "ASP_JOINT_GAIN_SIGMA_G",
        "ASP_JOINT_GAIN_ROBUST", "ASP_SP_SOFT_PX", "ASP_BG_NORM_MIN_PX",
        "ASP_POST_SEAM_WARN_THRESH"
    ],
    "C++ Acceleration": [
        "ASP_BATCH_GPU"
    ]
}


class AspAdvancedConfigDialog(QDialog):
    """Interactive Configuration Dialog with 20-flag Primary profile and 73-flag Advanced drawer."""

    config_changed = Signal(dict)

    def __init__(self, initial_config: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Anime Stitch Pipeline — Advanced Configuration Matrix")
        self.resize(850, 680)
        self.schema = get_active_schema()
        self.widgets: Dict[str, QWidget] = {}
        self.current_config: Dict[str, Any] = dict(initial_config or {})

        self._build_ui()
        self._load_config_values(self.current_config)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header with profile selection and search
        top_bar = QHBoxLayout()
        title_lbl = QLabel("ASP Configuration Matrix")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00f0ff;")
        top_bar.addWidget(title_lbl)

        top_bar.addStretch()

        top_bar.addWidget(QLabel("Preset Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Default (Laptop Balanced)", "Desktop Quality", "Research / Ungated", "Custom"])
        self.profile_combo.currentTextChanged.connect(self._on_profile_preset_changed)
        top_bar.addWidget(self.profile_combo)

        layout.addLayout(top_bar)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter parameters by key name or description...")
        self.search_edit.textChanged.connect(self._filter_parameters)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Tabs for Primary Curated vs Advanced Categories
        self.tab_widget = QTabWidget()

        # Primary Tab (Curated 20 flags)
        primary_widget = QWidget()
        primary_layout = QVBoxLayout(primary_widget)
        primary_scroll = QScrollArea()
        primary_scroll.setWidgetResizable(True)
        primary_content = QWidget()
        self.primary_form = QFormLayout(primary_content)
        self.primary_form.setLabelAlignment(Qt.AlignRight)

        for key in PRIMARY_CURATED_KEYS:
            if key in self.schema:
                widget = self._create_widget_for_key(key, self.schema[key])
                self.widgets[key] = widget
                label = QLabel(key)
                label.setToolTip(self.schema[key][3])
                self.primary_form.addRow(label, widget)

        primary_scroll.setWidget(primary_content)
        primary_layout.addWidget(primary_scroll)
        self.tab_widget.addTab(primary_widget, f"Primary Profile (20 Flags)")

        # Advanced Tab (Full 73 flags categorized)
        advanced_widget = QWidget()
        advanced_layout = QVBoxLayout(advanced_widget)
        advanced_scroll = QScrollArea()
        advanced_scroll.setWidgetResizable(True)
        advanced_content = QWidget()
        self.advanced_content_layout = QVBoxLayout(advanced_content)

        for category, keys in CATEGORY_MAPPING.items():
            group = QGroupBox(f"{category} ({len(keys)} parameters)")
            form = QFormLayout(group)
            form.setLabelAlignment(Qt.AlignRight)

            for key in keys:
                if key in self.schema and key not in self.widgets:
                    widget = self._create_widget_for_key(key, self.schema[key])
                    self.widgets[key] = widget
                
                if key in self.widgets:
                    label = QLabel(key)
                    label.setToolTip(self.schema[key][3])
                    form.addRow(label, self.widgets[key])

            self.advanced_content_layout.addWidget(group)

        advanced_scroll.setWidget(advanced_content)
        advanced_layout.addWidget(advanced_scroll)
        self.tab_widget.addTab(advanced_widget, f"Advanced Matrix ({len(self.schema)} Total Flags)")

        layout.addWidget(self.tab_widget)

        # Footer action buttons
        button_bar = QHBoxLayout()
        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.clicked.connect(self._reset_to_defaults)
        button_bar.addWidget(btn_reset)

        btn_import = QPushButton("Import JSON/TOML...")
        btn_import.clicked.connect(self._import_config)
        button_bar.addWidget(btn_import)

        btn_export = QPushButton("Export JSON...")
        btn_export.clicked.connect(self._export_config)
        button_bar.addWidget(btn_export)

        button_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        button_bar.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Configuration")
        btn_apply.setStyleSheet("background-color: #00f0ff; color: #07080b; font-weight: bold;")
        btn_apply.clicked.connect(self._apply_and_accept)
        button_bar.addWidget(btn_apply)

        layout.addLayout(button_bar)

    def _create_widget_for_key(self, key: str, schema_entry: tuple) -> QWidget:
        expected_type, lo, hi, desc = schema_entry

        if expected_type == int:
            if lo == 0 and hi == 1:
                cb = QCheckBox("Enabled")
                cb.setToolTip(f"{key}\n{desc}\nType: Binary [0, 1]")
                return cb
            else:
                spin = QSpinBox()
                spin.setRange(lo if lo is not None else -999999, hi if hi is not None else 999999)
                spin.setToolTip(f"{key}\n{desc}\nRange: [{lo}, {hi}]")
                return spin
        elif expected_type == float:
            dspin = QDoubleSpinBox()
            dspin.setDecimals(4)
            dspin.setRange(lo if lo is not None else -999999.0, hi if hi is not None else 999999.0)
            dspin.setSingleStep(0.05 if (hi or 1.0) <= 1.0 else 1.0)
            dspin.setToolTip(f"{key}\n{desc}\nRange: [{lo}, {hi}]")
            return dspin
        elif expected_type == str:
            if "searaft" in desc or "dis" in desc:
                combo = QComboBox()
                combo.addItems(["searaft", "dis"])
                combo.setToolTip(f"{key}\n{desc}")
                return combo
            else:
                edit = QLineEdit()
                edit.setToolTip(f"{key}\n{desc}")
                return edit
        
        edit = QLineEdit()
        edit.setToolTip(f"{key}\n{desc}")
        return edit

    def _load_config_values(self, config: Dict[str, Any]) -> None:
        for key, widget in self.widgets.items():
            val = config.get(key)
            if val is None:
                continue

            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(val))
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                try:
                    widget.setValue(float(val))
                except Exception:
                    pass
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))

    def get_config(self) -> Dict[str, Any]:
        """Extracts current configuration dictionary matching types in schema."""
        cfg = {}
        for key, widget in self.widgets.items():
            entry = self.schema.get(key)
            if not entry:
                continue
            expected_type = entry[0]

            if isinstance(widget, QCheckBox):
                cfg[key] = 1 if widget.isChecked() else 0
            elif isinstance(widget, QSpinBox):
                cfg[key] = int(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                cfg[key] = float(widget.value())
            elif isinstance(widget, QComboBox):
                cfg[key] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    try:
                        cfg[key] = expected_type(text)
                    except Exception:
                        cfg[key] = text
        return cfg

    def _apply_and_accept(self) -> None:
        cfg = self.get_config()
        self.config_changed.emit(cfg)
        self.accept()

    def _reset_to_defaults(self) -> None:
        # Default profile: Laptop Balanced
        self.profile_combo.setCurrentText("Default (Laptop Balanced)")
        self._on_profile_preset_changed("Default (Laptop Balanced)")

    def _on_profile_preset_changed(self, profile: str) -> None:
        if profile == "Default (Laptop Balanced)":
            defaults = {
                "ASP_HOLD_THRESHOLD": 0.05,
                "ASP_HOLD_DHASH_THRESH": 4,
                "ASP_VIDEO_PROXY_SCALE": 0.25,
                "ASP_USE_SAM2": 0,
                "ASP_LOFTR_BG_RATIO_MIN": 0.15,
                "ASP_SIMILARITY_MODE": 1,
                "ASP_ALIGN_GATE_DX": 50.0,
                "ASP_BA_F_SCALE": 1.0,
                "ASP_FG_REGISTER": 1,
                "ASP_FLOW_ENGINE": "dis",
                "ASP_ARAP_PUSH": 1,
                "ASP_FG_EXCLUDE_MEDIAN": 1,
                "ASP_ADAPTIVE_RENDER_GAIN": 1,
                "ASP_MASKED_MEDIAN": 1,
                "ASP_COV_MIN_MULTI_PCT": 0.30,
                "ASP_PHASE_COMPOSITE": 0,
                "ASP_BLOCKS_GAIN_COMP": 1,
                "ASP_JOINT_GAIN_SOLVE": 0,
                "ASP_SP_SOFT_PX": 10,
                "ASP_BATCH_GPU": 0,
            }
            self._load_config_values(defaults)
        elif profile == "Desktop Quality":
            quality = {
                "ASP_HOLD_THRESHOLD": 0.02,
                "ASP_HOLD_DHASH_THRESH": 2,
                "ASP_VIDEO_PROXY_SCALE": 0.50,
                "ASP_USE_SAM2": 1,
                "ASP_LOFTR_BG_RATIO_MIN": 0.20,
                "ASP_SIMILARITY_MODE": 1,
                "ASP_ALIGN_GATE_DX": 35.0,
                "ASP_BA_F_SCALE": 0.8,
                "ASP_FG_REGISTER": 1,
                "ASP_FLOW_ENGINE": "searaft",
                "ASP_ARAP_PUSH": 1,
                "ASP_FG_EXCLUDE_MEDIAN": 1,
                "ASP_ADAPTIVE_RENDER_GAIN": 1,
                "ASP_MASKED_MEDIAN": 1,
                "ASP_COV_MIN_MULTI_PCT": 0.40,
                "ASP_PHASE_COMPOSITE": 1,
                "ASP_BLOCKS_GAIN_COMP": 1,
                "ASP_JOINT_GAIN_SOLVE": 1,
                "ASP_SP_SOFT_PX": 15,
                "ASP_BATCH_GPU": 1,
            }
            self._load_config_values(quality)
        elif profile == "Research / Ungated":
            ungated = {
                "ASP_ALIGN_GATE_DX": 9999.0,
                "ASP_COV_MIN_MULTI_PCT": 0.0,
                "ASP_DY_CV_MAX": 0.0,
                "ASP_MATCH_SPREAD_CEIL": 0.0,
            }
            self._load_config_values(ungated)

    def _filter_parameters(self, text: str) -> None:
        query = text.lower().strip()
        for key, widget in self.widgets.items():
            desc = self.schema.get(key, (None, None, None, ""))[3].lower()
            visible = (not query) or (query in key.lower()) or (query in desc)
            widget.setVisible(visible)
            # Find associated label if possible
            parent_form = widget.parentWidget()
            if isinstance(parent_form, QWidget):
                label = parent_form.findChild(QLabel, "")

    def _export_config(self) -> None:
        cfg = self.get_config()
        path, _ = QFileDialog.getSaveFileName(self, "Export ASP Configuration", "asp_config.json", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                QMessageBox.information(self, "Export Successful", f"Configuration exported to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to write file:\n{e}")

    def _import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import ASP Configuration", "", "JSON/TOML Files (*.json *.toml)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._load_config_values(data)
                    self.profile_combo.setCurrentText("Custom")
                    QMessageBox.information(self, "Import Successful", f"Imported {len(data)} configuration keys.")
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Failed to parse file:\n{e}")
