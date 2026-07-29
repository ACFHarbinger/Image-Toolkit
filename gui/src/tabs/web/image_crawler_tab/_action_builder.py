"""Action-list context menu, parameter editing, reordering, add/remove.

Extracted from ``image_crawler_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMenu, QMessageBox


class _ActionBuilderMixin:
    """Manages the general-crawler action list (add/remove/reorder/edit)."""

    def show_context_menu(self, pos: QPoint):
        item = self.action_list_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu()

        row = self.action_list_widget.row(item)

        move_up_action = QAction("Move Up 🔼", self)
        move_up_action.triggered.connect(self.move_action_up)
        move_up_action.setEnabled(row > 0)
        menu.addAction(move_up_action)

        move_down_action = QAction("Move Down 🔽", self)
        move_down_action.triggered.connect(self.move_action_down)
        move_down_action.setEnabled(row < self.action_list_widget.count() - 1)
        menu.addAction(move_down_action)

        menu.addSeparator()

        edit_action = QAction("Edit Parameter ✏️", self)
        edit_action.triggered.connect(self.edit_action_parameter)
        if " | Param: " in item.text():
            menu.addAction(edit_action)

        remove_action = QAction("Remove 🗑️", self)
        remove_action.triggered.connect(self.remove_action)
        menu.addAction(remove_action)
        menu.exec(self.action_list_widget.mapToGlobal(pos))

    def edit_action_parameter(self):
        current_item = self.action_list_widget.currentItem()
        if not current_item or " | Param: " not in current_item.text():
            return

        full_text = current_item.text()
        action_type, param_str = full_text.split(" | Param: ", 1)

        is_number_mode = (
            "Find <img> Number X on Page" in action_type
            or "Wait X Seconds" in action_type
        )

        title = f"Edit Parameter for: {action_type}"
        prompt = "Enter new parameter value:"

        if is_number_mode:
            try:
                initial_value = int(float(param_str))
            except ValueError:
                initial_value = 1

            if "Wait X Seconds" in action_type:
                new_param, ok = QInputDialog.getDouble(
                    self, title, prompt, float(initial_value), 0.1, 300.0, 1
                )
            else:
                new_param, ok = QInputDialog.getInt(
                    self, title, prompt, initial_value, 1, 99999, 1
                )

            if ok:
                new_param = str(new_param)
            else:
                return

        else:
            new_param, ok = QInputDialog.getText(
                self, title, prompt, QLineEdit.EchoMode.Normal, param_str
            )

        if ok and new_param is not None:
            new_param_str = new_param.strip()
            if new_param_str:
                current_item.setText(f"{action_type} | Param: {new_param_str}")
                QMessageBox.information(
                    self, "Success", f"Parameter updated for '{action_type}'."
                )
            else:
                QMessageBox.warning(
                    self, "Edit Failed", "Parameter value cannot be empty."
                )

    def move_action_up(self):
        row = self.action_list_widget.currentRow()
        if row > 0:
            item = self.action_list_widget.takeItem(row)
            self.action_list_widget.insertItem(row - 1, item)
            self.action_list_widget.setCurrentRow(row - 1)

    def move_action_down(self):
        row = self.action_list_widget.currentRow()
        if row < self.action_list_widget.count() - 1:
            item = self.action_list_widget.takeItem(row)
            self.action_list_widget.insertItem(row + 1, item)
            self.action_list_widget.setCurrentRow(row + 1)

    def add_action(self):
        action_text = self.action_combo.currentText()
        param = self.action_param.text().strip()
        if param:
            action_text += f" | Param: {param}"
        self.action_list_widget.addItem(action_text)
        self.action_param.clear()

    def remove_action(self):
        row = self.action_list_widget.currentRow()
        if row >= 0:
            self.action_list_widget.takeItem(row)


__all__ = ["_ActionBuilderMixin"]
