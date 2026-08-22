"""Merge-config collect/get_default_config/set_config for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import Any, Dict

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtWidgets import QMessageBox


class _ConfigPersistenceMixin:
    """Collect the merge-run config dict and save/restore tab settings."""

    def collect(self, output_path: str = "") -> Dict[str, Any]:
        # canvas_layout stays canvas-widget-sourced (only meaningful for the
        # "canvas" direction, and the widget is always freshly reconciled by
        # _enter_canvas_mode by the time that direction is active). input_path
        # is the selection queue order — the same thing while in canvas mode
        # (kept in lockstep by toggle_selection) and the authoritative order
        # for every other mode, where the canvas isn't touched/shown at all.
        layout = self.canvas_widget.get_layout()
        direction = self.direction.currentText()
        return {
            "direction": direction,
            "scan_directory": self.scan_directory_path.text().strip(),
            "input_path": list(self.selected_files),
            "canvas_layout": layout,
            "canvas_width": self.canvas_w_spin.value(),
            "canvas_height": self.canvas_h_spin.value(),
            "canvas_background": self.canvas_bg_combo.currentText().lower(),
            "output_path": output_path,
            "input_formats": [
                f.strip().lstrip(".") for f in SUPPORTED_IMG_FORMATS if f.strip()
            ],
            "spacing": self.spacing.value(),
            "align_mode": self.align_mode.currentText(),
            "grid_size": (
                (self.grid_rows.value(), self.grid_cols.value())
                if direction == "grid"
                else None
            ),
            "duration": self.duration_spin.value(),
            "engine": self.engine_combo.currentData() if direction == "panorama" else None,
            "engine_kwargs": (
                self._collect_engine_kwargs() if direction == "panorama" else None
            ),
            "selected_files": list(self.selected_files),
        }

    def _collect_engine_kwargs(self) -> Dict[str, Any]:
        """Gather the settings for whichever panorama engine is selected."""
        engine = self.engine_combo.currentData()
        if engine == "hugin":
            return {
                "projection": self.hugin_projection_combo.currentData(),
                "linear_match": self.hugin_linear_match_checkbox.isChecked(),
            }
        elif engine == "overmix":
            return {
                "aligner": self.overmix_aligner_combo.currentText(),
                "render_stat": self.overmix_render_combo.currentText(),
            }
        elif engine == "asp":
            return {
                "renderer": self.renderer_combo.currentText(),
                "motion_model": self.motion_model_combo.currentData(),
                "use_basic": self.use_basic_checkbox.isChecked(),
                "use_loftr": self.use_loftr_checkbox.isChecked(),
                "use_ecc": self.use_ecc_checkbox.isChecked(),
                "composite_fg": self.composite_fg_checkbox.isChecked(),
                "use_birefnet": self.use_birefnet_checkbox.isChecked(),
                "edge_crop": self.edge_crop_spinbox.value(),
                "laplacian_bands": self.pyramid_levels_spinbox.value(),
            }
        else:  # opencv
            return {
                "stitcher_mode": self.opencv_stitcher_mode_combo.currentData(),
                "registration_resol": self.opencv_registration_resol_spin.value(),
            }

    # ─── Config save/restore ────────────────────────────────────────────────────

    def get_default_config(self) -> dict:
        return {
            "direction": "canvas",
            "spacing": 10,
            "grid_size": [2, 2],
            "scan_directory": "",
            "output_directory": "",
            "output_filename": "",
            "align_mode": "Default (Top/Center)",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "canvas_background": "transparent",
        }

    def set_config(self, config: dict):  # noqa: C901
        try:
            direction = config.get("direction", "canvas")
            if self.direction.findText(direction) != -1:
                self.direction.setCurrentText(direction)

            self.spacing.setValue(config.get("spacing", 10))

            align_mode = config.get("align_mode", "Default (Top/Center)")
            if self.align_mode.findText(align_mode) != -1:
                self.align_mode.setCurrentText(align_mode)

            grid_size = config.get("grid_size", [2, 2])
            if isinstance(grid_size, list) and len(grid_size) == 2:
                self.grid_rows.setValue(grid_size[0])
                self.grid_cols.setValue(grid_size[1])

            cw = config.get("canvas_width", 1920)
            ch = config.get("canvas_height", 1080)
            self.canvas_w_spin.setValue(cw)
            self.canvas_h_spin.setValue(ch)

            bg = config.get("canvas_background", "transparent").capitalize()
            idx = self.canvas_bg_combo.findText(bg)
            if idx >= 0:
                self.canvas_bg_combo.setCurrentIndex(idx)

            self._restore_selected_files(config)

            scan_dir = config.get("scan_directory")
            if scan_dir:
                self.scan_directory_path.setText(scan_dir)
                if os.path.isdir(scan_dir):
                    self.populate_scan_gallery(scan_dir)

            out_dir = config.get("output_directory")
            if out_dir:
                self.output_directory_path.setText(out_dir)
                self.output_dir = out_dir

            out_fname = config.get("output_filename")
            if out_fname:
                self.output_filename_input.setText(out_fname)

            engine = config.get("engine")
            if engine is None:
                # Back-compat: old saved sessions used a "Perfect Stitch
                # Mode" checkbox instead of an engine choice.
                engine = "asp" if config.get("perfect_stitch_mode") else "opencv"
            idx = self.engine_combo.findData(engine)
            if idx >= 0:
                self.engine_combo.setCurrentIndex(idx)

            ek = config.get("engine_kwargs") or {}
            self.opencv_stitcher_mode_combo.setCurrentIndex(
                max(0, self.opencv_stitcher_mode_combo.findData(ek.get("stitcher_mode", 0)))
            )
            self.opencv_registration_resol_spin.setValue(ek.get("registration_resol", 0.6))

            self.hugin_projection_combo.setCurrentIndex(
                max(0, self.hugin_projection_combo.findData(ek.get("projection", 0)))
            )
            self.hugin_linear_match_checkbox.setChecked(ek.get("linear_match", True))

            idx = self.overmix_aligner_combo.findText(ek.get("aligner", "Recursive"))
            if idx >= 0:
                self.overmix_aligner_combo.setCurrentIndex(idx)
            idx = self.overmix_render_combo.findText(ek.get("render_stat", "average"))
            if idx >= 0:
                self.overmix_render_combo.setCurrentIndex(idx)

            self.edge_crop_spinbox.setValue(
                ek.get("edge_crop", config.get("edge_crop_px", 30))
            )
            self.pyramid_levels_spinbox.setValue(
                ek.get("laplacian_bands", config.get("pyramid_levels", 8))
            )
            self.use_birefnet_checkbox.setChecked(
                ek.get("use_birefnet", config.get("use_birefnet", True))
            )
            self.use_basic_checkbox.setChecked(
                ek.get("use_basic", config.get("use_basic", True))
            )
            self.use_loftr_checkbox.setChecked(
                ek.get("use_loftr", config.get("use_loftr", True))
            )
            self.use_ecc_checkbox.setChecked(
                ek.get("use_ecc", config.get("use_ecc", True))
            )
            self.composite_fg_checkbox.setChecked(
                ek.get("composite_fg", config.get("composite_fg", True))
            )
            renderer = ek.get("renderer", config.get("renderer", "blend"))
            idx = self.renderer_combo.findText(renderer)
            if idx >= 0:
                self.renderer_combo.setCurrentIndex(idx)
            mm_idx = self.motion_model_combo.findData(
                ek.get("motion_model", config.get("motion_model", "translation"))
            )
            if mm_idx >= 0:
                self.motion_model_combo.setCurrentIndex(mm_idx)

            self._update_engine_visibility()

            print("MergeTab configuration loaded.")
        except Exception as e:
            print(f"Error applying MergeTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

    def _restore_selected_files(self, config: dict):
        saved = config.get("selected_files", [])
        if not saved:
            return
        valid = [p for p in saved if os.path.isfile(p)]
        if not valid:
            return
        self.selected_files = list(valid)
        self._push_selection_to_gallery()
        if self.direction.currentText() == "canvas":
            for path in valid:
                self.canvas_widget.add_image(path, self._thumbnail_for(path))
        else:
            self._refresh_queue_gallery()
        self.on_selection_changed()


__all__ = ["_ConfigPersistenceMixin"]
