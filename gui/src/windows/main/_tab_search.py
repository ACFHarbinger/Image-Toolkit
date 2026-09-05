"""Ctrl+T floating tab-name filter popup (§2.16C).

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout


class _TabSearchMixin:
    """Show a floating tab-name filter popup and jump to the chosen tab."""

    def _open_tab_search(self) -> None:
        """Show a floating tab-name filter popup (§2.16C)."""
        if getattr(self, "_using_runtime_shell", False):
            self._open_runtime_module_search()
            return
        all_entries: list[tuple[str, str, str]] = []
        for category, tabs_in_cat in self.all_tabs.items():
            for tab_name in tabs_in_cat:
                all_entries.append((category, tab_name, f"{tab_name}  —  {category}"))

        dlg = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dlg.setWindowTitle("Go to Tab")
        dlg.setFixedWidth(400)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to filter tabs…")
        layout.addWidget(search_input)

        list_widget = QListWidget()
        list_widget.setMaximumHeight(260)
        layout.addWidget(list_widget)

        def _populate(text: str) -> None:
            list_widget.clear()
            q = text.strip().lower()
            for category, tab_name, label in all_entries:
                if not q or q in tab_name.lower() or q in category.lower():
                    item = QListWidgetItem(label)
                    item.setData(Qt.ItemDataRole.UserRole, (category, tab_name))
                    list_widget.addItem(item)
            if list_widget.count():
                list_widget.setCurrentRow(0)

        def _activate(item=None) -> None:
            if item is None:
                item = list_widget.currentItem()
            if item is None:
                return
            category, tab_name = item.data(Qt.ItemDataRole.UserRole)
            self.command_combo.setCurrentText(category)
            QTimer.singleShot(0, lambda: self._select_tab_by_name(tab_name))
            dlg.accept()

        search_input.textChanged.connect(_populate)
        search_input.returnPressed.connect(_activate)
        list_widget.itemActivated.connect(_activate)
        list_widget.itemDoubleClicked.connect(_activate)

        _populate("")
        dlg.exec()

    def _select_tab_by_name(self, tab_name: str) -> None:
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_name:
                self.tabs.setCurrentIndex(i)
                return

    def _open_runtime_module_search(self) -> None:
        """Search catalog descriptors and activate the selected lazy module."""
        descriptors = self.module_catalog.all_descriptors()
        dlg = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dlg.setWindowTitle("Go to Module")
        dlg.setFixedWidth(400)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        search_input = QLineEdit(placeholderText="Type to filter modules…")
        list_widget = QListWidget()
        list_widget.setMaximumHeight(260)
        layout.addWidget(search_input)
        layout.addWidget(list_widget)

        def populate(text: str) -> None:
            list_widget.clear()
            query = text.strip().lower()
            for descriptor in descriptors:
                label = f"{descriptor.title}  —  {descriptor.category.value}"
                if not query or query in label.lower() or query in descriptor.module_id:
                    item = QListWidgetItem(label)
                    item.setData(Qt.ItemDataRole.UserRole, descriptor.module_id)
                    list_widget.addItem(item)
            if list_widget.count():
                list_widget.setCurrentRow(0)

        def activate(item=None) -> None:
            item = item or list_widget.currentItem()
            if item is not None:
                self.shell_layout_manager.activate_module(item.data(Qt.ItemDataRole.UserRole))
                dlg.accept()

        search_input.textChanged.connect(populate)
        search_input.returnPressed.connect(activate)
        list_widget.itemActivated.connect(activate)
        list_widget.itemDoubleClicked.connect(activate)
        populate("")
        dlg.exec()


__all__ = ["_TabSearchMixin"]
