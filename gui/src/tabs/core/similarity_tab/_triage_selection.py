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
        self._push_selection_to_dual()

    def _deselect_paths(self, paths):
        doomed = set(paths)
        self.selected_files[:] = [p for p in self.selected_files if p not in doomed]
        self._push_selection_to_dual()

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
        self.dual.toggle_selection(path)
        self.selection_changed_qml.emit()

    # ─── Virtual dual-gallery surface (GUI/UX §2.1 Option A) ────────────────

    def _sync_selection_from_dual(self):
        self.selected_files = list(self.dual.selected_paths())
        self.on_selection_changed()
        self.selection_changed_qml.emit()

    def _push_selection_to_dual(self):
        self.dual.set_selected_paths(self.selected_files)

    def refresh_found_gallery(self):
        self.dual.set_found_paths(self.found_files)

    def refresh_selected_panel(self):
        self.dual.set_selected_paths(self.selected_files)

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files = []
            self.selected_files = []
        self.dual.clear()
        self.cancel_loading()
        self.on_selection_changed()

    @Slot(str)
    def select_file_qml(self, path):
        self.toggle_selection(path)


__all__ = ["_TriageSelectionMixin"]
