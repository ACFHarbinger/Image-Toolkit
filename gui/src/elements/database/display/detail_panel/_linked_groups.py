"""DB.8a: "Linked Image Groups" section -- link/unlink a media entry to
image groups from the image domain (``media_groups`` M2M).

Unlike associated-entities (a staged list synced to entity_entity only on
Save), links here are written immediately via MediaRepo.link_group/
unlink_group -- there is no bulk "set" API for this table (deliberately;
DB.1's design collapses M2M sync into direct INSERT OR IGNORE/DELETE
statements instead of diff-then-reupsert loops), and immediate writes
need no unsaved-entry special-casing beyond requiring self._entry_id to
already exist (a brand-new, not-yet-saved entry has no media_item_id row
for the FK to reference -- the section stays hidden until then, same
gating as del_btn/episode_group in _entry_lifecycle.py).
"""

from __future__ import annotations

from typing import List

from backend.src.database.unified.image_repo import ImageRepo
from backend.src.database.unified.media_repo import MediaRepo
from gui.src.helpers.database.library_session import get_library_db
from gui.src.elements.database.dialog import _LinkedGroupsDialog
from PySide6.QtWidgets import QInputDialog, QMessageBox


class _LinkedGroupsMixin:
    """Chip-row display + link/unlink dialog for media <-> image groups."""

    def _refresh_linked_groups_display(self) -> None:
        if not self._entry_id:
            self.f_linked_groups_display.setPlainText("")
            self.f_linked_groups_display.setToolTip("")
            return

        names: List[str] = []
        db = get_library_db(self.vault_manager, parent=self)
        if db is not None:
            try:
                names = [g["name"] for g in MediaRepo(db).get_linked_groups(self._entry_id)]
            except Exception as e:
                print(f"Failed to load linked image groups: {e}")

        display_text = ", ".join(names) if names else ""
        self.f_linked_groups_display.setPlainText(display_text)
        self.f_linked_groups_display.setToolTip(display_text)

    def _select_linked_groups(self) -> None:  # noqa: C901
        if not self._entry_id:
            QMessageBox.information(
                self,
                "Save First",
                "Save this entry before linking it to image groups.",
            )
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(self, "Error", "The library database is not available.")
            return

        try:
            media_repo = MediaRepo(db)
            image_repo = ImageRepo(db)
            all_group_names = image_repo.get_all_groups()
            linked = media_repo.get_linked_groups(self._entry_id)
            linked_names = [g["name"] for g in linked]
            suggested_names = media_repo.suggest_group_matches(
                self.f_title.text(), all_group_names
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image groups:\n{e}")
            return

        if not all_group_names:
            QMessageBox.information(
                self,
                "No Image Groups",
                "There are no image groups in the library yet. Create one from "
                "the Library Management tab first.",
            )
            return

        dlg = _LinkedGroupsDialog(all_group_names, linked_names, suggested_names, parent=self)
        if not dlg.exec():
            return

        new_names = set(dlg.get_selected_names())
        old_names = set(linked_names)
        changed_names = new_names ^ old_names
        try:
            # add_group() is INSERT OR IGNORE + SELECT id -- idempotent,
            # cheap to call again for names that already exist. Only
            # resolve ids for names actually changing, not every group.
            id_for_name = {name: image_repo.add_group(name) for name in changed_names}
            for name in new_names - old_names:
                media_repo.link_group(self._entry_id, id_for_name[name])
            for name in old_names - new_names:
                media_repo.unlink_group(self._entry_id, id_for_name[name])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update image group links:\n{e}")
            return

        self._refresh_linked_groups_display()

    def _view_linked_group_images(self) -> None:
        """DB.8a: "View Images" -- switch MainWindow to the Search tab and
        pre-filter it to one of this entry's linked image groups. Uses the
        real tab-activation mechanism MainWindow's Ctrl+T tab search already
        exercises (command_combo + _select_tab_by_name) -- see
        gui/src/windows/main/_tab_search.py's _activate() -- via
        main_window_ref, threaded down from MainWindow through ListingsTab
        -> SeriesListingsSubTab -> this panel (mirrors the existing
        search_tab_ref/merge_tab_ref cross-tab-reference pattern)."""
        if not self._entry_id:
            return
        if self.main_window_ref is None:
            QMessageBox.warning(
                self, "Error", "Main window reference not available."
            )
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(self, "Error", "The library database is not available.")
            return

        try:
            linked = MediaRepo(db).get_linked_groups(self._entry_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image groups:\n{e}")
            return

        if not linked:
            QMessageBox.information(
                self, "No Linked Groups", "This entry has no linked image groups yet."
            )
            return

        if len(linked) == 1:
            group_name = linked[0]["name"]
        else:
            names = [g["name"] for g in linked]
            group_name, ok = QInputDialog.getItem(
                self, "View Images", "Which linked group?", names, editable=False,
            )
            if not ok or not group_name:
                return

        mw = self.main_window_ref
        mw.command_combo.setCurrentText("Library Database")
        mw._select_tab_by_name("Image Search")
        mw.search_tab.filter_by_group(group_name)


__all__ = ["_LinkedGroupsMixin"]
