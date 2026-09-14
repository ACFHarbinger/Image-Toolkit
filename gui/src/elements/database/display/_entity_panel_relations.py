"""Entity detail panel — relations: tags, credits, linked images, associations.

Split from ``entity_detail_panel`` (§5.17 Option B, #629) — pure code
motion, no logic change. Mixed into :class:`_EntityDetailPanel` together
with :mod:`_entity_panel_form`.
"""

from typing import Any, Dict

from backend.src.database.unified.entity_repo import EntityRepo
from backend.src.database.unified.image_repo import ImageRepo
from backend.src.database.unified.media_repo import MediaRepo
from backend.src.database.unified.tag_repo import TagRepo
from gui.src.components.dialogs import AddTagDialog
from gui.src.constants.listings import RATING_STAR_COLOR
from gui.src.elements.database.dialog import (
    _AssociatedContentDialog,
    _AssociatedEntitiesDialog,
)
from gui.src.elements.database.dialog.credit_dialog import _CreditDialog
from gui.src.helpers.database.library_session import get_library_db
from gui.src.helpers.image import apply_thumbnail_to_label
from gui.src.theming.theme_api import qss
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _EntityPanelRelationsMixin:
    """Tags, credits, linked images, and association pickers."""

    def _refresh_grouped_tags_display(self) -> None:
        if not self._entity_id:
            self.grouped_tags_display.set_grouped_tags({})
            return
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            self.grouped_tags_display.set_grouped_tags({})
            return
        try:
            grouped = EntityRepo(db).get_grouped_tags(self._entity_id)
        except Exception as e:
            print(f"Failed to load grouped tags: {e}")
            grouped = {}
        self.grouped_tags_display.set_grouped_tags(grouped)

    def _on_add_tag(self) -> None:
        if not self._entity_id:
            QMessageBox.information(
                self, "Save First", "Save this entity before adding tags."
            )
            return
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(self, "Error", "The library database is not available.")
            return
        try:
            tag_repo = TagRepo(db)
            categories = tag_repo.list_categories(applies_to="entity")
            all_tags = tag_repo.get_all_tags()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tag vocabulary:\n{e}")
            return

        dlg = AddTagDialog(categories, all_tags, parent=self)
        if not dlg.exec():
            return
        name, category = dlg.get_data()
        if not name:
            return
        try:
            EntityRepo(db).add_tag(self._entity_id, name, category)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add tag:\n{e}")
            return
        self._refresh_grouped_tags_display()

    def _refresh_credit_list(self):
        while self.credit_list_layout.count():
            item = self.credit_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        sorted_credits = sorted(
            self._credit_data, key=lambda x: x.get("year", 0), reverse=True
        )

        for cr in sorted_credits:
            row = QFrame()
            row.setStyleSheet(qss("detail_panel_episode_row"))
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)

            title = cr.get("title", "Untitled")
            role = cr.get("role", "")
            year = cr.get("year", 0)
            rating = cr.get("rating", 0)
            img_path = cr.get("image_path", "")

            t_lbl = QLabel()
            t_lbl.setFixedSize(50, 40)
            t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            apply_thumbnail_to_label(
                t_lbl,
                img_path,
                50,
                40,
                worker_size=80,
                placeholder_text="No Img",
                placeholder_component="detail_panel_thumb_placeholder",
            )
            rl.addWidget(t_lbl)

            role_part = f" as <i>{role}</i>" if role else ""
            year_part = f" ({year})" if year else ""
            info = QLabel(f"<b>{title}</b>{role_part}{year_part}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet(qss("database_card_rating_small", STAR_COLOR=RATING_STAR_COLOR))
                rl.addWidget(r_lbl)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setToolTip("Edit credit")
            edit_btn.clicked.connect(lambda _, c=cr: self._edit_credit(c))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove credit record")
            del_btn.clicked.connect(lambda _, cid=cr["id"]: self._remove_credit(cid))
            rl.addWidget(del_btn)

            self.credit_list_layout.addWidget(row)

    def _refresh_linked_images(self) -> None:
        while self.linked_images_layout.count():
            item = self.linked_images_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()  # pyrefly: ignore [missing-attribute]

        if not self._entity_id:
            self.linked_images_layout.addStretch()
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            self.linked_images_layout.addStretch()
            return

        try:
            linked = EntityRepo(db).get_linked_images(self._entity_id)
        except Exception as e:
            print(f"Failed to load linked images: {e}")
            linked = []

        for img in linked:
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)

            thumb = QLabel()
            thumb.setFixedSize(70, 70)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            apply_thumbnail_to_label(
                thumb,
                img["file_path"],
                70,
                70,
                worker_size=100,
                placeholder_text="No Img",
                placeholder_component="detail_panel_thumb_placeholder",
            )
            thumb.setToolTip(img["file_path"])
            cell_layout.addWidget(thumb)

            remove_btn = QPushButton("✕ Unlink")
            remove_btn.setFixedHeight(18)
            remove_btn.setStyleSheet(qss("detail_panel_unlink_btn"))
            remove_btn.clicked.connect(
                lambda _, image_id=img["id"]: self._unlink_image(image_id)
            )
            cell_layout.addWidget(remove_btn)

            self.linked_images_layout.addWidget(cell)

        self.linked_images_layout.addStretch()

    def _link_image(self) -> None:
        if not self._entity_id:
            QMessageBox.information(
                self, "Save First", "Save this entity before linking images."
            )
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(self, "Error", "The library database is not available.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select an Image to Link",
            "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if not file_path:
            return

        try:
            image_repo = ImageRepo(db)
            existing = image_repo.get_image_by_path(file_path)
            image_id = existing["id"] if existing else image_repo.add_image(file_path, tags=[])
            EntityRepo(db).link_image(self._entity_id, image_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to link image:\n{e}")
            return

        self._refresh_linked_images()

    def _unlink_image(self, image_id: int) -> None:
        if not self._entity_id:
            return
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            return
        try:
            EntityRepo(db).unlink_image(self._entity_id, image_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to unlink image:\n{e}")
            return
        self._refresh_linked_images()

    def _add_credit(self):
        dlg = _CreditDialog(parent=self)
        if dlg.exec():
            new_cr = dlg.get_data()
            self._credit_data.append(new_cr)
            self._refresh_credit_list()

    def _edit_credit(self, credit_data: Dict[str, Any]):
        dlg = _CreditDialog(credit_data, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            for i, c in enumerate(self._credit_data):
                if c["id"] == updated["id"]:
                    self._credit_data[i] = updated
                    break
            self._refresh_credit_list()

    def _remove_credit(self, credit_id: str):
        self._credit_data = [c for c in self._credit_data if c["id"] != credit_id]
        self._refresh_credit_list()

    def _refresh_assoc_displays(self) -> None:
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            self.f_assoc_content_display.setPlainText("")
            self.f_assoc_entity_display.setPlainText("")
            return

        try:
            title_map = dict(MediaRepo(db).list_ids_and_titles())
            name_map = EntityRepo(db).name_map()

            content_names = [title_map.get(i, i) for i in self.assoc_content_ids]
            self.f_assoc_content_display.setPlainText(", ".join(content_names))

            entity_names = [name_map.get(i, i) for i in self.assoc_entity_ids]
            self.f_assoc_entity_display.setPlainText(", ".join(entity_names))
        except Exception as e:
            print(f"Failed to refresh assoc displays: {e}")
            self.f_assoc_content_display.setPlainText(
                f"{len(self.assoc_content_ids)} linked"
            )
            self.f_assoc_entity_display.setPlainText(
                f"{len(self.assoc_entity_ids)} linked"
            )

    def _select_associated_content(self) -> None:
        entries = []
        db = get_library_db(self.vault_manager, parent=self)
        if db is not None:
            try:
                entries = MediaRepo(db).list_media()
            except Exception as e:
                print(f"Failed to load content for association: {e}")

        if not entries:
            QMessageBox.information(
                self,
                "No Content Available",
                "There are no content entries in Series Listings yet.",
            )
            return

        dlg = _AssociatedContentDialog(entries, self.assoc_content_ids, parent=self)
        if dlg.exec():
            self.assoc_content_ids = dlg.get_selected_ids()
            self._refresh_assoc_displays()

    def _select_associated_entities(self) -> None:
        entities = []
        db = get_library_db(self.vault_manager, parent=self)
        if db is not None:
            try:
                entities = EntityRepo(db).list_entities()
            except Exception as e:
                print(f"Failed to load entities for association: {e}")

        if self._entity_id:
            entities = [e for e in entities if e.get("id") != self._entity_id]

        if not entities:
            QMessageBox.information(
                self,
                "No Entities Available",
                "There are no other entities available to associate.",
            )
            return

        dlg = _AssociatedEntitiesDialog(entities, self.assoc_entity_ids, parent=self)
        if dlg.exec():
            self.assoc_entity_ids = dlg.get_selected_ids()
            self._refresh_assoc_displays()


__all__ = ["_EntityPanelRelationsMixin"]
