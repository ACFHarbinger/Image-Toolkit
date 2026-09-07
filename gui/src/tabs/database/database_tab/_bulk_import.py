"""Bulk JSON tag import controller for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

if TYPE_CHECKING:
    pass


class DatabaseBulkImportController:
    """Browse for and import a JSON tag list into the database."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def browse_json_file(self) -> None:
        """Opens a file dialog to select a JSON file."""
        tab = self.tab
        initial_dir = Path(os.getcwd())
        file_path, _ = QFileDialog.getOpenFileName(
            tab,
            "Select JSON Tags File",
            str(initial_dir),
            "JSON Files (*.json);;All Files (*.*)",
        )
        if file_path:
            tab.json_file_path_edit.setText(file_path)

    def import_tags_from_json(self) -> None:
        """Reads the selected JSON file and imports tags into the database."""
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return

        file_path = tab.json_file_path_edit.text().strip()
        tag_type = tab.bulk_tag_type_combo.currentText().strip().title()

        if not file_path or not Path(file_path).is_file():
            QMessageBox.warning(tab, "Error", "Please select a valid JSON file.")
            return

        progress = None
        imported_tags = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if (
                isinstance(data, dict)
                and "tags" in data
                and isinstance(data["tags"], list)
            ):
                tag_list = data["tags"]
            elif isinstance(data, list):
                # Allow a direct array of strings as a fallback
                tag_list = [item for item in data if isinstance(item, str)]
            else:
                QMessageBox.critical(
                    tab,
                    "JSON Format Error",
                    "JSON file must be an object with a 'tags' key containing a list of strings, "
                    "or a direct list of strings.",
                )
                return

            if not tag_list:
                QMessageBox.information(
                    tab, "Import Info", "No valid tags found in the JSON file."
                )
                return

            progress = QProgressDialog(
                "Importing tags...", "Cancel", 0, len(tag_list), tab
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            for i, tag_name_raw in enumerate(tag_list):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                progress.setLabelText(
                    f"Importing tag {i + 1}/{len(tag_list)}: {tag_name_raw[:40]}..."
                )

                tag_name = tag_name_raw.strip()
                if tag_name:
                    tab.db.add_tag(tag_name, tag_type if tag_type else None)
                    imported_tags += 1

            progress.close()

            # Final refresh and update
            tab.refresh_tags_list()
            tab._publish_tag_catalog_changed()
            tab.update_statistics()

            QMessageBox.information(
                tab,
                "Import Success",
                f"Successfully imported and updated {imported_tags} tags with type '{tag_type if tag_type else 'None'}'.",
            )

        except json.JSONDecodeError:
            QMessageBox.critical(
                tab, "File Error", "The selected file is not a valid JSON file."
            )
        except Exception as e:
            QMessageBox.critical(
                tab,
                "Database Error",
                f"An error occurred during tag import:\n{str(e)}",
            )
        finally:
            if "progress" in locals() and progress is not None and progress.isVisible():
                progress.close()


# Backward-compatible alias
_BulkImportMixin = DatabaseBulkImportController

__all__ = ["DatabaseBulkImportController", "_BulkImportMixin"]
