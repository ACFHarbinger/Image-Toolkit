"""Shared style constants and small helper functions for the metadata editor.

Extracted from ``metadata_editor_window.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QListWidget

from gui.src.theming.theme_api import color, qss

if TYPE_CHECKING:
    from ._filtered_tag_list import FilteredTagList

# ---------------------------------------------------------------------------
# Tag colour: real colors now come from tag_categories (via
# db.get_all_tags_with_categories()) per tag; this is only the fallback for
# an uncategorized/unknown category name.
# ---------------------------------------------------------------------------
_DEFAULT_TAG_COLOR = color("muted_text")

_LIST_STYLE = qss("metadata_list")
_INPUT_STYLE = qss("metadata_input")
_GROUP_STYLE = qss("metadata_group")


def _make_tag_list(tags_data: List[Dict[str, str]]) -> "FilteredTagList":
    """Return a FilteredTagList pre-populated with checkable tag items."""
    from ._filtered_tag_list import FilteredTagList

    return FilteredTagList(tags_data)


def _checked_tags(lw: "FilteredTagList | QListWidget") -> List[str]:
    if hasattr(lw, "checked_tags"):
        return lw.checked_tags()
    return [
        lw.item(i).data(Qt.ItemDataRole.UserRole)  # pyrefly: ignore [missing-attribute]
        for i in range(lw.count())  # pyrefly: ignore [missing-attribute]
        if lw.item(i).checkState() == Qt.CheckState.Checked  # pyrefly: ignore [missing-attribute]
    ]


def _set_checked_tags(lw: "FilteredTagList | QListWidget", tags: List[str]) -> None:
    if hasattr(lw, "set_checked_tags"):
        lw.set_checked_tags(tags)
        return
    tag_set = set(tags)
    for i in range(lw.count()):  # pyrefly: ignore [missing-attribute]
        item = lw.item(i)  # pyrefly: ignore [missing-attribute]
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
    lbl.setStyleSheet(qss("metadata_thumb"))
    px = QPixmap(path)
    if not px.isNull():
        lbl.setPixmap(px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
    else:
        lbl.setText("?")
    return lbl


__all__ = [
    "_DEFAULT_TAG_COLOR",
    "_LIST_STYLE",
    "_INPUT_STYLE",
    "_GROUP_STYLE",
    "_make_tag_list",
    "_checked_tags",
    "_set_checked_tags",
    "_apply_pattern",
    "_thumb",
]
