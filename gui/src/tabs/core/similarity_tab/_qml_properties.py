"""QML Property accessors and selection hook for ``SimilarityTab``.

Card creation and styling are promoted to AbstractClassTwoGalleries (§Issue 446).
"""

from __future__ import annotations

from typing import List


class _QmlPropertiesMixin:
    """scanRunning/confidenceThreshold/selectedFiles Qt Properties and selection hook."""

    # ==================================================================
    # Similarity state accessors
    # ==================================================================
    # NOTE: ``_cluster_model`` (a ClusterListModel) is kept for internal cluster
    # bookkeeping/auto-select. It is intentionally NOT exposed as a Qt Property:
    # this is a native widget tab, and a ``QAbstractListModel*`` property type
    # is not registerable on a plain QObject meta-object (it only warned).

    def _get_scan_running(self) -> bool:
        return self._scan_running

    def _get_conf_threshold(self) -> float:
        return self._sim_config.confidence_threshold

    def _set_conf_threshold(self, value: float):
        self.set_confidence_threshold(value)

    def _get_selected_files(self) -> List[str]:
        return sorted(self.selected_files)

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_delete_files.setText(f"Delete Selected Files ({count})")
        self.btn_delete_files.setEnabled(count > 0)
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        has_dups = len(self.found_files) > 0
        self.btn_compare_properties.setVisible(has_dups)
        self.btn_compare_properties.setEnabled(count > 0)
        self.selection_changed_qml.emit()


__all__ = ["_QmlPropertiesMixin"]
