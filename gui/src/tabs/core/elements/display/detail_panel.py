import json
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import base
from backend.src.constants import IMAGE_TOOLKIT_DIR
from gui.src.components.dialogs.frame_selection_dialog import FrameSelectionDialog
from gui.src.constants.listings import (
    ENTRY_STATUS,
    ENTRY_TYPES,
    LISTING_IMAGES_DIR,
)
from gui.src.helpers.image import apply_thumbnail_to_label
from gui.src.helpers.image.card_thumb_worker import invalidate_thumbnail_cache
from gui.src.helpers.web.mal_sync_worker import MalSyncWorker
from gui.src.styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from gui.src.tabs.core.elements.common.listings_common import (
    fetch_entity_name_map,
    normalize_id_list,
    open_file_location,
    open_web_link,
)
from gui.src.tabs.core.elements.dialog import _AssociatedEntitiesDialog
from gui.src.tabs.core.elements.dialog.episode_dialog import _EpisodeDialog
from gui.src.tabs.core.elements.display.common.base_detail_panel import BaseDetailPanel
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class _DetailPanel(BaseDetailPanel):
    saved = Signal(dict)
    deleted = Signal(str)

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entry_id: Optional[str] = None
        self._episode_data: List[Dict[str, Any]] = []
        self._mal_worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image preview setup from BaseDetailPanel
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )

        img_row = QHBoxLayout()
        img_row.addWidget(self.img_preview)

        img_btns_layout = QVBoxLayout()
        img_btns_layout.setSpacing(6)
        img_btns_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse_image)
        browse_btn.setFixedWidth(140)
        img_btns_layout.addWidget(browse_btn)

        self.btn_gen_thumb = QPushButton("⚡ Gen Thumbnail")
        self.btn_gen_thumb.setToolTip(
            "Extract thumbnail/cover from the associated Local File"
        )
        self.btn_gen_thumb.clicked.connect(self._generate_thumbnail)
        self.btn_gen_thumb.setFixedWidth(140)
        img_btns_layout.addWidget(self.btn_gen_thumb)

        self.btn_mal = QPushButton("Auto-Fill from MAL")
        self.btn_mal.setToolTip(
            "Fetch metadata from MyAnimeList via Jikan API (Anime only)"
        )
        self.btn_mal.setFixedWidth(140)
        self.btn_mal.setStyleSheet(
            "QPushButton { background-color:#1565c0; color:white; font-weight:bold;"
            " padding:6px 8px; border-radius:6px; border:none; }"
            "QPushButton:hover { background-color:#1976d2; }"
            "QPushButton:pressed { background-color:#0d47a1; }"
            "QPushButton:disabled { background-color:#37474f; color:#78909c; }"
        )
        self.btn_mal.clicked.connect(self._on_fetch_mal_clicked)
        img_btns_layout.addWidget(self.btn_mal)

        img_row.addLayout(img_btns_layout)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("e.g. Cowboy Bebop")
        self.f_type = QComboBox()
        self.f_type.addItems(ENTRY_TYPES)
        self.btn_mal.setEnabled(self.f_type.currentText() == "Anime")
        self.f_type.currentTextChanged.connect(
            lambda text: self.btn_mal.setEnabled(text == "Anime")
        )
        self.f_status = QComboBox()
        self.f_status.addItems(ENTRY_STATUS)
        self.f_personal_rating = QSpinBox()
        self.f_personal_rating.setRange(0, 10)
        self.f_personal_rating.setSpecialValueText("No rating")
        self.f_community_rating = QDoubleSpinBox()
        self.f_community_rating.setRange(0.0, 10.0)
        self.f_community_rating.setSingleStep(0.01)
        self.f_community_rating.setDecimals(2)
        self.f_community_rating.setSpecialValueText("No rating")
        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(0)
        self.f_year.setSpecialValueText("Unknown")
        self.f_episodes = QSpinBox()
        self.f_episodes.setRange(1, 99999)
        self.f_current_episode = QSpinBox()
        self.f_current_episode.setRange(0, 99999)
        self.f_episodes.valueChanged.connect(
            lambda val: self.f_current_episode.setRange(0, max(0, val))
        )
        self.f_genres = QLineEdit()
        self.f_genres.setPlaceholderText("e.g. Action, Drama")

        self.f_tags = QLineEdit()
        self.f_tags.setPlaceholderText("e.g. Space Cowboy, Sci-Fi")

        # Associated Entities selection row
        self.assoc_entities_ids = []
        self.f_assoc_entities_display = QLabel("None selected")
        self.f_assoc_entities_display.setWordWrap(True)
        self.f_assoc_entities_display.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.f_assoc_entities_display.setStyleSheet(
            "background:#23272a; border:1px solid #4f545c; border-radius:4px;"
            "padding:4px 6px; color:white;"
        )

        self.btn_select_entities = QPushButton("🔗 Select Entities")
        self.btn_select_entities.clicked.connect(self._select_associated_entities)

        assoc_row = QHBoxLayout()
        assoc_row.addWidget(self.f_assoc_entities_display, 1)
        assoc_row.addWidget(self.btn_select_entities)

        # Local File and Web Link rows
        self.f_local_file = QLineEdit()
        self.f_local_file.setPlaceholderText("Select/paste local file path…")
        self.btn_browse_local_file = QPushButton("📁 Browse")
        self.btn_browse_local_file.clicked.connect(self._browse_local_file)
        self.btn_open_local_file = QPushButton("🚀 Open Location")
        self.btn_open_local_file.clicked.connect(self._open_local_file)

        local_file_row = QHBoxLayout()
        local_file_row.addWidget(self.f_local_file, 1)
        local_file_row.addWidget(self.btn_browse_local_file)
        local_file_row.addWidget(self.btn_open_local_file)

        self.f_web_link = QLineEdit()
        self.f_web_link.setPlaceholderText("Enter web URL (e.g. mal.net/anime/1)…")
        self.btn_open_web_link = QPushButton("🌐 Open Link")
        self.btn_open_web_link.clicked.connect(self._open_web_link)

        web_link_row = QHBoxLayout()
        web_link_row.addWidget(self.f_web_link, 1)
        web_link_row.addWidget(self.btn_open_web_link)

        # Summary
        self.f_summary = QTextEdit()
        self.f_summary.setPlaceholderText(
            "Synopsis / Summary (auto-filled from web, or write your own)…"
        )
        self.f_summary.setFixedHeight(75)

        # Personal review / notes
        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Personal review or notes…")
        self.f_review.setFixedHeight(80)

        form.addRow("Title *", self.f_title)
        form.addRow("Type", self.f_type)
        form.addRow("Status", self.f_status)
        form.addRow("My Rating (0-10)", self.f_personal_rating)
        form.addRow("Community Rating", self.f_community_rating)
        form.addRow("Year", self.f_year)
        form.addRow("Episodes / Pages", self.f_episodes)
        form.addRow("Current Episode / Page", self.f_current_episode)
        form.addRow("Genres", self.f_genres)
        form.addRow("Tags", self.f_tags)
        form.addRow("Associated Entities", assoc_row)
        form.addRow("Local File", local_file_row)
        form.addRow("Web Link", web_link_row)
        form.addRow("Summary", self.f_summary)
        form.addRow("Review / Notes", self.f_review)
        layout.addLayout(form)

        # --- Episode List Section ---
        self.episode_group = QGroupBox("Episodes / Chapters / Parts")
        self.episode_group.setStyleSheet("QGroupBox{font-weight:bold; color:#00bcd4;}")
        eg_layout = QVBoxLayout(self.episode_group)

        self.ep_list_layout = QVBoxLayout()
        self.ep_list_layout.setSpacing(4)
        eg_layout.addLayout(self.ep_list_layout)

        add_ep_btn = QPushButton("＋ Add Episode Entry")
        add_ep_btn.clicked.connect(self._add_episode)
        eg_layout.addWidget(add_ep_btn)
        layout.addWidget(self.episode_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self.save_btn.clicked.connect(self._on_save)
        apply_shadow_effect(self.save_btn)

        self.del_btn = QPushButton("🗑 Delete")
        self.del_btn.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "padding:10px;border-radius:8px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        self.del_btn.clicked.connect(self._on_delete)
        apply_shadow_effect(self.del_btn)

        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def _browse_image(self):
        self._image_path = self._browse_image_helper(self._entry_id) # pyrefly: ignore [bad-argument-type]

    def _select_associated_entities(self):
        all_entities = []
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
                    if category == "Entity":
                        try:
                            entity = json.loads(metadata_json)
                        except Exception:
                            entity = {}
                        entity["id"] = id_
                        entity["name"] = title
                        entity["date_added"] = date_added
                        all_entities.append(entity)
            except Exception as e:
                print(f"Failed to load entities from DB for association: {e}")

        if not all_entities:
            QMessageBox.information(
                self,
                "No Entities Available",
                "There are no entities available in Entity Listings. Please add people or organizations first.",
            )
            return

        dlg = _AssociatedEntitiesDialog(
            all_entities, self.assoc_entities_ids, parent=self
        )
        if dlg.exec():
            self.assoc_entities_ids = dlg.get_selected_ids()
            self._update_assoc_entities_display()

    def _update_assoc_entities_display(self, _all_entities: Optional[List[Dict[str, Any]]] = None):
        """Resolve associated entity IDs to names using a fresh DB lookup."""
        del _all_entities  # kept for callers; display always reads live data
        if not self.assoc_entities_ids:
            self.f_assoc_entities_display.setText("None selected")
            self.f_assoc_entities_display.setToolTip("")
            return

        name_map: Dict[str, str] = {}
        if (
            self.vault_manager
            and hasattr(self.vault_manager, "raw_password")
            and self.vault_manager.raw_password
        ):
            db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
            name_map = fetch_entity_name_map(
                db_path,
                self.vault_manager.raw_password,
                self.vault_manager.account_name,
            )

        names = [name_map.get(ent_id, ent_id) for ent_id in self.assoc_entities_ids]
        display_text = ", ".join(names)
        self.f_assoc_entities_display.setText(display_text or "None selected")
        self.f_assoc_entities_display.setToolTip(display_text)

    def load_entry(  # noqa: C901
        self,
        entry: Dict[str, Any],
        cached_entities: Optional[List[Dict[str, Any]]] = None,
    ):
        self._entry_id = entry.get("id")
        self._image_path = entry.get("image_path", "")
        self.f_title.setText(entry.get("title", ""))
        self.f_type.setCurrentText(entry.get("type", "Anime"))
        self.f_status.setCurrentText(entry.get("status", "Plan to Watch"))
        self.f_personal_rating.setValue(
            entry.get("personal_rating", entry.get("rating", 0)) # pyrefly: ignore [bad-argument-type]
        )
        self.f_community_rating.setValue(float(entry.get("community_rating", 0.0)))
        self.f_year.setValue(entry.get("year", 0))
        self.f_episodes.setValue(entry.get("episodes", 1))
        self.f_current_episode.setValue(entry.get("current_episode", 0))
        self.f_genres.setText(entry.get("genres", ""))
        self.f_tags.setText(entry.get("tags", ""))
        self.assoc_entities_ids = normalize_id_list(
            entry.get("associated_entities", [])
        )

        self.f_local_file.setText(entry.get("local_file", ""))
        self.f_web_link.setText(entry.get("web_link", ""))

        self._update_assoc_entities_display()

        self.f_summary.setPlainText(entry.get("summary", ""))
        self.f_review.setPlainText(entry.get("review", ""))
        self._episode_data = entry.get("episode_list", [])
        self.del_btn.setVisible(True)
        self.episode_group.setVisible(True)

        QTimer.singleShot(0, self._refresh_image)
        QTimer.singleShot(0, self._refresh_episode_list)

    def clear_for_new(self):
        self._entry_id = None
        self._image_path = ""
        self._episode_data = []
        self.f_title.clear()
        self.f_type.setCurrentIndex(0)
        self.f_status.setCurrentIndex(0)
        self.f_personal_rating.setValue(0)
        self.f_community_rating.setValue(0.0)
        self.f_year.setValue(0)
        self.f_episodes.setValue(1)
        self.f_current_episode.setValue(0)
        self.f_genres.clear()
        self.f_tags.clear()
        self.assoc_entities_ids = []
        self.f_assoc_entities_display.setText("None selected")
        self.f_assoc_entities_display.setToolTip("")
        self.f_local_file.clear()
        self.f_web_link.clear()
        self.f_summary.clear()
        self.f_review.clear()
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        self._refresh_episode_list()
        self.del_btn.setVisible(False)
        self.episode_group.setVisible(False)

    def _browse_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local File",
            "",
            "All Files (*.*)",
        )
        if path:
            self.f_local_file.setText(path)

    def _open_local_file(self):
        path = self.f_local_file.text().strip()
        if not path:
            QMessageBox.warning(
                self, "No File", "Please select or enter a local file path first."
            )
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file at '{path}' does not exist."
            )
            return
        open_file_location(path)

    def _open_web_link(self):
        url = self.f_web_link.text().strip()
        if not url:
            QMessageBox.warning(self, "No Link", "Please enter a web link first.")
            return
        open_web_link(url)

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
                QMessageBox.information(
                    self, "Success", "Image set as thumbnail successfully!"
                )
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
                    QMessageBox.critical(
                        self, "Error", "Failed to save selected thumbnail image."
                    )
            return

        QMessageBox.warning(
            self,
            "Unsupported Format",
            "This file format is not supported for generating a thumbnail.",
        )

    @Slot()
    def _on_fetch_mal_clicked(self):
        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(
                self, "No Title", "Please enter a title before fetching from MAL."
            )
            return
        self.btn_mal.setText("Fetching...")
        self.btn_mal.setEnabled(False)
        self._mal_worker = MalSyncWorker(title)
        self._mal_worker.finished.connect(self._on_mal_finished)
        self._mal_worker.error.connect(self._on_mal_error)
        self._mal_worker.start()

    @Slot(dict)
    def _on_mal_finished(self, data: dict):
        synopsis = data.get("synopsis", "")
        if synopsis:
            self.f_summary.setPlainText(synopsis)
        episodes = data.get("episodes")
        if episodes:
            self.f_episodes.setValue(int(episodes))
        score = data.get("score")
        if score:
            self.f_community_rating.setValue(float(score))
        genres = data.get("genres", "")
        if genres:
            self.f_genres.setText(genres)
        year = data.get("year")
        if year:
            self.f_year.setValue(int(year))
        mapped_status = data.get("status", "")
        if mapped_status and mapped_status in ENTRY_STATUS:
            self.f_status.setCurrentText(mapped_status)
        mal_url = data.get("mal_url", "")
        if mal_url and not self.f_web_link.text().strip():
            self.f_web_link.setText(mal_url)

        self._auto_associate_entities(data)

        self.btn_mal.setText("Auto-Fill from MAL")
        self.btn_mal.setEnabled(True)

    def _auto_associate_entities(self, data: dict) -> None:  # noqa: C901
        try:
            all_entities: list = []
            if (
                self.vault_manager
                and hasattr(self.vault_manager, "raw_password")
                and self.vault_manager.raw_password
            ):
                db_path = str(IMAGE_TOOLKIT_DIR / "listings_secure.db")
                password = self.vault_manager.raw_password
                salt = self.vault_manager.account_name

                rows = base.fetch_all_listings_secure(db_path, password, salt) # pyrefly: ignore [missing-attribute]
                for row in rows:
                    id_, category, title, metadata_json, date_added = row
                    if category == "Entity":
                        try:
                            entity = json.loads(metadata_json)
                        except Exception:
                            entity = {}
                        entity["id"] = id_
                        entity["name"] = title
                        entity["date_added"] = date_added
                        all_entities.append(entity)
        except Exception:
            return

        if not all_entities:
            return

        def _key(s: str) -> str:
            return s.strip().lower()

        name_index: dict[str, str] = {_key(e["name"]): e["id"] for e in all_entities}
        current_ids: set[str] = set(self.assoc_entities_ids)
        added_count = 0

        def _try_add(name: str) -> None:
            nonlocal added_count
            if not name:
                return
            eid = name_index.get(_key(name))
            if eid is None:
                words = name.split()
                if len(words) >= 2:
                    eid = name_index.get(_key(" ".join(reversed(words))))
            if eid is None and ", " in name:
                last, first = name.split(", ", 1)
                eid = name_index.get(_key(f"{first} {last}"))
            if eid and eid not in current_ids:
                current_ids.add(eid)
                added_count += 1

        for name in data.get("studios", []):
            _try_add(name)
        for name in data.get("producers", []):
            _try_add(name)
        for name in data.get("characters", []):
            _try_add(name)
        for name in data.get("voice_actors", []):
            _try_add(name)
        for entry in data.get("staff", []):
            _try_add(entry.get("name", ""))

        if added_count > 0:
            self.assoc_entities_ids = list(current_ids)
            self._update_assoc_entities_display()

        if not data.get("characters_available", True):
            msg = (
                "Character and voice-actor data was not available from MyAnimeList "
                "(this is common for 18+ / adult content). Studios and staff were "
                "matched where possible. Please use 'Select Entities' to add "
                "characters manually."
            )
            QMessageBox.information(self, "Auto-Fill — Partial Results", msg)

    @Slot(str)
    def _on_mal_error(self, message: str):
        QMessageBox.critical(self, "MAL Fetch Error", message)
        self.btn_mal.setText("Auto-Fill from MAL")
        self.btn_mal.setEnabled(True)

    def _refresh_episode_list(self):
        while self.ep_list_layout.count():
            item = self.ep_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        sorted_eps = sorted(self._episode_data, key=lambda x: x.get("number", 0))

        for ep in sorted_eps:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{background:#23272a; border-radius:4px; padding:2px;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)

            num = ep.get("number", 0)
            title = ep.get("title", "")
            rating = ep.get("rating", 0)
            img_path = ep.get("image_path", "")

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
                placeholder_style=(
                    "background:#1a1c1e; border-radius:3px; color:#555; font-size:8px;"
                ),
            )
            rl.addWidget(t_lbl)
            info = QLabel(f"<b>#{num}</b> {title}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet("color:#f1c40f; font-size:10px;")
                rl.addWidget(r_lbl)

            local_file = ep.get("local_file", "")
            web_link = ep.get("web_link", "")

            if local_file:
                file_btn = QPushButton("📁")
                file_btn.setFixedSize(24, 24)
                file_btn.setToolTip(f"Open: {local_file}")
                file_btn.setStyleSheet(
                    "background-color:#16a085; color:white; font-size:10px; font-weight:bold; border-radius:3px;"
                )
                file_btn.clicked.connect(
                    lambda _, path=local_file: open_file_location(path)
                )
                rl.addWidget(file_btn)

            if web_link:
                link_btn = QPushButton("🌐")
                link_btn.setFixedSize(24, 24)
                link_btn.setToolTip(f"Open Link: {web_link}")
                link_btn.setStyleSheet(
                    "background-color:#2980b9; color:white; font-size:10px; font-weight:bold; border-radius:3px;"
                )
                link_btn.clicked.connect(lambda _, url=web_link: open_web_link(url))
                rl.addWidget(link_btn)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setToolTip("Edit episode")
            edit_btn.clicked.connect(lambda _, e=ep: self._edit_episode(e))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove episode record")
            del_btn.clicked.connect(lambda _, eid=ep["id"]: self._remove_episode(eid))
            rl.addWidget(del_btn)

            self.ep_list_layout.addWidget(row)

    def _add_episode(self):
        dlg = _EpisodeDialog(parent=self)
        if dlg.exec():
            new_ep = dlg.get_data()
            self._episode_data.append(new_ep)
            self._refresh_episode_list()

    def _edit_episode(self, ep_data: Dict[str, Any]):
        dlg = _EpisodeDialog(ep_data, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            for i, e in enumerate(self._episode_data):
                if e["id"] == updated["id"]:
                    self._episode_data[i] = updated
                    break
            self._refresh_episode_list()

    def _remove_episode(self, ep_id: str):
        self._episode_data = [e for e in self._episode_data if e["id"] != ep_id]
        self._refresh_episode_list()

    def _collect(self) -> Optional[Dict[str, Any]]:
        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return None
        return {
            "id": self._entry_id or str(uuid.uuid4()),
            "title": title,
            "type": self.f_type.currentText(),
            "status": self.f_status.currentText(),
            "personal_rating": self.f_personal_rating.value(),
            "community_rating": round(self.f_community_rating.value(), 2),
            "year": self.f_year.value(),
            "episodes": self.f_episodes.value(),
            "current_episode": self.f_current_episode.value(),
            "genres": self.f_genres.text().strip(),
            "tags": self.f_tags.text().strip(),
            "associated_entities": self.assoc_entities_ids,
            "local_file": self.f_local_file.text().strip(),
            "web_link": self.f_web_link.text().strip(),
            "summary": self.f_summary.toPlainText().strip(),
            "review": self.f_review.toPlainText().strip(),
            "image_path": self._image_path,
            "episode_list": self._episode_data,
            "date_added": str(date.today()),
        }

    @Slot()
    def _on_save(self):
        entry = self._collect()
        if entry:
            self.saved.emit(entry)

    @Slot()
    def _on_delete(self):
        if not self._entry_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entry from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.deleted.emit(self._entry_id)
