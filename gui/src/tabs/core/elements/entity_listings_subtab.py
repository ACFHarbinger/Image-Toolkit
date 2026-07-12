import contextlib
import logging
import os
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import backend.src.constants as udef
from backend.src.database.unified.entity_repo import EntityRepo
from backend.src.database.unified.media_repo import MediaRepo
from gui.src.constants.listings import (
    CARD_SIZE,
    ENTITY_ROLES,
    ENTITY_TYPES,
    LISTING_IMAGES_DIR,
)
from gui.src.helpers.core.library_session import get_library_db
from gui.src.helpers.web.sync_backup_worker import _SyncBackupWorker
from gui.src.styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from gui.src.tabs.core.elements.common.listings_common import (
    _persist_splitter,
)
from gui.src.tabs.core.elements.dialog.entity_directory_import_dialog import _EntityDirectoryImportDialog
from gui.src.tabs.core.elements.display.entity_card import _EntityCard
from gui.src.tabs.core.elements.display.entity_detail_panel import _EntityDetailPanel
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class EntityListingsSubTab(QWidget):
    listings_changed = Signal()  # emitted when listings.json is updated by cross-sync

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entities: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_role = "All"
        self._search_query = ""

        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("👥 Entity Listings")
        title_lbl.setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search entities…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTITY_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_filter)
        toolbar.addWidget(self.type_combo)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["All Roles"] + ENTITY_ROLES)
        self.role_combo.currentTextChanged.connect(self._on_role_filter)
        toolbar.addWidget(self.role_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Sort by: Name",
                "Sort by: Rating",
                "Sort by: Type",
                "Sort by: Role",
                "Sort by: Date Added",
                "Sort by: Credits Count",
            ]
        )
        self.sort_combo.setFixedWidth(150)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItems(["Ascending", "Descending"])
        self.sort_order_combo.setFixedWidth(100)
        self.sort_order_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_order_combo)

        # ── Pair 1: Add Entity (top) / Import Dir (bottom) ──────────────
        entity_pair = QWidget()
        entity_pair_vbox = QVBoxLayout(entity_pair)
        entity_pair_vbox.setContentsMargins(0, 0, 0, 0)
        entity_pair_vbox.setSpacing(3)

        add_btn = QPushButton("＋ Add Entity")
        add_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self._on_add_new)
        apply_shadow_effect(add_btn)

        import_dir_btn = QPushButton("📂 Import Dir")
        import_dir_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        import_dir_btn.setFixedWidth(120)
        import_dir_btn.setToolTip(
            "Scan an entity image directory and auto-create listings."
        )
        import_dir_btn.clicked.connect(self._on_import_from_directory)
        apply_shadow_effect(import_dir_btn)

        entity_pair_vbox.addWidget(add_btn)
        entity_pair_vbox.addWidget(import_dir_btn)
        toolbar.addWidget(entity_pair)

        # ── Pair 2: Sync Backup (top) / Update Backup (bottom) ─────────
        backup_pair = QWidget()
        backup_pair_vbox = QVBoxLayout(backup_pair)
        backup_pair_vbox.setContentsMargins(0, 0, 0, 0)
        backup_pair_vbox.setSpacing(3)

        sync_btn = QPushButton("🔄 Sync Backup")
        sync_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        sync_btn.setFixedWidth(130)
        sync_btn.clicked.connect(self._synchronize_listings)
        apply_shadow_effect(sync_btn)

        update_btn = QPushButton("⚡ Update Backup")
        update_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        update_btn.setFixedWidth(130)
        update_btn.clicked.connect(self._update_encrypted_backup)
        apply_shadow_effect(update_btn)

        backup_pair_vbox.addWidget(sync_btn)
        backup_pair_vbox.addWidget(update_btn)
        toolbar.addWidget(backup_pair)

        root.addLayout(toolbar)

        # ---- Stats bar ----
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#888;font-size:11px;")
        root.addWidget(self.stats_label)

        # ---- Splitter: gallery | detail ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Gallery
        gallery_container = QWidget()
        gallery_vbox = QVBoxLayout(gallery_container)
        gallery_vbox.setContentsMargins(0, 0, 0, 0)
        gallery_vbox.setSpacing(0)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#23272a;}"
        )
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:#23272a;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self.gallery_scroll.setWidget(self._grid_widget)
        gallery_vbox.addWidget(self.gallery_scroll)
        splitter.addWidget(gallery_container)

        # Detail panel (wrapped in a scroll area)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#2c2f33;}"
        )
        self._detail = _EntityDetailPanel(vault_manager=self.vault_manager)
        self._detail.saved.connect(self._on_entity_saved)
        self._detail.deleted.connect(self._on_entity_deleted)
        detail_scroll.setWidget(self._detail)
        splitter.addWidget(detail_scroll)
        _persist_splitter(splitter, "EntityListingsSubTab_main")

        splitter.setSizes([680, 340])
        splitter.setHandleWidth(6)
        root.addWidget(splitter, 1)

        # Context Menu for Gallery background
        self.gallery_scroll.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gallery_scroll.customContextMenuRequested.connect(
            self._show_gallery_context_menu
        )

        # ---- Load data ----
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

        # Debounced resize for EntityListingsSubTab.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._rebuild_gallery)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_data(self):
        self._entities = []

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            return
        try:
            self._entities = EntityRepo(db).list_entities()
        except Exception as e:
            logging.exception("[EntityListingsSubTab] Failed to load from library DB")
            QMessageBox.critical(
                self,
                "Library Database Unavailable",
                "Could not load entities from the unified library database:\n"
                f"{e}\n\n"
                "Your existing entities may not be visible, and anything "
                "added or changed in this session will NOT be saved until "
                "this is fixed. Check the app log for details.",
            )

    def _entity_repo(self) -> Optional[EntityRepo]:
        """Return an EntityRepo on the session DB, or None when the vault is locked."""
        db = get_library_db(self.vault_manager, parent=self)
        return EntityRepo(db) if db is not None else None

    def _upsert_entity(self, entity: Dict[str, Any]) -> bool:
        """Persist a single entity in one transaction — the entity row, its
        credits, and both association directions commit (or roll back)
        together via :meth:`EntityRepo.save_entity`.

        Returns ``True`` on success. Callers MUST check this — silently
        swallowing the error here previously meant a newly added entity could
        look saved while never actually reaching disk, only to vanish the
        next time the app was launched."""
        repo = self._entity_repo()
        if repo is None:
            QMessageBox.warning(
                self,
                "Not Saved",
                "The vault is locked (no active password), so this entity was "
                "NOT written to the library database. It will be lost when "
                "you close the app.",
            )
            return False
        try:
            repo.save_entity(entity)
            return True
        except Exception as e:
            logging.exception("[EntityListingsSubTab] Failed to upsert entity")
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save '{entity.get('name', '')}' to the library "
                f"database:\n{e}\n\n"
                "This entity was NOT persisted and will be lost on restart.",
            )
            return False

    def _delete_entity_row(self, entity_id: str) -> bool:
        """Delete a single entity row; credits and association rows cascade."""
        repo = self._entity_repo()
        if repo is None:
            return False
        try:
            repo.delete_entity(entity_id)
            return True
        except Exception as e:
            logging.exception("[EntityListingsSubTab] Failed to delete entity")
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete entity from the library database:\n{e}",
            )
            return False

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _filtered_entities(self) -> List[Dict[str, Any]]:  # noqa: C901
        result = self._entities
        if self._filter_type and self._filter_type not in (
            "All",
            "All Types",
            "None",
            "",
        ):
            result = [e for e in result if e.get("type") == self._filter_type]
        if self._filter_role not in ("All", "All Roles"):
            result = [e for e in result if e.get("role") == self._filter_role]
        if self._search_query:
            q = self._search_query.lower()
            content_titles_map: Dict[str, str] = {}
            db = get_library_db(self.vault_manager, parent=self)
            if db is not None:
                with contextlib.suppress(Exception):
                    content_titles_map = {
                        media_id: (title or "").lower()
                        for media_id, title in MediaRepo(db).list_ids_and_titles()
                    }

            filtered_ents = []
            for e in result:
                if q in e.get("name", "").lower() or q in e.get("notes", "").lower():
                    filtered_ents.append(e)
                    continue
                # Search associated_content (list of IDs → resolve titles)
                assoc_c = e.get("associated_content", [])
                if isinstance(assoc_c, list):
                    if any(q in content_titles_map.get(cid, "") for cid in assoc_c):
                        filtered_ents.append(e)
                        continue
                else:
                    if q in str(assoc_c).lower():
                        filtered_ents.append(e)
                        continue
            result = filtered_ents

        # Sorting logic
        sort_text = self.sort_combo.currentText()
        is_descending = self.sort_order_combo.currentText() == "Descending"

        def get_sort_key(entity):
            if "Name" in sort_text:
                return (entity.get("name") or "").lower()
            elif "Rating" in sort_text:
                return entity.get("rating") or 0
            elif "Type" in sort_text:
                return (entity.get("type") or "").lower()
            elif "Role" in sort_text:
                return (entity.get("role") or "").lower()
            elif "Date Added" in sort_text:
                return entity.get("date_added") or ""
            elif "Credits Count" in sort_text:
                return len(entity.get("credit_list") or [])
            return (entity.get("name") or "").lower()

        result = sorted(result, key=get_sort_key, reverse=is_descending)
        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        visible = self._filtered_entities()

        if not visible:
            placeholder = QLabel(
                "No entities found.\nClick '＋ Add Entity' to get started."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entity in enumerate(visible):
                card = _EntityCard(entity)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entities)
        completed = sum(1 for e in self._entities if e.get("rating", 0) >= 8)
        self.stats_label.setText(
            f"{total} entities total · {completed} highly rated (>=8) · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def showEvent(self, event):
        super().showEvent(event)

    def _on_sort_changed(self, text):
        self._rebuild_gallery()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    @Slot(str)
    def _on_card_clicked(self, entity_id: str):
        self._selected_id = entity_id
        entity = next((e for e in self._entities if e["id"] == entity_id), None)
        if entity:
            self._detail.load_entity(entity)

    def _on_card_delete_requested(self, entity_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entity from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_entity_deleted(entity_id)

    def _show_gallery_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

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

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entity_saved(self, entity: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entities) if e["id"] == entity["id"]), None
        )
        if idx is not None:
            self._entities[idx] = entity
        else:
            self._entities.insert(0, entity)
        # save_entity writes the entity, its credits, its media links and its
        # peer links in one transaction; the content side reads the same
        # media_entity table, so the old sync loops are gone. Peer entities'
        # in-memory dicts may now be stale — reload from the store.
        if self._upsert_entity(entity):
            self._load_data()
        self.listings_changed.emit()
        self._rebuild_gallery()
        self._detail.load_entity(entity)

    @Slot(str)
    def _on_entity_deleted(self, entity_id: str):
        self._entities = [e for e in self._entities if e["id"] != entity_id]
        # FK cascades remove this entity's credits and association rows
        # (media_entity + entity_entity, both directions).
        self._delete_entity_row(entity_id)
        self.listings_changed.emit()
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    def _on_external_reload(self) -> None:
        """Called when another subtab modifies entities.json; refreshes in-memory data."""
        self._load_data()
        self._rebuild_gallery()

    @Slot(str)
    def _on_search(self, text: str):
        self._search_query = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_type_filter(self, text: str):
        self._filter_type = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_role_filter(self, text: str):
        self._filter_role = text
        self._rebuild_gallery()

    @Slot()
    def _synchronize_listings(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to sync.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                "No encrypted entities backup file found to synchronize from. Use 'Update Backup' first to generate it.",
            )
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(
                self,
                "Library Unavailable",
                "The unified library database could not be opened; cannot sync.",
            )
            return

        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            "Starting synchronization...", "", 0, 100, self
        )
        self.progress_dialog.setWindowTitle("Synchronizing Backup")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setWindowFlags(
            self.progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        self.progress_dialog.show()

        # Start background thread
        self._sync_worker = _SyncBackupWorker(
            "sync",
            "Entity",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "local_entries": self._entities,
                "db": db,
            },
        )
        self._sync_worker.progress.connect(self._on_sync_progress)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.start()

    def _on_sync_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_sync_finished(self, success, message, result_data):
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None # pyrefly: ignore [bad-assignment]

        if success:
            merged_entries, synced_imgs = result_data
            self._entities = merged_entries
            self._rebuild_gallery()

            img_info = (
                f"\nAlso restored {synced_imgs} missing image(s) from backup."
                if synced_imgs
                else ""
            )
            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized entities!\nMerged local and backup entries to a total of {len(merged_entries)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Sync Error",
                f"An error occurred during synchronization:\n{message}",
            )

    @Slot()
    def _update_encrypted_backup(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to update backup.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        # Create progress dialog
        self.progress_dialog = QProgressDialog("Starting backup...", "", 0, 100, self)
        self.progress_dialog.setWindowTitle("Updating Backup")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setWindowFlags(
            self.progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        self.progress_dialog.show()

        # Start background thread
        self._backup_worker = _SyncBackupWorker(
            "backup",
            "Entity",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "entries": self._entities,
            },
        )
        self._backup_worker.progress.connect(self._on_backup_progress)
        self._backup_worker.finished.connect(self._on_backup_finished)
        self._backup_worker.start()

    def _on_backup_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_backup_finished(self, success, message, result_data):
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None # pyrefly: ignore [bad-assignment]

        if success:
            backup_count = result_data
            img_info = (
                f"\nAlso backed up {backup_count} image(s) to multi-part archive."
                if backup_count
                else ""
            )
            QMessageBox.information(
                self,
                "Backup Updated",
                f"Successfully generated encrypted backup entities file with {len(self._entities)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred while generating backup:\n{message}",
            )

