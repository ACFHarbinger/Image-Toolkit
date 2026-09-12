"""Tab-config collect/get_default_config/set_config for FormatSubTab.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Collects/restores the full FormatSubTab UI state as a config dict."""

    def collect(self) -> dict:
        input_formats = (
            list(self.selected_formats)
            if self.dropdown and self.selected_formats
            else (
                self.join_list_str(self.input_formats.text().strip())
                if not self.dropdown and hasattr(self, "input_formats")
                else SUPPORTED_IMG_FORMATS
            )
        )

        # Calculate Aspect Ratio
        ar_val = None
        ar_mode = "crop"  # default
        ar_w = None
        ar_h = None

        if self.enable_ar_checkbox.isChecked():
            try:
                w = self.ar_w.value()
                h = self.ar_h.value()
                if h != 0:
                    ar_val = w / h
                    ar_w = w
                    ar_h = h
                    ar_mode = self.ar_mode_combo.currentText().lower()
            except Exception as e:
                print(f"Error calculating aspect ratio: {e}")

        return {
            "output_format": self.output_format_combo.currentText().lower(),
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "output_filename_prefix": self.output_filename_prefix.text().strip(),
            "input_formats": [
                f.strip().lstrip(".").lower() for f in input_formats if f.strip()
            ],
            "delete_original": self.delete_checkbox.isChecked(),
            "use_multicore": self.multicore_checkbox.isChecked(),
            "aspect_ratio": ar_val,
            "aspect_ratio_w": ar_w,
            "aspect_ratio_h": ar_h,
            "aspect_ratio_mode": ar_mode,
            "video_engine": self.engine_combo.currentText().split(" ")[0].lower(),
            "selected_files": list(self.selected_files),
        }

    def get_default_config(self) -> dict:
        """Returns the default configuration dictionary for the ConvertTab."""
        formats = SUPPORTED_IMG_FORMATS if self.dropdown else "jpg png"
        return {
            "input_path": "",
            "output_format": "png",
            "output_path": "",
            "output_filename_prefix": "",
            "input_formats": formats,
            "delete_original": False,
            "use_multicore": True,
            "aspect_ratio": None,
            "aspect_ratio_mode": "crop",
            "video_engine": "auto",
        }

    def set_config(self, config: dict):  # noqa: C901
        """Applies the configuration dictionary to the ConvertTab UI elements."""
        try:
            # 1. Paths
            input_path = config.get("input_path", "")
            self.input_path.setText(input_path)
            output_path = config.get("output_path", "")
            self.output_path.setText(output_path)

            # Set Filename Prefix (NEW)
            self.output_filename_prefix.setText(
                config.get("output_filename_prefix", "")
            )

            if output_path or config.get("output_filename_prefix"):
                self.output_field.set_open(True)

            # 2. Output Format
            output_fmt = config.get("output_format", "png")
            index = self.output_format_combo.findText(output_fmt.lower())
            if index != -1:
                self.output_format_combo.setCurrentIndex(index)

            # 3. Input Formats
            formats = config.get("input_formats", [])
            if self.dropdown:
                self.remove_all_formats()
                for fmt in formats:
                    if fmt in self.format_buttons:
                        self.format_buttons[fmt].setChecked(True)
                        self.toggle_format(fmt, True)
                if formats and len(formats) < len(SUPPORTED_IMG_FORMATS):
                    self.formats_field.set_open(True)
            elif hasattr(self, "input_formats"):
                self.input_formats.setText(" ".join(formats))
                if formats:
                    self.formats_field.set_open(True)

            # 4. Delete Checkbox
            self.delete_checkbox.setChecked(config.get("delete_original", False))
            self.multicore_checkbox.setChecked(config.get("use_multicore", True))

            # 5. Aspect Ratio
            aspect_ratio = config.get("aspect_ratio")
            ar_mode = config.get("aspect_ratio_mode", "crop")

            if aspect_ratio:
                self.enable_ar_checkbox.setChecked(True)

                # Set Mode
                mode_index = self.ar_mode_combo.findText(ar_mode.capitalize())
                if mode_index != -1:
                    self.ar_mode_combo.setCurrentIndex(mode_index)

                # Set Ratio
                ratios = {
                    "16:9": 16 / 9,
                    "4:3": 4 / 3,
                    "1:1": 1.0,
                    "9:16": 9 / 16,
                    "3:2": 3 / 2,
                }
                matched = False
                for label, val in ratios.items():
                    if abs(aspect_ratio - val) < 0.01:
                        self.ar_combo.setCurrentText(label)
                        matched = True
                        break

                if not matched:
                    self.ar_combo.setCurrentText("Custom")
            else:
                self.enable_ar_checkbox.setChecked(False)

            # 6. Restore selected gallery
            self._restore_selected_files(config)

            # 7. Load data
            if os.path.isdir(input_path):
                self.scan_directory_visual()

            print("FormatSubTab configuration loaded.")
        except Exception as e:
            print(f"Error applying ConvertTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
