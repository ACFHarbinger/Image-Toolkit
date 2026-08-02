"""``AddTagDialog`` -- the "+" quick-add action for the grouped-tags section
on the Series/Entity detail panels (Danbooru-style tag overhaul).

Lets the user type a tag name (autocompleting against the existing
vocabulary) and pick a category from a scope-filtered list (universal
categories plus whichever of listing/entity applies).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class AddTagDialog(QDialog):
    def __init__(
        self,
        categories: List[Dict[str, str]],
        all_tag_names: List[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Tag")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tag name…")
        completer = QCompleter(all_tag_names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.name_edit.setCompleter(completer)
        form.addRow("Name", self.name_edit)

        self.category_combo = QComboBox()
        for cat in categories:
            self.category_combo.addItem(cat["name"], cat["name"])
        form.addRow("Category", self.category_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_edit.setFocus()

    def get_data(self) -> Tuple[str, Optional[str]]:
        name = self.name_edit.text().strip()
        category = self.category_combo.currentData()
        return name, category


__all__ = ["AddTagDialog"]
