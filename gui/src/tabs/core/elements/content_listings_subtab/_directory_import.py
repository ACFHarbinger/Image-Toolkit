"""Directory-import wizard: scan a video dir and auto-create listings.

Extracted from ``content_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List

from gui.src.tabs.core.elements.dialog.directory_import_dialog import _DirectoryImportDialog
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox


class _DirectoryImportMixin:
    """Runs the directory-import wizard and creates listings for new series."""

    @Slot()
    def _on_import_from_directory(self):
        """Open the directory-import wizard and create listings for new series."""
        existing_titles = {e.get("title", "").lower() for e in self._entries}
        dlg = _DirectoryImportDialog(existing_titles, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected_series = dlg.get_selected_series()
        if not selected_series:
            QMessageBox.information(
                self,
                "Nothing to Import",
                "No series were selected. Nothing was imported.",
            )
            return

        scan_result = dlg.get_scan_result()
        meta = dlg.get_metadata()
        today = str(date.today())
        created = 0
        new_entries: List[Dict[str, Any]] = []

        for series_name in selected_series:
            episodes = scan_result.get(series_name, [])
            if not episodes:
                continue

            # Build the per-episode sub-list
            episode_list = []
            for idx, (ep_num, file_path) in enumerate(episodes):
                episode_list.append(
                    {
                        "id": str(uuid.uuid4()),
                        "number": ep_num if ep_num is not None else (idx + 1),
                        "title": "",
                        "date_watched": today,
                        "rating": 0,
                        "review": "",
                        "image_path": "",
                        "local_file": file_path,
                        "web_link": "",
                    }
                )

            entry = {
                "id": str(uuid.uuid4()),
                "title": series_name,
                "type": meta["type"],
                "status": meta["status"],
                "personal_rating": 0,
                "community_rating": 0.0,
                "year": meta["year"],
                "episodes": len(episodes),
                "current_episode": 0,
                "genres": meta["genres"],
                "tags": meta["tags"],
                "creator": meta.get("creator", ""),
                "associated_entities": [],
                # First episode's file is the series-level local file
                "local_file": episodes[0][1],
                "web_link": "",
                "review": "",
                "image_path": "",
                "episode_list": episode_list,
                "date_added": today,
            }
            self._entries.insert(0, entry)
            new_entries.append(entry)
            created += 1

        if created:
            for entry in new_entries:
                self._upsert_entry(entry)
            self._rebuild_gallery()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {created} new listing"
                f"{'s' if created != 1 else ''}.",
            )
        else:
            QMessageBox.information(
                self,
                "No New Entries",
                "All selected series already had listings — nothing was added.",
            )


__all__ = ["_DirectoryImportMixin"]
