"""Similarity/triage settings getters/setters + reference-directory QML slots.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os

from backend.src.core.similarity import SimilarityConfig, TriageRules
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog


class _QmlSettingsMixin:
    """QML-facing similarity-config/triage-rules accessors and reference-dir picker."""

    @Slot("QVariantMap")
    def set_similarity_settings(self, values: dict):
        data = self._sim_config.to_dict()
        for key, val in dict(values).items():
            if key not in data:
                continue
            # An empty extensions list means "use defaults" — never clobber.
            if key == "extensions" and not val:
                continue
            data[key] = val
        self._sim_config = SimilarityConfig.from_dict(data)

    @Slot(result="QVariantMap")
    def get_similarity_settings(self):
        return self._sim_config.to_dict()

    @Slot("QVariantMap")
    def set_triage_rules(self, values: dict):
        data = self._triage_rules.to_dict()
        for key, val in dict(values).items():
            if key in data:
                data[key] = val
        self._triage_rules = TriageRules.from_dict(data)

    @Slot(result="QVariantMap")
    def get_triage_rules(self):
        return self._triage_rules.to_dict()

    @Slot(str, result=str)
    def browse_reference_qml(self, current_path=""):
        starting = current_path if os.path.isdir(current_path) else ""
        d = QFileDialog.getExistingDirectory(
            self, "Select Reference Directory", starting,
            QFileDialog.Option.DontUseNativeDialog)
        if d:
            self._sim_config.reference_dir = d
            self.reference_dir_changed.emit(d)
            return d
        return ""

    @Slot()
    def clear_reference_dir(self):
        self._sim_config.reference_dir = None
        self.reference_dir_changed.emit("")


__all__ = ["_QmlSettingsMixin"]
