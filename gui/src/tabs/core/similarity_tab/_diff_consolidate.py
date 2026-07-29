"""Visual diffing (base.similarity.diff_mask) and hardlink/symlink consolidation.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import logging
import os

from backend.src.core.similarity import auto_select, consolidate_cluster
from PySide6.QtCore import Slot

logger = logging.getLogger(__name__)


class _DiffConsolidateMixin:
    """Generate a pixel-diff overlay for two paths, and consolidate a cluster."""

    @Slot(str, str, result=str)
    def generate_diff(self, path_a: str, path_b: str) -> str:
        import base

        name = f"diff_{abs(hash((path_a, path_b))) & 0xFFFFFFFF:08x}.png"
        out = os.path.join(self._diff_dir, name)
        try:
            result = base.similarity.diff_mask(path_a, path_b, out, tolerance=12)
        except Exception as e:
            logger.warning("diff_mask failed: %s", e)
            return ""
        if not result["ok"]:
            return ""
        self.diff_ready.emit(result["out_path"], result["changed_ratio"])
        return result["out_path"]

    @Slot(str)
    def consolidate_selected(self, mode: str = "auto"):
        total_linked, total_bytes, errors = 0, 0, []
        for c in self._cluster_model.clusters():
            selected_in_cluster = [p for p in c["paths"] if p in self.selected_files]
            if not selected_in_cluster:
                continue
            keeper = c.get("keeper") or ""
            if not keeper or keeper in selected_in_cluster:
                keeper, _ = auto_select(
                    [p for p in c["paths"] if p not in selected_in_cluster] or c["paths"],
                    self._triage_rules, self._ref_set,
                )
            if not keeper:
                continue
            res = consolidate_cluster(keeper, selected_in_cluster, mode=mode)
            total_linked += len(res.linked)
            total_bytes += res.bytes_reclaimed
            errors.extend(res.errors)
            self._deselect_paths(res.linked)
        self.on_selection_changed()
        summary = (f"Consolidated {total_linked} files "
                   f"({total_bytes / (1024 * 1024):.1f} MB reclaimed)")
        if errors:
            summary += f"; {len(errors)} errors (see log)"
            for e in errors[:10]:
                logger.warning("Consolidation error: %s", e)
        self.consolidation_done.emit(summary)
        self.status_label.setText(summary)
        self.scan_status_changed.emit(summary)


__all__ = ["_DiffConsolidateMixin"]
