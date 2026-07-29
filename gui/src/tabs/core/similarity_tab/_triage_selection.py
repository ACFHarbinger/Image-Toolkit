"""Triage/selection helpers: per-cluster auto-select and QML selection toggles.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from backend.src.core.similarity import auto_select
from PySide6.QtCore import Slot


class _TriageSelectionMixin:
    """Auto-select keepers per cluster/globally, and QML-facing selection toggles."""

    def _select_paths(self, paths):
        current = set(self.selected_files)
        for p in paths:
            if p not in current:
                self.selected_files.append(p)
                current.add(p)

    def _deselect_paths(self, paths):
        doomed = set(paths)
        self.selected_files[:] = [p for p in self.selected_files if p not in doomed]

    @Slot(str, result="QStringList")
    def cluster_paths(self, cluster_id: str):
        c = self._cluster_model.get(cluster_id)
        return c["paths"] if c else []

    @Slot(str)
    def auto_select_cluster(self, cluster_id: str):
        c = self._cluster_model.get(cluster_id)
        if not c:
            return
        keeper, discards = auto_select(c["paths"], self._triage_rules, self._ref_set)
        if keeper:
            self._cluster_model.set_keeper(cluster_id, keeper)
        self._deselect_paths(c["paths"])
        self._select_paths(discards)
        self.on_selection_changed()

    @Slot()
    def auto_select_all(self):
        for c in self._cluster_model.clusters():
            keeper, discards = auto_select(c["paths"], self._triage_rules, self._ref_set)
            c["keeper"] = keeper or ""
            self._deselect_paths(c["paths"])
            self._select_paths(discards)
        self._cluster_model.set_clusters(self._cluster_model.clusters())
        self.on_selection_changed()

    @Slot(str, result=bool)
    def is_selected(self, path: str) -> bool:
        return path in self.selected_files

    def toggle_selection(self, path: str):
        super().toggle_selection(path)
        self.selection_changed_qml.emit()

    @Slot(str)
    def select_file_qml(self, path):
        self.toggle_selection(path)


__all__ = ["_TriageSelectionMixin"]
