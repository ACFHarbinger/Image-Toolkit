"""Bulk JSON tag import methods for ``DatabaseTab``.

Extracted from ``database_tab.py`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog


class _BulkImportMixin:
    """Browse for and import a JSON tag list into the database."""

    def browse_json_file(self):
        """Opens a file dialog to select a JSON file."""
        initial_dir = Path(os.getcwd())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select JSON Tags File",
            str(initial_dir),
            "JSON Files (*.json);;All Files (*.*)",
        )
        if file_path:
            self.json_file_path_edit.setText(file_path)

    def import_tags_from_json(self):
        """Reads the selected JSON file and imports tags into the database."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return

        file_path = self.json_file_path_edit.text().strip()
        tag_type = self.bulk_tag_type_combo.currentText().strip().title()

        if not file_path or not Path(file_path).is_file():
            QMessageBox.warning(self, "Error", "Please select a valid JSON file.")
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
                    self,
                    "JSON Format Error",
                    "JSON file must be an object with a 'tags' key containing a list of strings, "
                    "or a direct list of strings.",
                )
                return

            if not tag_list:
                QMessageBox.information(
                    self, "Import Info", "No valid tags found in the JSON file."
                )
                return

            progress = QProgressDialog(
                "Importing tags...", "Cancel", 0, len(tag_list), self
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
                    self.db.add_tag(tag_name, tag_type if tag_type else None)
                    imported_tags += 1

            progress.close()

            # Final refresh and update
            self.refresh_tags_list()
            self._publish_tag_catalog_changed()
            self.update_statistics()

            QMessageBox.information(
                self,
                "Import Success",
                f"Successfully imported and updated {imported_tags} tags with type '{tag_type if tag_type else 'None'}'.",
            )

        except json.JSONDecodeError:
            QMessageBox.critical(
                self, "File Error", "The selected file is not a valid JSON file."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"An error occurred during tag import:\n{str(e)}",
            )
        finally:
            if "progress" in locals() and progress is not None and progress.isVisible():
                progress.close()


__all__ = ["_BulkImportMixin"]
