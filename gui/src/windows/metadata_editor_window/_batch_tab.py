"""``_BatchTab`` -- the first tab: bulk-apply metadata and define clusters.

Extracted from ``metadata_editor_window.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...styles import apply_shadow_effect
from ._cluster_entry import _ClusterEntry
from ._image_tab import _ImageTab
from ._shared import _GROUP_STYLE, _INPUT_STYLE, _checked_tags, _make_tag_list


class _BatchTab(QWidget):
    """The first tab — bulk-apply metadata and define clusters."""

    def __init__(
        self,
        all_paths: List[str],
        groups: List[str],
        subgroups: List[Tuple[str, str]],
        tags_data: List[Dict[str, str]],
        per_image_tabs: List["_ImageTab"],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._all_paths = all_paths
        self._groups = groups
        self._subgroups = subgroups
        self._tags_data = tags_data
        self._per_image_tabs = per_image_tabs
        self._clusters: List[_ClusterEntry] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # --- Apply-to-all section ---
        all_box = QGroupBox("Apply to ALL Images")
        all_box.setStyleSheet(_GROUP_STYLE)
        all_form = QFormLayout(all_box)
        all_form.setContentsMargins(8, 16, 8, 8)

        self._all_group = QComboBox()
        self._all_group.setEditable(True)
        self._all_group.setPlaceholderText("Group…")
        self._all_group.addItems([""] + groups)
        self._all_group.setStyleSheet(_INPUT_STYLE)
        self._all_group.currentTextChanged.connect(self._refresh_all_subgroups)
        all_form.addRow("Group:", self._all_group)

        self._all_subgroup = QComboBox()
        self._all_subgroup.setEditable(True)
        self._all_subgroup.setPlaceholderText("Subgroup…")
        self._all_subgroup.setStyleSheet(_INPUT_STYLE)
        self._refresh_all_subgroups()
        all_form.addRow("Subgroup:", self._all_subgroup)

        self._all_tags = _make_tag_list(tags_data)
        all_form.addRow("Tags:", self._all_tags)

        apply_all_btn = QPushButton("⬇  Apply to All Image Tabs")
        apply_all_btn.setStyleSheet(
            "QPushButton { background: #5865f2; color: white; font-weight: bold; "
            "padding: 8px 14px; border-radius: 6px; }"
            "QPushButton:hover { background: #4752c4; }"
        )
        apply_shadow_effect(apply_all_btn, "#000000", 6, 0, 2)
        apply_all_btn.clicked.connect(self._apply_all)
        all_form.addRow("", apply_all_btn)
        root.addWidget(all_box)

        # --- Clusters ---
        clusters_hdr = QHBoxLayout()
        clusters_hdr.addWidget(QLabel("Clusters (optional — override specific image subsets):"))
        clusters_hdr.addStretch()
        add_cluster_btn = QPushButton("+ Add Cluster")
        add_cluster_btn.setStyleSheet(
            "QPushButton { background: #2ecc71; color: white; padding: 5px 12px; border-radius: 5px; }"
            "QPushButton:hover { background: #27ae60; }"
        )
        add_cluster_btn.clicked.connect(self._add_cluster)
        clusters_hdr.addWidget(add_cluster_btn)
        root.addLayout(clusters_hdr)

        apply_clusters_btn = QPushButton("⬇  Apply All Clusters to Image Tabs")
        apply_clusters_btn.setStyleSheet(
            "QPushButton { background: #e67e22; color: white; font-weight: bold; "
            "padding: 7px 14px; border-radius: 6px; }"
            "QPushButton:hover { background: #ca6f1e; }"
        )
        apply_shadow_effect(apply_clusters_btn, "#000000", 6, 0, 2)
        apply_clusters_btn.clicked.connect(self._apply_clusters)
        root.addWidget(apply_clusters_btn)

        # Scrollable cluster container
        self._cluster_container = QWidget()
        self._cluster_layout = QVBoxLayout(self._cluster_container)
        self._cluster_layout.setContentsMargins(0, 0, 0, 0)
        self._cluster_layout.setSpacing(8)
        self._cluster_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cluster_container)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; border-radius: 6px; }")
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------------ helpers

    def _refresh_all_subgroups(self) -> None:
        grp = self._all_group.currentText().strip()
        self._all_subgroup.clear()
        self._all_subgroup.addItem("")
        for sg, g in self._subgroups:
            if not grp or g.lower() == grp.lower():
                self._all_subgroup.addItem(sg)

    def _apply_all(self) -> None:
        meta = {
            "group_name": self._all_group.currentText().strip() or None,
            "subgroup_name": self._all_subgroup.currentText().strip() or None,
            "tags": _checked_tags(self._all_tags),
        }
        for tab in self._per_image_tabs:
            tab.apply_batch(meta)

    def _add_cluster(self) -> None:
        idx = len(self._clusters)
        cluster = _ClusterEntry(
            idx, self._all_paths, self._groups, self._subgroups, self._tags_data
        )
        cluster.remove_requested.connect(self._remove_cluster)
        self._clusters.append(cluster)
        # Insert before the trailing stretch
        self._cluster_layout.insertWidget(self._cluster_layout.count() - 1, cluster)

    def _remove_cluster(self, cluster: _ClusterEntry) -> None:
        self._clusters.remove(cluster)
        self._cluster_layout.removeWidget(cluster)
        cluster.deleteLater()

    def _apply_clusters(self) -> None:
        for cluster in self._clusters:
            paths = cluster.checked_paths()
            for path in paths:
                meta = cluster.metadata_for(path)
                for tab in self._per_image_tabs:
                    if tab.path == path:
                        tab.apply_batch(meta)


__all__ = ["_BatchTab"]
