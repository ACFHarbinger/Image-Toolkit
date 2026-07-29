"""Browse-for-image and generate-thumbnail (from local file/video) actions.

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gui.src.components.dialogs.frame_selection_dialog import FrameSelectionDialog
from gui.src.constants.listings import LISTING_IMAGES_DIR
from gui.src.helpers.image.card_thumb_worker import invalidate_thumbnail_cache
from PySide6.QtWidgets import QDialog, QMessageBox


class _ImageActionsMixin:
    """Browse for a manual image, or auto-generate one from the local file."""

    def _browse_image(self):
        self._image_path = self._browse_image_helper(self._entry_id)  # pyrefly: ignore [bad-argument-type]

    def _generate_thumbnail(self):
        file_path = self.f_local_file.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "No Local File",
                "Please specify a valid Local File first to generate a thumbnail.",
            )
            return

        p = Path(file_path)
        if not p.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The local file at '{file_path}' does not exist.",
            )
            return

        suffix = p.suffix.lower()
        LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self._entry_id = self._entry_id or str(uuid.uuid4())
        dest_p = LISTING_IMAGES_DIR / f"{self._entry_id}.png"

        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            try:
                shutil.copy2(file_path, dest_p)
                self._image_path = str(dest_p.absolute())
                invalidate_thumbnail_cache(self._image_path)
                self._refresh_image()
                QMessageBox.information(self, "Success", "Image set as thumbnail successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to set image: {e}")
            return

        if suffix in (".pdf", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
            dlg = FrameSelectionDialog(file_path, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_image:
                if dlg.selected_image.save(str(dest_p.absolute())):
                    self._image_path = str(dest_p.absolute())
                    invalidate_thumbnail_cache(self._image_path)
                    self._refresh_image()
                    QMessageBox.information(
                        self,
                        "Success",
                        "Successfully saved selected representative thumbnail!",
                    )
                else:
                    QMessageBox.critical(self, "Error", "Failed to save selected thumbnail image.")
            return

        QMessageBox.warning(
            self,
            "Unsupported Format",
            "This file format is not supported for generating a thumbnail.",
        )


__all__ = ["_ImageActionsMixin"]
