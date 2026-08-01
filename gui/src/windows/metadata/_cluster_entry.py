"""``_ClusterEntry`` -- one named cluster (image subset + its own metadata form).

Extracted from ``metadata_editor_window.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ._shared import _GROUP_STYLE, _INPUT_STYLE, _LIST_STYLE, _apply_pattern, _checked_tags, _make_tag_list


class _ClusterEntry(QGroupBox):
    """One cluster: a label, an image-path selection list, and a metadata form."""

    remove_requested = Signal(object)  # emits self

    def __init__(
        self,
        index: int,
        all_paths: List[str],
        groups: List[str],
        subgroups: List[Tuple[str, str]],
        tags_data: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(f"Cluster {index + 1}", parent)
        self.setStyleSheet(_GROUP_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._all_paths = all_paths

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 16, 8, 8)

        # Header row: rename + remove
        hdr = QHBoxLayout()
        self._name_edit = QLineEdit(f"Cluster {index + 1}")
        self._name_edit.setStyleSheet(_INPUT_STYLE)
        self._name_edit.textChanged.connect(lambda t: self.setTitle(t or f"Cluster {index + 1}"))
        hdr.addWidget(QLabel("Name:"))
        hdr.addWidget(self._name_edit, 1)
        btn_remove = QPushButton("✕ Remove")
        btn_remove.setStyleSheet("background-color: #992222; color: white; padding: 4px 8px;")
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        hdr.addWidget(btn_remove)
        root.addLayout(hdr)

        # Image multi-selection
        img_lbl = QLabel("Images in this cluster (check to include):")
        root.addWidget(img_lbl)
        self._img_list = QListWidget()
        self._img_list.setMaximumHeight(110)
        self._img_list.setStyleSheet(_LIST_STYLE)
        for p in all_paths:
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._img_list.addItem(item)
        root.addWidget(self._img_list)

        btn_row = QHBoxLayout()
        for label, state in [("Check All", Qt.CheckState.Checked), ("Uncheck All", Qt.CheckState.Unchecked)]:
            b = QPushButton(label)
            b.setStyleSheet("padding: 3px 8px;")
            s = state
            b.clicked.connect(lambda _, st=s: self._set_all(st))
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Metadata form
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)

        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        self._group_combo.setPlaceholderText("Group…")
        self._group_combo.addItems([""] + groups)
        self._group_combo.setStyleSheet(_INPUT_STYLE)
        self._group_combo.currentTextChanged.connect(self._refresh_subgroups)
        form.addRow("Group:", self._group_combo)

        self._subgroup_combo = QComboBox()
        self._subgroup_combo.setEditable(True)
        self._subgroup_combo.setPlaceholderText("Subgroup…")
        self._subgroup_combo.setStyleSheet(_INPUT_STYLE)
        self._all_subgroups = subgroups  # list of (subgroup_name, group_name)
        self._refresh_subgroups()
        form.addRow("Subgroup:", self._subgroup_combo)

        # Pattern mode
        pat_row = QHBoxLayout()
        self._pattern_check = QCheckBox("Group pattern (sequential)")
        self._pattern_check.setToolTip(
            "When checked, the Group/Subgroup values are treated as templates.\n"
            "Use {n} for the index, or leave it out to auto-append a number.\n"
            "e.g. 'Episode{n}' → Episode1, Episode2…"
        )
        pat_row.addWidget(self._pattern_check)
        pat_row.addStretch()
        root.addLayout(pat_row)

        self._tags_lw = _make_tag_list(tags_data)
        form.addRow("Tags:", self._tags_lw)
        root.addLayout(form)

    # ------------------------------------------------------------------
    def _set_all(self, state: Qt.CheckState) -> None:
        for i in range(self._img_list.count()):
            self._img_list.item(i).setCheckState(state)

    def _refresh_subgroups(self) -> None:
        grp = self._group_combo.currentText().strip()
        self._subgroup_combo.clear()
        self._subgroup_combo.addItem("")
        for sg, g in self._all_subgroups:
            if not grp or g.lower() == grp.lower():
                self._subgroup_combo.addItem(sg)

    # ------------------------------------------------------------------
    def checked_paths(self) -> List[str]:
        return [
            self._img_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._img_list.count())
            if self._img_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def metadata_for(self, path: str) -> Dict[str, Any]:
        """Return the metadata dict for a specific path in this cluster."""
        grp_tmpl = self._group_combo.currentText().strip() or None
        sub_tmpl = self._subgroup_combo.currentText().strip() or None
        tags = _checked_tags(self._tags_lw)
        use_pattern = self._pattern_check.isChecked()

        checked = self.checked_paths()
        idx = checked.index(path) if path in checked else 0

        grp = _apply_pattern(grp_tmpl, idx) if (use_pattern and grp_tmpl) else grp_tmpl
        sub = _apply_pattern(sub_tmpl, idx) if (use_pattern and sub_tmpl) else sub_tmpl
        return {"group_name": grp, "subgroup_name": sub, "tags": tags or None}


__all__ = ["_ClusterEntry"]
