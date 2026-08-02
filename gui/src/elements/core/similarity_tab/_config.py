"""Tab-config persistence (``collect``/``get_default_config``/``set_config``).

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from backend.src.constants import SUPPORTED_IMG_FORMATS
from backend.src.core.similarity import SimilarityConfig, TriageRules
from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class _ConfigMixin:
    """Save/restore directories, scan settings, extensions, and similarity config."""

    def collect(self, mode: str = "files") -> Dict[str, Any]:
        exts = []
        if self.dropdown and self.selected_extensions is not None:
            exts = list(self.selected_extensions)
        elif not self.dropdown and hasattr(self, "target_extensions"):
            exts = self.join_list_str(self.target_extensions.text().strip())
        send_to_trash_enabled = self._prefs().get("send_to_trash", True)
        return {
            "target_path": self.target_path.text().strip(),
            "reference_path": self.reference_path.text().strip(),
            "recursive": self.recursive_check.isChecked(),
            "mode": mode,
            "target_extensions": [e.strip().lstrip(".") for e in exts if e.strip()],
            "scan_method": self.scan_method_combo.currentText(),
            "require_confirm": self.confirm_checkbox.isChecked(),
            "selected_files": list(self.selected_files),
            "send_to_trash": send_to_trash_enabled,
            "similarity": self._sim_config.to_dict(),
            "triage": self._triage_rules.to_dict(),
        }

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip(".")
                for item in text.replace(",", " ").split() if item.strip()]

    def get_default_config(self) -> dict:
        extensions = SUPPORTED_IMG_FORMATS if self.dropdown else "jpg png"
        return {
            "target_path": "",
            "reference_path": "",
            "recursive": False,
            "scan_method": "Similarity Engine (tiered clusters)",
            "target_extensions": extensions,
            "require_confirm": True,
            "similarity": SimilarityConfig().to_dict(),
            "triage": TriageRules().to_dict(),
        }

    def set_config(self, config: dict):
        try:
            self.target_path.setText(config.get("target_path", ""))
            ref_path = config.get("reference_path", "")
            self.reference_path.setText(ref_path)
            self._sim_config.reference_dir = ref_path if os.path.isdir(ref_path) else None
            self.recursive_check.setChecked(bool(config.get("recursive", False)))
            scan_method = config.get("scan_method", "Similarity Engine (tiered clusters)")
            index = self.scan_method_combo.findText(scan_method)
            if index != -1:
                self.scan_method_combo.setCurrentIndex(index)
            extensions = config.get("target_extensions", [])
            if self.dropdown:
                self.remove_all_extensions()
                for ext in extensions:
                    if ext in self.extension_buttons:
                        self.extension_buttons[ext].setChecked(True)
                        self.toggle_extension(ext, True)
                if extensions and len(extensions) < len(SUPPORTED_IMG_FORMATS):
                    self.extensions_field.set_open(True)
            elif hasattr(self, "target_extensions"):
                self.target_extensions.setText(" ".join(extensions))
                if extensions:
                    self.extensions_field.set_open(True)
            self.confirm_checkbox.setChecked(config.get("require_confirm", True))
            self._restore_selected_files(config)
            if config.get("similarity"):
                self._sim_config = SimilarityConfig.from_dict(config["similarity"])
            if config.get("triage"):
                self._triage_rules = TriageRules.from_dict(config["triage"])
        except Exception as e:
            logger.error("Error applying SimilarityTab config: %s", e)
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")


__all__ = ["_ConfigMixin"]
