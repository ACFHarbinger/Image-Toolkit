"""Shared style constants and small helper functions for the metadata editor.

Extracted from ``metadata_editor_window.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QListWidget

if TYPE_CHECKING:
    from ._filtered_tag_list import FilteredTagList

# ---------------------------------------------------------------------------
# Tag colour palette (mirrors scan_metadata_tab)
# ---------------------------------------------------------------------------
_TAG_COLORS: Dict[str, str] = {
    "Artist": "#5865f2",
    "Series": "#f1c40f",
    "Character": "#2ecc71",
    "General": "#e91e63",
    "Meta": "#9b59b6",
    "": "#c7c7c7",
}

_LIST_STYLE = (
    "QListWidget::item { padding: 4px; } "
    "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 6px; }"
)
_INPUT_STYLE = (
    "QLineEdit, QComboBox { background-color: #2c2f33; color: #dcddde; "
    "border: 1px solid #4f545c; border-radius: 4px; padding: 4px; }"
)
_GROUP_STYLE = (
    "QGroupBox { font-weight: bold; border: 1px solid #4f545c; border-radius: 6px; "
    "margin-top: 8px; padding-top: 8px; } "
    "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
)


def _make_tag_list(tags_data: List[Dict[str, str]]) -> "FilteredTagList":
    """Return a FilteredTagList pre-populated with checkable tag items."""
    from ._filtered_tag_list import FilteredTagList

    return FilteredTagList(tags_data)


def _checked_tags(lw: "FilteredTagList | QListWidget") -> List[str]:
    if hasattr(lw, "checked_tags"):
        return lw.checked_tags()
    return [
        lw.item(i).data(Qt.ItemDataRole.UserRole) # pyrefly: ignore [missing-attribute]
        for i in range(lw.count()) # pyrefly: ignore [missing-attribute]
        if lw.item(i).checkState() == Qt.CheckState.Checked # pyrefly: ignore [missing-attribute]
    ]


def _set_checked_tags(lw: "FilteredTagList | QListWidget", tags: List[str]) -> None:
    if hasattr(lw, "set_checked_tags"):
        lw.set_checked_tags(tags)
        return
    tag_set = set(tags)
    for i in range(lw.count()): # pyrefly: ignore [missing-attribute]
        item = lw.item(i) # pyrefly: ignore [missing-attribute]
        item.setCheckState(
            Qt.CheckState.Checked
            if item.data(Qt.ItemDataRole.UserRole) in tag_set
            else Qt.CheckState.Unchecked
        )


def _apply_pattern(template: str, index: int) -> str:
    """Replace {n} or trailing digits with sequential index.

    Examples:
        "name{n}"  → "name1", "name2", …
        "shot"     → "shot1", "shot2", …  (auto-append)
    """
    if "{n}" in template:
        return template.replace("{n}", str(index + 1))
    return f"{template}{index + 1}"


def _thumb(path: str, size: int = 120) -> QLabel:
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("border: 1px solid #4f545c; background-color: #1e2124; border-radius: 4px;")
    px = QPixmap(path)
    if not px.isNull():
        lbl.setPixmap(px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
    else:
        lbl.setText("?")
    return lbl


__all__ = [
    "_TAG_COLORS",
    "_LIST_STYLE",
    "_INPUT_STYLE",
    "_GROUP_STYLE",
    "_make_tag_list",
    "_checked_tags",
    "_set_checked_tags",
    "_apply_pattern",
    "_thumb",
]
