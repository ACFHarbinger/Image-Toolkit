"""Directory-import wizard: scan a video dir and auto-create listings.

Extracted from ``series_listings_subtab.py`` -- pure code motion, no logic
change, plus DB.8d (docs/moon/roadmaps/unified_database.md, issue #66): the
whole batch of newly-created series now commits in a single transaction
(previously one implicit transaction per ``save_media()`` call, via
``_upsert_entry()``), and a series whose name exactly matches an existing
image ``groups`` row gets that ``media_groups`` link pre-filled --
mirrors ``scan_metadata_tab/_auto_listings.py``'s sibling feature for the
image-group side.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List

from backend.src.database.unified.media_repo import MediaRepo
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from gui.src.elements.database.dialog.directory_import_dialog import _DirectoryImportDialog
from gui.src.helpers.database.library_session import get_library_db


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

        raw_db = get_library_db(self.vault_manager, parent=self)
        if raw_db is None:
            QMessageBox.warning(
                self,
                "Not Saved",
                "The vault is locked (no active password), so nothing was "
                "imported.",
            )
            return

        scan_result = dlg.get_scan_result()
        meta = dlg.get_metadata()
        today = str(date.today())
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
            new_entries.append(entry)

        if not new_entries:
            QMessageBox.information(
                self,
                "No New Entries",
                "All selected series already had listings — nothing was added.",
            )
            return

        media_repo = MediaRepo(raw_db)
        # Case-insensitive series-name -> image-group-id map, for the
        # media_groups auto-link below (DB.8d) -- built once, not once per
        # series, so a large import doesn't repeat the group scan.
        group_id_by_name = {}
        try:
            for row in raw_db.query(
                "SELECT id, name FROM groups", ()
            ):
                group_id_by_name[row[1].strip().lower()] = row[0]
        except Exception:
            group_id_by_name = {}

        created = 0
        try:
            raw_db.begin()
            for entry in new_entries:
                media_repo.save_media(entry)
                created += 1
                group_id = group_id_by_name.get(entry["title"].strip().lower())
                if group_id is not None:
                    media_repo.link_group(entry["id"], group_id)
            raw_db.commit()
        except Exception as e:
            raw_db.rollback()
            QMessageBox.critical(
                self,
                "Import Failed",
                f"Failed to import series to the library database:\n{e}\n\n"
                "No entries were saved (the whole batch was rolled back).",
            )
            return

        for entry in new_entries:
            self._entries.insert(0, entry)
        self._rebuild_gallery()
        QMessageBox.information(
            self,
            "Import Complete",
            f"Successfully imported {created} new listing"
            f"{'s' if created != 1 else ''}.",
        )


__all__ = ["_DirectoryImportMixin"]
