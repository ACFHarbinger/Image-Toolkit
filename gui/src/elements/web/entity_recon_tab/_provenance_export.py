"""JSON/CSV provenance-report export.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.web.recon import export_provenance
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ....constants import DIALOG_OPTS


class _ProvenanceExportMixin:
    """Exports the last resolved provenance report to JSON or CSV."""

    def _export(self, fmt: str):
        if self._report is None:
            self._set_status("Nothing to export yet.")
            return
        ext = "csv" if fmt == "csv" else "json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Provenance", f"provenance.{ext}", f"{ext.upper()} (*.{ext})", options=DIALOG_OPTS
        )
        if not path:
            return
        try:
            export_provenance(self._report, path, fmt=ext)
            self._set_status(f"Exported provenance to {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", str(e))


__all__ = ["_ProvenanceExportMixin"]
