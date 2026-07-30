"""The inspector's region/link annotation flow, as a mixin.

Split out of ``main_window.py`` to keep that file within the repo's 500-LoC
budget (§5.17 / issues #121-#122), following the same mixin-composition pattern
that epic used. The mixin reads ``self.session``, ``self.grid``, ``self.overlay``,
``self.annotation_list``, ``self.scoring_panel``, ``self.status_label`` and
``self._edge_builder`` — all owned by ``InspectorWindow``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog

from ..constants.schema import COMPARATOR_TITLES
from ..other.schema import BoundingBox, Edge, RatingEntry
from .annotations import DefectDialog


class AnnotationFlowMixin:
    """Turns panel-drawn geometry into schema objects on the current entry."""

    def _current_entry(self) -> RatingEntry:
        return self.session.entry()

    def _on_bbox_drawn(self, key: str, data: dict) -> None:
        dialog = DefectDialog(COMPARATOR_TITLES.get(key, key), self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            self.grid.restore_bboxes(self._current_entry().bboxes)  # drop the transient rect
            return
        defect, severity, label = dialog.result_values()
        entry = self._current_entry()
        entry.bboxes.append(BoundingBox(
            image=key, x=data["x"], y=data["y"], w=data["w"], h=data["h"],
            label=label, defect=defect, severity=severity,
        ))
        # A region tagged with a defect class implies the test-level tag too —
        # otherwise the corpus-level defect counts would miss anything the user
        # only recorded spatially.
        if defect and defect not in entry.defects:
            entry.defects = sorted(set(entry.defects) | {defect})
            self.scoring_panel.load_entry(entry)
        self.grid.restore_bboxes(entry.bboxes)
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._commit()

    def _on_point_picked(self, key: str, x: float, y: float) -> None:
        pair = self._edge_builder.add_point(key, x, y)
        if pair is None:
            self.status_label.setText("First point set — click the matching point in another panel.")
            return
        first, second = pair
        label, ok = QInputDialog.getText(
            self, "Link points", "Describe the relationship between these two points:"
        )
        if not ok:
            return
        entry = self._current_entry()
        entry.edges.append(Edge(a=first, b=second, label=label.strip()))
        self.overlay.set_edges(entry.edges)
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._commit()

    def _on_remove_annotation(self, kind: str, index: int) -> None:
        entry = self._current_entry()
        target = entry.bboxes if kind == "bbox" else entry.edges
        if 0 <= index < len(target):
            del target[index]
        self.grid.restore_bboxes(entry.bboxes)
        self.overlay.set_edges(entry.edges)
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._commit()
