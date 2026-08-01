"""DB.8a: pick which image groups a media entry links to.

Modeled on ``_AssociatedEntitiesDialog`` -- a checkable list, search box,
Select/Cancel -- but with suggested matches (fuzzy title<->group-name,
``MediaRepo.suggest_group_matches``) sorted first and visually marked.
"""

from typing import List

from gui.src.styles import SHARED_BUTTON_STYLE
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class _LinkedGroupsDialog(QDialog):
    def __init__(
        self,
        all_group_names: List[str],
        linked_names: List[str],
        suggested_names: List[str],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Link Image Groups")
        self.setMinimumSize(380, 420)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.selected_names = set(linked_names)
        self._suggested = set(suggested_names)
        # Suggested-first, then alphabetical within each bucket.
        self._all_names = sorted(
            all_group_names, key=lambda n: (n not in self._suggested, n.lower())
        )

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search image groups…")
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background:#23272a; border:1px solid #4f545c; border-radius:6px; padding:4px; }"
            "QListWidget::item { color:white; padding:4px; border-bottom:1px solid #2c2f33; }"
            "QListWidget::item:hover { background:#00bcd4; color:black; }"
        )
        layout.addWidget(self.list_widget)

        self._populate_list()

        btns = QHBoxLayout()
        ok_btn = QPushButton("Save Links")
        ok_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def _populate_list(self):
        self.list_widget.clear()
        query = self.search_box.text().lower()
        for name in self._all_names:
            if query and query not in name.lower():
                continue

            label = f"★ {name}" if name in self._suggested else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if name in self.selected_names
                else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(item)

    def _filter_list(self):
        self._sync_selection_from_widget()
        self._populate_list()

    def _sync_selection_from_widget(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_names.add(name)
            else:
                self.selected_names.discard(name)

    def get_selected_names(self) -> List[str]:
        self._sync_selection_from_widget()
        return list(self.selected_names)


__all__ = ["_LinkedGroupsDialog"]
