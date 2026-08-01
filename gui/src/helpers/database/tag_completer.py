"""
TagCompleter helper (§2.22 Option D).
======================================
QCompleter extension and multi-tag autocomplete helper for tag search QLineEdit fields.
"""

from __future__ import annotations

from typing import List, Optional, Set

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtWidgets import QCompleter, QLineEdit


class TagCompleter(QCompleter):
    """
    QCompleter extension supporting multi-tag prefix completion (comma-separated tag lists).

    Parameters
    ----------
    tags : Optional[List[str]]
        Initial vocabulary list of tags.
    parent : Optional[QLineEdit]
        Parent line edit widget.
    """

    def __init__(self, tags: Optional[List[str]] = None, parent: Optional[QLineEdit] = None) -> None:
        self._tag_set: Set[str] = set(tags or [])
        self._string_model = QStringListModel(sorted(self._tag_set))
        super().__init__(self._string_model, parent)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        if parent is not None:
            self.attach_to_line_edit(parent)

    def set_tags(self, tags: List[str]) -> None:
        """Update the tag completion vocabulary."""
        self._tag_set = set(tags)
        self._string_model.setStringList(sorted(self._tag_set))

    def add_tag(self, tag: str) -> None:
        """Add a single tag to the completion vocabulary if not already present."""
        if tag and tag not in self._tag_set:
            self._tag_set.add(tag)
            self._string_model.setStringList(sorted(self._tag_set))

    def get_matching_tags(self, prefix: str) -> List[str]:
        """Return all tags matching the given prefix string."""
        clean_prefix = prefix.strip().lower()
        if not clean_prefix:
            return sorted(self._tag_set)
        return [t for t in sorted(self._tag_set) if t.lower().startswith(clean_prefix)]

    def attach_to_line_edit(self, line_edit: QLineEdit) -> None:
        """Attach completion signal handling to a QLineEdit."""
        line_edit.setCompleter(self)
        self.activated.connect(lambda text: self._on_tag_activated(line_edit, text))

    def _on_tag_activated(self, line_edit: QLineEdit, selected_tag: str) -> None:
        """Replace the current trailing token with the selected tag."""
        current_text = line_edit.text()
        tokens = [t.strip() for t in current_text.split(",") if t.strip()]
        if tokens:
            tokens[-1] = selected_tag
        else:
            tokens = [selected_tag]
        new_text = ", ".join(tokens) + ", "
        line_edit.setText(new_text)
