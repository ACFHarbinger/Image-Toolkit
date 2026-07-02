import os
import json
import uuid
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from send2trash import send2trash # pyrefly: ignore [untyped-import]
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QScrollArea,
    QSplitter,
    QGridLayout,
    QMessageBox,
    QMenu,
    QProgressDialog,
    QPushButton,
    QDialog,
)
from PySide6.QtGui import QAction

import base
import backend.src.constants as udef
from backend.src.constants import IMAGE_TOOLKIT_DIR

from gui.src.helpers.core.recommendation_worker import RecommendationWorker
from gui.src.styles import apply_shadow_effect, SHARED_BUTTON_STYLE
from gui.src.constants.listings import (
    ENTRY_TYPES,
    ENTRY_STATUS,
    CARD_SIZE,
)

from gui.src.tabs.core.elements.common.listings_common import (
    _persist_splitter,
)
from gui.src.helpers.web.sync_backup_worker import _SyncBackupWorker
from gui.src.tabs.core.elements.dialog.episode_dialog import _EpisodeDialog
from gui.src.tabs.core.elements.display.listing_card import _ListingCard
from gui.src.tabs.core.elements.display.detail_panel import _DetailPanel
from gui.src.tabs.core.elements.dialog.advanced_search_dialog import _AdvancedSearchDialog
from gui.src.tabs.core.elements.dialog.directory_import_dialog import _DirectoryImportDialog
from gui.src.tabs.core.elements.dialog.recommendation_dialog import _RecommendationDialog


