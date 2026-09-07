"""Entity directory-import wizard: scan an image dir and auto-create entities.

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from gui.src.constants.listings import LISTING_IMAGES_DIR
from gui.src.elements.database.dialog.entity_directory_import_dialog import _EntityDirectoryImportDialog


class _DirectoryImportMixin:
    """Runs the entity directory-import wizard and creates new entities."""

    @Slot()
    def _on_import_from_directory(self):
        """Open the entity directory-import wizard and create listings for new entities."""
        existing_names = {e.get("name", "").lower() for e in self._entities}
        dlg = _EntityDirectoryImportDialog(existing_names, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected_entities = dlg.get_selected_entities()
        if not selected_entities:
            QMessageBox.information(
                self,
                "Nothing to Import",
                "No entities were selected. Nothing was imported.",
            )
            return

        meta = dlg.get_metadata()
        today = str(date.today())
        created = 0
        new_entities: List[Dict[str, Any]] = []

        # Ensure listing-images directory exists
        LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        for first_name, last_name, src_file_path in selected_entities:
            # Generate unique entity ID
            entity_id = "ent-" + uuid.uuid4().hex[:8]

            # Copy profile image to listing-images directory
            src_path = Path(src_file_path)
            dest_img_name = f"{entity_id}{src_path.suffix}"
            dest_img_path = LISTING_IMAGES_DIR / dest_img_name

            try:
                shutil.copy2(src_path, dest_img_path)
                image_path = str(dest_img_path)
            except Exception as e:
                print(f"Failed to copy entity image: {e}")
                image_path = ""

            entity = {
                "id": entity_id,
                "name": f"{first_name} {last_name}".strip(),
                "first_name": first_name,
                "last_name": last_name,
                "type": meta["type"],
                "role": meta["role"],
                "rating": meta["rating"],
                "year": meta["year"],
                "image_path": image_path,
                "notes": "",
                "credit_list": [],
                "associated_content": [],
                "associated_entities": [],
                "date_added": today,
            }

            self._entities.insert(0, entity)
            new_entities.append(entity)
            created += 1

        if created:
            for entity in new_entities:
                self._upsert_entity(entity)
            self._rebuild_gallery()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {created} new entity"
                f"{'s' if created != 1 else ''}.",
            )
        else:
            QMessageBox.information(
                self,
                "No New Entries",
                "All selected entities already had listings — nothing was added.",
            )


__all__ = ["_DirectoryImportMixin"]
