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


class _AssociatedEntitiesDialog(QDialog):
    def __init__(
        self, all_entities: List[Dict[str, Any]], selected_ids: List[str], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Associated Entities")
        self.setMinimumSize(400, 450)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.all_entities = all_entities
        self.selected_ids = set(selected_ids)

        layout = QVBoxLayout(self)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search entities by name or role…")
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background:#23272a; border:1px solid #4f545c; border-radius:6px; padding:4px; }"
            "QListWidget::item { color:white; padding:4px; border-bottom:1px solid #2c2f33; }"
            "QListWidget::item:hover { background:#00bcd4; color:black; }"
        )
        layout.addWidget(self.list_widget)

        self._populate_list()

        # Buttons
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
        for ent in self.all_entities:
            name = ent.get("name", "Unnamed")
            role = ent.get("role", "Other")
            ent_type = ent.get("type", "Other")

            if query and query not in name.lower() and query not in role.lower():
                continue

            item = QListWidgetItem(f"{name} ({ent_type} - {role})")
            item.setData(Qt.ItemDataRole.UserRole, ent["id"])

            if ent["id"] in self.selected_ids:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

            self.list_widget.addItem(item)

    def _filter_list(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ent_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(ent_id)
            else:
                self.selected_ids.discard(ent_id)
        self._populate_list()

    def get_selected_ids(self) -> List[str]:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ent_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(ent_id)
            else:
                self.selected_ids.discard(ent_id)
        return list(self.selected_ids)