class ContentListingsSubTab(QWidget):
    entities_changed = Signal()  # emitted when entities.json is updated by cross-sync

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entries: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_status = "All"
        self._search_query = ""
        self._advanced_search_criteria = None

        # Vector search state
        self._recommendation_results: Optional[List[Tuple[str, float]]] = None
        self._active_rec_worker = None

        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("🎬 Content Listings")
        title_lbl.setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search titles…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        # ── Search / Recommend pair (stacked vertically) ─────────────
        _search_rec_pair = QWidget()
        _search_rec_vbox = QVBoxLayout(_search_rec_pair)
        _search_rec_vbox.setContentsMargins(0, 0, 0, 0)
        _search_rec_vbox.setSpacing(3)

        adv_search_btn = QPushButton("🔍 Advanced")
        adv_search_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        adv_search_btn.setFixedWidth(120)
        adv_search_btn.clicked.connect(self._on_advanced_search)
        apply_shadow_effect(adv_search_btn)

        rec_btn = QPushButton("🌟 Recommend")
        rec_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        rec_btn.setFixedWidth(120)
        rec_btn.clicked.connect(self._on_recommend_content)
        apply_shadow_effect(rec_btn)

        _search_rec_vbox.addWidget(adv_search_btn)
        _search_rec_vbox.addWidget(rec_btn)
        toolbar.addWidget(_search_rec_pair)

        # ── Clear pair (stacked vertically, hidden until active) ──────
        _clear_pair = QWidget()
        _clear_vbox = QVBoxLayout(_clear_pair)
        _clear_vbox.setContentsMargins(0, 0, 0, 0)
        _clear_vbox.setSpacing(3)

        self.clear_adv_btn = QPushButton("❌ Clear Advanced")
        self.clear_adv_btn.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border:none; border-radius:4px; padding:2px 8px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#e74c3c; }"
        )
        self.clear_adv_btn.setFixedWidth(130)
        self.clear_adv_btn.clicked.connect(self._clear_advanced_search)
        self.clear_adv_btn.hide()

        self.clear_rec_btn = QPushButton("❌ Clear Rec")
        self.clear_rec_btn.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border:none; border-radius:4px; padding:2px 8px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#e74c3c; }"
        )
        self.clear_rec_btn.setFixedWidth(130)
        self.clear_rec_btn.clicked.connect(self._clear_recommendations)
        self.clear_rec_btn.hide()

        _clear_vbox.addWidget(self.clear_adv_btn)
        _clear_vbox.addWidget(self.clear_rec_btn)
        toolbar.addWidget(_clear_pair)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTRY_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_filter)
        toolbar.addWidget(self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Status"] + ENTRY_STATUS)
        self.status_combo.currentTextChanged.connect(self._on_status_filter)
        toolbar.addWidget(self.status_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Sort by: Title",
                "Sort by: Rating",
                "Sort by: Episodes",
                "Sort by: Current Episode",
                "Sort by: Date",
                "Sort by: Type",
                "Sort by: Status",
                "Sort by: Local Filename",
                "Sort by: Tags",
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

        # ── Pair 1: Add Entry (top) / Import Dir (bottom) ──────────────
        entry_pair = QWidget()
        entry_pair_vbox = QVBoxLayout(entry_pair)
        entry_pair_vbox.setContentsMargins(0, 0, 0, 0)
        entry_pair_vbox.setSpacing(3)

        add_btn = QPushButton("＋ Add Entry")
        add_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self._on_add_new)
        apply_shadow_effect(add_btn)

        import_dir_btn = QPushButton("📂 Import Dir")
        import_dir_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        import_dir_btn.setFixedWidth(120)
        import_dir_btn.setToolTip(
            "Scan a video directory and auto-create listings\n"
            "for series that don't already have an entry."
        )
        import_dir_btn.clicked.connect(self._on_import_from_directory)
        apply_shadow_effect(import_dir_btn)

        entry_pair_vbox.addWidget(add_btn)
        entry_pair_vbox.addWidget(import_dir_btn)
        toolbar.addWidget(entry_pair)

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
        self._detail = _DetailPanel(vault_manager=self.vault_manager)
        self._detail.saved.connect(self._on_entry_saved)
        self._detail.deleted.connect(self._on_entry_deleted)
        detail_scroll.setWidget(self._detail)
        splitter.addWidget(detail_scroll)
        _persist_splitter(splitter, "ContentListingsSubTab_main")

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

        # Debounced resize — avoid rebuilding the gallery on every pixel of a drag.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(120)
        self._resize_timer.timeout.connect(self._rebuild_gallery)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_data(self):
        self._entries = []
        self._all_entities = []

        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                for row in rows:
                    id_, category, title, metadata_json, date_added = row
                    try:
                        entry = json.loads(metadata_json)
                    except Exception:
                        entry = {}
                    entry["id"] = id_
                    entry["date_added"] = date_added
                    if category == "Entity":
                        entry["name"] = title
                        self._all_entities.append(entry)
                    else:
                        entry["type"] = category
                        entry["title"] = title
                        self._entries.append(entry)
            except Exception as e:
                print(f"[ContentListingsSubTab] Failed to load from secure DB: {e}")

    def _save_data(self):
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                for row in rows:
                    id_, category, _, _, _ = row
                    if category != "Entity":
                        base.delete_listing_secure(db_path, password, salt, id_) # pyrefly: ignore [missing-attribute]
                for entry in self._entries:
                    eid = entry.get("id")
                    ecat = entry.get("type", "Anime")
                    etitle = entry.get("title", "")
                    edate = entry.get("date_added", "")
                    meta = dict(entry)
                    base.insert_listing_secure( # pyrefly: ignore [missing-attribute]
                        db_path,
                        password,
                        salt,
                        eid,
                        ecat,
                        etitle,
                        json.dumps(meta, ensure_ascii=False),
                        edate,
                        [],
                    )
            except Exception as e:
                print(f"[ContentListingsSubTab] Failed to save to secure DB: {e}")

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _filtered_entries(self) -> List[Dict[str, Any]]:
        # Recommendation mode: show results sorted by descending relevance score
        if getattr(self, "_recommendation_results", None) is not None:
            assert self._recommendation_results is not None
            rec_map = {uid: score for uid, score in self._recommendation_results}
            result = [e for e in self._entries if e.get("id") in rec_map]
            result.sort(key=lambda e: rec_map.get(e.get("id", ""), 0.0), reverse=True)
            return result

        result = self._entries
        if self._filter_type and self._filter_type not in (
            "All",
            "All Types",
            "None",
            "",
        ):
            result = [e for e in result if e.get("type") == self._filter_type]
        if self._filter_status not in ("All", "All Status"):
            result = [e for e in result if e.get("status") == self._filter_status]

        # Advanced Search Criteria
        if (
            hasattr(self, "_advanced_search_criteria")
            and self._advanced_search_criteria
        ):
            crit = self._advanced_search_criteria
            inc_ent = set(crit.get("include_entities", []))
            exc_ent = set(crit.get("exclude_entities", []))
            inc_tag = {t.lower() for t in crit.get("include_tags", [])}
            exc_tag = {t.lower() for t in crit.get("exclude_tags", [])}
            inc_genre = {g.lower() for g in crit.get("include_genres", [])}
            exc_genre = {g.lower() for g in crit.get("exclude_genres", [])}
            match_mode = crit.get("match_mode", "AND")

            filtered = []
            for e in result:
                # Get fields
                e_ent = set(e.get("associated_entities", []))
                e_tags = {
                    t.strip().lower() for t in e.get("tags", "").split(",") if t.strip()
                }
                e_genres = {
                    g.strip().lower()
                    for g in e.get("genres", "").split(",")
                    if g.strip()
                }

                # Negative filtering (exclusions): if any matches, exclude this entry
                if exc_ent.intersection(e_ent):
                    continue
                if exc_tag.intersection(e_tags):
                    continue
                if exc_genre.intersection(e_genres):
                    continue

                # Positive filtering (inclusions)
                ent_active = len(inc_ent) > 0
                tag_active = len(inc_tag) > 0
                genre_active = len(inc_genre) > 0

                if not ent_active and not tag_active and not genre_active:
                    # No inclusions requested, so it's a match
                    filtered.append(e)
                    continue

                if match_mode == "AND":
                    # Must match all included criteria in active categories
                    ent_ok = not ent_active or inc_ent.issubset(e_ent)
                    tag_ok = not tag_active or inc_tag.issubset(e_tags)
                    genre_ok = not genre_active or inc_genre.issubset(e_genres)

                    if ent_ok and tag_ok and genre_ok:
                        filtered.append(e)
                else:
                    # OR mode: must match at least one of the active inclusions
                    ent_match = ent_active and len(inc_ent.intersection(e_ent)) > 0
                    tag_match = tag_active and len(inc_tag.intersection(e_tags)) > 0
                    genre_match = (
                        genre_active and len(inc_genre.intersection(e_genres)) > 0
                    )

                    if ent_match or tag_match or genre_match:
                        filtered.append(e)

            result = filtered

        if self._search_query:
            q = self._search_query.lower()
            entity_names_map = {
                ent["id"]: ent["name"].lower()
                for ent in self._all_entities
                if "id" in ent and "name" in ent
            }

            filtered = []
            for e in result:
                title = e.get("title", "").lower()
                genres = e.get("genres", "").lower()
                tags = e.get("tags", "").lower()
                creator = e.get("creator", "").lower()

                assoc_match = False
                for ent_id in e.get("associated_entities", []):
                    if ent_id in entity_names_map and q in entity_names_map[ent_id]:
                        assoc_match = True
                        break

                if (
                    q in title
                    or q in genres
                    or q in tags
                    or q in creator
                    or assoc_match
                ):
                    filtered.append(e)
            result = filtered

        # Apply Sort
        sort_field = self.sort_combo.currentText()
        reverse = self.sort_order_combo.currentText() == "Descending"

        if sort_field == "Sort by: Title":
            result = sorted(
                result, key=lambda x: x.get("title", "").lower(), reverse=reverse
            )
        elif sort_field == "Sort by: Type":
            result = sorted(
                result, key=lambda x: x.get("type", "").lower(), reverse=reverse
            )
        elif sort_field == "Sort by: Status":
            result = sorted(
                result, key=lambda x: x.get("status", "").lower(), reverse=reverse
            )
        elif sort_field == "Sort by: Rating":
            result = sorted(
                result,
                key=lambda x: x.get("personal_rating", x.get("rating", 0)),
                reverse=reverse,
            )
        elif sort_field == "Sort by: Episodes":
            result = sorted(result, key=lambda x: x.get("episodes", 0), reverse=reverse)
        elif sort_field == "Sort by: Current Episode":
            result = sorted(
                result, key=lambda x: x.get("current_episode", 0), reverse=reverse
            )
        elif sort_field == "Sort by: Date":
            result = sorted(
                result, key=lambda x: x.get("date_watched", ""), reverse=reverse
            )
        elif sort_field == "Sort by: Local Filename":
            result = sorted(
                result,
                key=lambda x: Path(x.get("local_file", "")).name.lower()
                if x.get("local_file")
                else "",
                reverse=reverse,
            )
        elif sort_field == "Sort by: Tags":
            result = sorted(
                result, key=lambda x: x.get("tags", "").lower(), reverse=reverse
            )

        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        visible = self._filtered_entries()
        if not visible:
            placeholder = QLabel(
                "No entries found.\nClick '＋ Add Entry' to get started."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entry in enumerate(visible):
                card = _ListingCard(entry)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                card.image_remove_requested.connect(
                    self._on_card_image_remove_requested
                )
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entries)
        completed = sum(1 for e in self._entries if e.get("status") == "Completed")
        self.stats_label.setText(
            f"{total} entries total · {completed} completed · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def showEvent(self, event):
        super().showEvent(event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_advanced_search(self):
        dialog = _AdvancedSearchDialog(
            self, entries=self._entries, entities=self._all_entities
        )
        if self._advanced_search_criteria:
            dialog.load_criteria(self._advanced_search_criteria)

        if dialog.exec():
            criteria = dialog.get_criteria()

            # Check if any criteria is set
            has_crit = any(criteria[k] for k in criteria if k != "match_mode")
            if has_crit:
                self._advanced_search_criteria = criteria
                self.clear_adv_btn.show()
            else:
                self._advanced_search_criteria = None
                self.clear_adv_btn.hide()

            self._rebuild_gallery()

    def _clear_advanced_search(self):
        self._advanced_search_criteria = None
        self.clear_adv_btn.hide()
        self._rebuild_gallery()

    @Slot(str)
    def _on_card_clicked(self, entry_id: str):
        self._selected_id = entry_id
        entry = next((e for e in self._entries if e["id"] == entry_id), None)
        if entry:
            self._detail.load_entry(entry, cached_entities=self._all_entities)

    def _on_card_delete_requested(self, entry_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entry from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_entry_deleted(entry_id)

    def _on_card_image_remove_requested(self, entry_id: str):
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        reply = QMessageBox.question(
            self,
            f"Confirm {action_name} Image",
            f"Are you sure you want to move the image for this listing to {action_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            entry = next((e for e in self._entries if e["id"] == entry_id), None)
            if entry:
                img_path = entry.get("image_path", "")
                if img_path:
                    try:
                        p = Path(img_path)
                        if p.exists() and p.is_file():
                            if send_to_trash_enabled:
                                send2trash(str(p))
                            else:
                                p.unlink(missing_ok=True)
                    except Exception as e:
                        print(f"Failed to delete physical image file: {e}")
                entry["image_path"] = ""
                self._save_data()
                self._rebuild_gallery()
                if self._selected_id == entry_id:
                    self._detail.load_entry(entry)

    def _show_gallery_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Content", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entry_saved(self, entry: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entries) if e["id"] == entry["id"]), None
        )
        if idx is not None:
            self._entries[idx] = entry
        else:
            self._entries.insert(0, entry)
        self._save_data()
        if self._sync_entities_for_entry(entry):
            self.entities_changed.emit()
        self._rebuild_gallery()
        self._detail.load_entry(entry, cached_entities=self._all_entities)

    @Slot(str)
    def _on_entry_deleted(self, entry_id: str):
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        self._save_data()
        if self._remove_content_from_entities(entry_id):
            self.entities_changed.emit()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    def _sync_entities_for_entry(self, entry: Dict[str, Any]) -> bool:
        """Keep entities in sync in secure DB: each associated entity gains this entry's ID
        in its associated_content list; removed entities lose it."""
        entry_id = entry.get("id")
        if not entry_id:
            return False
        new_assoc = set(entry.get("associated_entities", []))

        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                entities = []
                for row in rows:
                    id_, category, title, metadata_json, date_added = row
                    if category == "Entity":
                        try:
                            ent = json.loads(metadata_json)
                        except Exception:
                            ent = {}
                        ent["id"] = id_
                        ent["name"] = title
                        ent["date_added"] = date_added
                        entities.append(ent)

                changed = False
                for ent in entities:
                    eid = ent.get("id")
                    if not eid:
                        continue
                    raw = ent.get("associated_content", [])
                    current = set(raw) if isinstance(raw, list) else set()
                    if eid in new_assoc and entry_id not in current:
                        current.add(entry_id)
                        ent["associated_content"] = list(current)
                        changed = True
                    elif eid not in new_assoc and entry_id in current:
                        current.discard(entry_id)
                        ent["associated_content"] = list(current)
                        changed = True

                if changed:
                    for ent in entities:
                        base.delete_listing_secure(db_path, password, salt, ent["id"]) # pyrefly: ignore [missing-attribute]
                        meta = dict(ent)
                        base.insert_listing_secure( # pyrefly: ignore [missing-attribute]
                            db_path,
                            password,
                            salt,
                            ent["id"],
                            "Entity",
                            ent.get("name", ""),
                            json.dumps(meta, ensure_ascii=False),
                            ent.get("date_added", ""),
                            [],
                        )
                return changed
            except Exception as e:
                print(
                    f"[ContentListingsSubTab] Failed to sync entities in secure DB: {e}"
                )
        return False

    def _remove_content_from_entities(self, entry_id: str) -> bool:
        """Remove a deleted content entry's ID from all entities' associated_content in secure DB."""
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            password = self.vault_manager.raw_password
            salt = self.vault_manager.account_name
            try:
                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                entities = []
                for row in rows:
                    id_, category, title, metadata_json, date_added = row
                    if category == "Entity":
                        try:
                            ent = json.loads(metadata_json)
                        except Exception:
                            ent = {}
                        ent["id"] = id_
                        ent["name"] = title
                        ent["date_added"] = date_added
                        entities.append(ent)

                changed = False
                for ent in entities:
                    raw = ent.get("associated_content", [])
                    current = set(raw) if isinstance(raw, list) else set()
                    if entry_id in current:
                        current.discard(entry_id)
                        ent["associated_content"] = list(current)
                        changed = True

                if changed:
                    for ent in entities:
                        base.delete_listing_secure(db_path, password, salt, ent["id"]) # pyrefly: ignore [missing-attribute]
                        meta = dict(ent)
                        base.insert_listing_secure( # pyrefly: ignore [missing-attribute]
                            db_path,
                            password,
                            salt,
                            ent["id"],
                            "Entity",
                            ent.get("name", ""),
                            json.dumps(meta, ensure_ascii=False),
                            ent.get("date_added", ""),
                            [],
                        )
                return changed
            except Exception as e:
                print(
                    f"[ContentListingsSubTab] Failed to clean up entities in secure DB: {e}"
                )
        return False

    def _on_external_reload(self) -> None:
        """Called when another subtab modifies listings.json; refreshes in-memory data."""
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
    def _on_status_filter(self, text: str):
        self._filter_status = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_sort_changed(self, text: str):
        self._rebuild_gallery()

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    def _on_recommend_content(self) -> None:
        if not self.vault_manager or not self.vault_manager.raw_password:
            QMessageBox.information(
                self,
                "Secure Access Required",
                "You must be logged in to get personalized recommendations.",
            )
            return

        dlg = _RecommendationDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._run_recommendation(dlg.get_inputs())

    def _run_recommendation(self, inputs: dict) -> None:
        if self._active_rec_worker and self._active_rec_worker.isRunning():
            self._active_rec_worker.terminate()

        worker = RecommendationWorker(
            entries=self._entries,
            all_entities=self._all_entities,
            inputs=inputs,
            top_k=50,
            parent=self,
        )
        worker.finished.connect(self._on_recommendation_results)
        worker.error.connect(
            lambda e: QMessageBox.warning(self, "Recommendation Error", e)
        )
        worker.status.connect(lambda msg: self.stats_label.setText(f"🌟 {msg}"))
        self._active_rec_worker = worker
        self.stats_label.setText("🌟 Running recommendations…")
        worker.start()

    @Slot(list)
    def _on_recommendation_results(self, results: list) -> None:
        self._recommendation_results = results
        self.clear_rec_btn.show()
        self._rebuild_gallery()

    def _clear_recommendations(self) -> None:
        self._recommendation_results = None
        self.clear_rec_btn.hide()
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
        enc_file_path = str(secrets_dir / "listings.json.enc")

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                "No encrypted listings backup file found to synchronize from. Use 'Update Backup' first to generate it.",
            )
            return

        db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")

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
            "Content",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "local_entries": self._entries,
                "db_path": db_path,
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
            self._entries = merged_entries
            self._rebuild_gallery()

            img_info = (
                f"\nAlso restored {synced_imgs} missing image(s) from backup."
                if synced_imgs
                else ""
            )
            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized listings!\nMerged local and backup entries to a total of {len(merged_entries)} entries.{img_info}",
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
        enc_file_path = str(secrets_dir / "listings.json.enc")

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
            "Content",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "entries": self._entries,
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
                f"Successfully generated encrypted backup listings file with {len(self._entries)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred while generating backup:\n{message}",
            )

    # ------------------------------------------------------------------
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
            created += 1

        if created:
            self._save_data()
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
