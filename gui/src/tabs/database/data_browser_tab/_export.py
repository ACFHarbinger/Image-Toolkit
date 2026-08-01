"""Export the current grid view as CSV/JSON for ``DataBrowserTab``."""

from __future__ import annotations

import csv
import json

from PySide6.QtWidgets import QFileDialog, QMessageBox


class _ExportMixin:
    """Write ``self.current_columns``/``self.current_rows`` (the currently
    displayed page) out to a file the user picks."""

    def export_csv(self) -> None:
        if not self.current_columns:
            QMessageBox.information(self, "Export CSV", "Nothing to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", f"{self.current_table or 'table'}.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.current_columns)
                writer.writerows(self.current_rows)
            QMessageBox.information(self, "Export CSV", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export CSV", f"Failed to export:\n{e}")

    def export_json(self) -> None:
        if not self.current_columns:
            QMessageBox.information(self, "Export JSON", "Nothing to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export JSON", f"{self.current_table or 'table'}.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            records = [dict(zip(self.current_columns, row)) for row in self.current_rows]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
            QMessageBox.information(self, "Export JSON", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export JSON", f"Failed to export:\n{e}")


__all__ = ["_ExportMixin"]
