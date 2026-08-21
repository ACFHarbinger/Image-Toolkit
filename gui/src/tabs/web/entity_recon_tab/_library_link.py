"""Link a "local" identity-resolution match to a library entity (DB.8b).

Extracted as its own mixin -- bridges base.recon IdentityIndex hits into
entity_images, the same M2M table the entity detail panel's "Linked
Images" gallery strip (DB.8b, an earlier round) already reads/writes via
EntityRepo.link_image()/get_linked_images().

This tab has never had any access to the unified library session before
this file. It is NOT constructed with a vault_manager (see
gui/src/windows/main/_tab_registry.py -- EntityReconTab() takes no
args), so rather than threading that through (out of scope for this
round -- another work stream owns gui/src/windows/main/ changes right
now), this reads the session directly via
backend.src.database.unified.session.is_open()/get_session(): if the
vault has already been unlocked and the library opened elsewhere in the
app (the normal case once any other Library-category tab has run), the
session is already there to use; if not, this shows a clear message
instead of silently failing.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox


class _LibraryLinkMixin:
    """Right-click "Link to Library Entity" on a local provenance match."""

    def _on_prov_context_menu(self, pos) -> None:
        item = self.prov_tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data[0] != "local":
            return
        path = data[1]

        menu = QMenu(self)
        link_action = menu.addAction("🔗 Link to Library Entity")
        action = menu.exec(self.prov_tree.viewport().mapToGlobal(pos))
        if action == link_action:
            self._link_match_to_library(path)

    def _link_match_to_library(self, path: str) -> None:
        from backend.src.database.unified import session

        if not session.is_open():
            QMessageBox.information(
                self,
                "Library Not Open",
                "The unified library isn't open yet. Open the Database or "
                "Listings tab first (this unlocks it for the whole app), "
                "then try linking again.",
            )
            return

        name = self.name_label.text().strip()
        if not name or name == "Unknown":
            QMessageBox.information(
                self, "No Identity", "Resolve an identity with a known name first."
            )
            return

        import os

        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"File not found:\n{path}")
            return

        db = session.get_session()
        from backend.src.database.unified.entity_repo import EntityRepo
        from backend.src.database.unified.image_repo import ImageRepo

        image_repo = ImageRepo(db)
        entity_repo = EntityRepo(db)

        try:
            image_row = image_repo.get_image_by_path(path)
            image_id = image_row["id"] if image_row else image_repo.add_image(path, tags=[])

            entity_id = self._resolve_entity_id(entity_repo, name)
            if entity_id is None:
                return  # user cancelled

            entity_repo.link_image(entity_id, image_id)
            QMessageBox.information(
                self, "Linked", f"Linked this image to entity '{name}'."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to link image to entity:\n{e}")

    def _resolve_entity_id(self, entity_repo, name: str) -> Optional[str]:
        """Find (or, with confirmation, create) the entity matching *name*.

        A simple case-insensitive substring ranker, same spirit as
        MediaRepo.suggest_group_matches() elsewhere in this roadmap --
        good enough for a human-confirmed pick, not a full fuzzy-match
        library. A human always confirms before link_image()/save_entity()
        actually run.
        """
        name_map = entity_repo.name_map()  # {entity_id: name}
        norm_target = " ".join(name.lower().replace("_", " ").split())

        candidates: List[tuple] = []
        for entity_id, entity_name in name_map.items():
            norm_candidate = " ".join((entity_name or "").lower().split())
            if not norm_candidate:
                continue
            if norm_candidate == norm_target:
                candidates.insert(0, (entity_id, entity_name))  # exact match first
            elif norm_candidate in norm_target or norm_target in norm_candidate:
                candidates.append((entity_id, entity_name))

        if candidates:
            if len(candidates) == 1 or candidates[0][1].lower() == norm_target:
                entity_id, entity_name = candidates[0]
                confirm = QMessageBox.question(
                    self,
                    "Link to Entity",
                    f"Link this image to existing entity '{entity_name}'?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                return entity_id if confirm == QMessageBox.StandardButton.Yes else None

            labels = [f"{n}" for _, n in candidates]
            choice, ok = QInputDialog.getItem(
                self,
                "Link to Entity",
                f"Multiple entities are close to '{name}'. Pick one, or "
                "cancel to create a new entity instead:",
                labels,
                editable=False,
            )
            if ok and choice:
                for entity_id, entity_name in candidates:
                    if entity_name == choice:
                        return entity_id
            return None

        confirm = QMessageBox.question(
            self,
            "Create Entity",
            f"No entity named '{name}' exists in the library yet. Create "
            "one and link this image to it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return None
        return entity_repo.save_entity({"name": name})


__all__ = ["_LibraryLinkMixin"]
