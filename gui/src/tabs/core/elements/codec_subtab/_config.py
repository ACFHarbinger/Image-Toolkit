"""Tab-config collect/get_default_config/set_config for CodecSubTab.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtWidgets import QMessageBox

from ._constants import AUDIO_CODEC_OPTIONS, SPEED_OPTIONS, VIDEO_CODEC_OPTIONS


class _ConfigMixin:
    """Collects/restores the full CodecSubTab UI state as a config dict."""

    def collect(self) -> dict:
        return {
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "output_filename_prefix": self.output_filename_prefix.text().strip(),
            "video_codec": VIDEO_CODEC_OPTIONS[self.video_codec_combo.currentText()],
            "audio_codec": AUDIO_CODEC_OPTIONS[self.audio_codec_combo.currentText()],
            "crf": self.crf_spin.value(),
            "speed": SPEED_OPTIONS[self.speed_combo.currentText()],
            "source_video_codecs": list(self.selected_video_codecs),
            "source_audio_codecs": list(self.selected_audio_codecs),
            "delete_original": self.delete_checkbox.isChecked(),
            "use_multicore": self.multicore_checkbox.isChecked(),
            "selected_files": list(self.selected_files),
        }

    def get_default_config(self) -> dict:
        return {
            "input_path": "",
            "output_path": "",
            "output_filename_prefix": "",
            "video_codec": "copy",
            "audio_codec": "copy",
            "crf": 28,
            "speed": 2,
            "source_video_codecs": [],
            "source_audio_codecs": [],
            "delete_original": False,
            "use_multicore": True,
        }

    def set_config(self, config: dict):  # noqa: C901
        try:
            input_path = config.get("input_path", "")
            self.input_path.setText(input_path)
            output_path = config.get("output_path", "") or ""
            self.output_path.setText(output_path)
            self.output_filename_prefix.setText(
                config.get("output_filename_prefix", "")
            )
            if output_path or config.get("output_filename_prefix"):
                self.output_field.set_open(True)

            video_codec_key = config.get("video_codec", "copy")
            for label, key in VIDEO_CODEC_OPTIONS.items():
                if key == video_codec_key:
                    self.video_codec_combo.setCurrentText(label)
                    break

            audio_codec_key = config.get("audio_codec", "copy")
            for label, key in AUDIO_CODEC_OPTIONS.items():
                if key == audio_codec_key:
                    self.audio_codec_combo.setCurrentText(label)
                    break

            self.crf_spin.setValue(config.get("crf", 28))

            speed_val = config.get("speed", 2)
            for label, val in SPEED_OPTIONS.items():
                if val == speed_val:
                    self.speed_combo.setCurrentText(label)
                    break

            for codec in config.get("source_video_codecs", []):
                if codec in self.video_codec_buttons:
                    self.video_codec_buttons[codec].setChecked(True)
                    self._toggle_codec_filter(
                        codec, True, self.video_codec_buttons, self.selected_video_codecs
                    )
            for codec in config.get("source_audio_codecs", []):
                if codec in self.audio_codec_buttons:
                    self.audio_codec_buttons[codec].setChecked(True)
                    self._toggle_codec_filter(
                        codec, True, self.audio_codec_buttons, self.selected_audio_codecs
                    )
            if self.selected_video_codecs:
                self.video_filter_field.set_open(True)
            if self.selected_audio_codecs:
                self.audio_filter_field.set_open(True)

            self.delete_checkbox.setChecked(config.get("delete_original", False))
            self.multicore_checkbox.setChecked(config.get("use_multicore", True))

            self._restore_selected_files(config)

            if os.path.isdir(input_path):
                self.scan_directory_visual()

            print("CodecSubTab configuration loaded.")
        except Exception as e:
            print(f"Error applying CodecSubTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
