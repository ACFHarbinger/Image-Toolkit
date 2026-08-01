"""``_ImageTab`` -- a single per-image tab (thumbnail + editable metadata).

Extracted from ``metadata_editor_window.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ._shared import _INPUT_STYLE, _checked_tags, _make_tag_list, _set_checked_tags, _thumb


class _ImageTab(QWidget):
    """A single tab showing a thumbnail and editable metadata for one image."""

    def __init__(
        self,
        path: str,
        groups: List[str],
        subgroups: List[Tuple[str, str]],
        tags_data: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.path = path
        self._all_subgroups = subgroups

        root = QHBoxLayout(self)

        # Left: thumbnail
        left = QVBoxLayout()
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        left.addWidget(_thumb(path, 140))
        fn_lbl = QLabel(os.path.basename(path))
        fn_lbl.setWordWrap(True)
        fn_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        fn_lbl.setMaximumWidth(150)
        left.addWidget(fn_lbl)
        left.addStretch()
        root.addLayout(left)

        # Right: form
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(8, 4, 4, 4)

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
        self._refresh_subgroups()
        form.addRow("Subgroup:", self._subgroup_combo)

        self._tags_lw = _make_tag_list(tags_data)
        form.addRow("Tags:", self._tags_lw)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        root.addWidget(scroll, 1)

    def _refresh_subgroups(self) -> None:
        grp = self._group_combo.currentText().strip()
        self._subgroup_combo.clear()
        self._subgroup_combo.addItem("")
        for sg, g in self._all_subgroups:
            if not grp or g.lower() == grp.lower():
                self._subgroup_combo.addItem(sg)

    def apply_batch(self, meta: Dict[str, Any]) -> None:
        """Pre-fill this tab's fields from a batch-level dict."""
        if meta.get("group_name"):
            self._group_combo.setCurrentText(meta["group_name"])
        if meta.get("subgroup_name"):
            self._subgroup_combo.setCurrentText(meta["subgroup_name"])
        if meta.get("tags"):
            _set_checked_tags(self._tags_lw, meta["tags"])

    def collect(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "group_name": self._group_combo.currentText().strip() or None,
            "subgroup_name": self._subgroup_combo.currentText().strip() or None,
            "tags": _checked_tags(self._tags_lw) or None,
        }


__all__ = ["_ImageTab"]
