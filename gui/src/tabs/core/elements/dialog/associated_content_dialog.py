from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
)

from gui.src.styles.style import SHARED_BUTTON_STYLE


class _AssociatedContentDialog(QDialog):
    """Multi-select dialog for linking content listings to an entity."""

    def __init__(
        self, all_entries: List[Dict[str, Any]], selected_ids: List[str], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Associated Content")
        self.setMinimumSize(420, 460)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.all_entries = all_entries
        self.selected_ids = set(selected_ids)

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search by title or type…")
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
        ok_btn = QPushButton("Select")
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
        for entry in self.all_entries:
            title = entry.get("title", "Untitled")
            etype = entry.get("type", "")
            if query and query not in title.lower() and query not in etype.lower():
                continue
            label = f"{title} ({etype})" if etype else title
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            item.setCheckState(
                Qt.CheckState.Checked
                if entry["id"] in self.selected_ids
                else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(item)

    def _filter_list(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            eid = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(eid)
            else:
                self.selected_ids.discard(eid)
        self._populate_list()

    def get_selected_ids(self) -> List[str]:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            eid = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(eid)
            else:
                self.selected_ids.discard(eid)
        return list(self.selected_ids)
