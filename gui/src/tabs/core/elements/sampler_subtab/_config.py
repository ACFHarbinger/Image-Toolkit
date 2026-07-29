"""Tab-config get_default_config/set_config for SamplerSubTab.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Restores/provides default SamplerSubTab UI state as a config dict."""

    def get_default_config(self) -> dict:
        """Return the default tab configuration dict."""
        return {
            "input_path": "",
            "scale_mode": "factor",
            "scale_factor": 2.0,
            "target_width": 1920,
            "target_height": 1080,
            "preserve_aspect_ratio": True,
            "algorithm": "Lanczos",
            "output_format": "Keep original format",
            "output_path": "",
            "output_filename_prefix": "",
            "delete_original": False,
            "use_multicore": True,
        }

    def set_config(self, config: dict) -> None:
        """Populate input fields from a saved configuration dict."""
        try:
            # 1. Paths
            input_path = config.get("input_path", "")
            self.input_path.setText(input_path)

            output_path = config.get("output_path", "")
            self.out_dir_edit.setText(output_path)

            prefix = config.get("output_filename_prefix", config.get("prefix", ""))
            self.prefix_edit.setText(prefix)

            # 2. Scale mode and values
            scale_mode = config.get("scale_mode", "factor")
            if scale_mode == "factor":
                self._radio_factor.setChecked(True)
            else:
                self._radio_dims.setChecked(True)
            self._on_scale_mode_changed(scale_mode == "factor")

            self.scale_factor_spin.setValue(config.get("scale_factor", 2.0))
            self.dim_w_spin.setValue(config.get("target_width", 1920))
            self.dim_h_spin.setValue(config.get("target_height", 1080))
            self.preserve_ar_cb.setChecked(config.get("preserve_aspect_ratio", True))

            # 3. Algorithm
            algo = config.get("algorithm", "Lanczos")
            algo_map_rev = {
                "lanczos": "Lanczos",
                "bicubic": "Bicubic",
                "bilinear": "Bilinear",
                "nearest": "Nearest Neighbor",
            }
            mapped_algo = algo_map_rev.get(algo.lower(), algo)
            idx = self.algorithm_combo.findText(mapped_algo)
            if idx != -1:
                self.algorithm_combo.setCurrentIndex(idx)

            # 4. Output format
            out_fmt = config.get("output_format", "Keep original format")
            if not out_fmt:
                out_fmt = "Keep original format"
            idx_fmt = self.out_format_combo.findText(out_fmt, Qt.MatchFlag.MatchExactly)
            if idx_fmt == -1 and out_fmt != "Keep original format":
                idx_fmt = self.out_format_combo.findText(out_fmt.upper(), Qt.MatchFlag.MatchExactly)
            if idx_fmt != -1:
                self.out_format_combo.setCurrentIndex(idx_fmt)

            # 5. Checkboxes
            self.delete_cb.setChecked(config.get("delete_original", False))
            self.multicore_cb.setChecked(config.get("use_multicore", True))

            # 6. Restore selected files
            self._restore_selected_files(config)

            # 7. Scan/load data if valid directory
            if os.path.isdir(input_path):
                self._scan_and_load()

            print("SamplerSubTab configuration loaded.")
        except Exception as e:
            print(f"Error applying SamplerSubTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
