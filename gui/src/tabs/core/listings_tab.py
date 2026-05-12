import json
import uuid
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QFrame,
    QSizePolicy,
    QGroupBox,
    QFormLayout,
    QSplitter,
    QDialog,
    QDateEdit,
    QScrollArea,
)

from backend.src.utils.definitions import IMAGE_TOOLKIT_DIR
from ...styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
LISTINGS_FILE = IMAGE_TOOLKIT_DIR / "listings.json"

ENTRY_TYPES = ["Anime", "Movie", "Show", "Book", "Manga", "Game", "Other"]
ENTRY_STATUS = [
    "Completed",
    "Watching / Reading",
    "On Hold",
    "Dropped",
    "Plan to Watch",
]

TYPE_COLORS = {
    "Anime": "#e91e63",
    "Movie": "#2196f3",
    "Show": "#4caf50",
    "Book": "#ff9800",
    "Manga": "#9c27b0",
    "Game": "#00bcd4",
    "Other": "#607d8b",
}
STATUS_COLORS = {
    "Completed": "#2ecc71",
    "Watching / Reading": "#3498db",
    "On Hold": "#f39c12",
    "Dropped": "#e74c3c",
    "Plan to Watch": "#95a5a6",
}

CARD_SIZE = 180
THUMB_SIZE = 130
PLACEHOLDER = "📽"  # shown when no image is set


# -------------------------------------------------------------------
# Helper – coloured badge label
# -------------------------------------------------------------------
def _badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background:{color}; color:white; font-size:9px; font-weight:bold;"
        f"border-radius:4px; padding:1px 5px;"
    )
    return lbl


# -------------------------------------------------------------------
# Episode Dialog
# -------------------------------------------------------------------
class EpisodeDialog(QDialog):
    def __init__(self, episode_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Episode / Chapter Details")
        self.setMinimumWidth(400)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.data = episode_data or {}
        self.image_path = self.data.get("image_path", "")

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.f_number = QSpinBox()
        self.f_number.setRange(1, 999999)
        self.f_number.setValue(self.data.get("number", 1))

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("Episode Title (optional)")
        self.f_title.setText(self.data.get("title", ""))

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        # Handle date parsing/setting
        d_str = self.data.get("date_watched")
        if d_str:
            self.f_date.setDate(date.fromisoformat(d_str))
        else:
            self.f_date.setDate(date.today())

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_rating.setValue(self.data.get("rating", 0))

        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Episode notes / review…")
        self.f_review.setPlainText(self.data.get("review", ""))
        self.f_review.setFixedHeight(80)

        form.addRow("Number", self.f_number)
        form.addRow("Title", self.f_title)
        form.addRow("Date", self.f_date)
        form.addRow("Rating", self.f_rating)
        form.addRow("Review", self.f_review)
        layout.addLayout(form)

        # Image picker
        img_layout = QHBoxLayout()
        self.img_preview = QLabel()
        self.img_preview.setFixedSize(120, 120)
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setStyleSheet("border:1px dashed #4f545c; border-radius:4px;")
        self._update_preview()
        img_layout.addWidget(self.img_preview)

        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse)
        img_layout.addWidget(browse_btn, alignment=Qt.AlignTop)
        layout.addLayout(img_layout)

        # Buttons
        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Episode Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self.image_path = path
            self._update_preview()

    def _update_preview(self):
        if self.image_path and Path(self.image_path).exists():
            px = QPixmap(self.image_path).scaled(
                120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
        else:
            self.img_preview.setText("No Image")

    def get_data(self) -> Dict[str, Any]:
        # QDate.toPython() returns datetime.date
        date_obj = self.f_date.date().toPython()
        return {
            "id": self.data.get("id") or str(uuid.uuid4()),
            "number": self.f_number.value(),
            "title": self.f_title.text().strip(),
            "date_watched": date_obj.isoformat(),
            "rating": self.f_rating.value(),
            "review": self.f_review.toPlainText().strip(),
            "image_path": self.image_path,
        }


# -------------------------------------------------------------------
# Card widget
# -------------------------------------------------------------------
class _ListingCard(QWidget):
    clicked = Signal(str)  # entry id

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._id = entry["id"]
        self.setFixedSize(CARD_SIZE + 10, CARD_SIZE + 50)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("listing_card")
        self.setStyleSheet(
            "QWidget#listing_card{background:#2c2f33;border:2px solid #4f545c;"
            "border-radius:8px;}"
            "QWidget#listing_card:hover{border:2px solid #00bcd4;}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("border:none;")
        self._apply_thumbnail(entry.get("image_path", ""))
        layout.addWidget(self.thumb_label, alignment=Qt.AlignHCenter)

        # Title
        title_lbl = QLabel(entry.get("title", "Untitled"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setWordWrap(False)
        title_lbl.setStyleSheet(
            "color:#ffffff;font-weight:bold;font-size:11px;border:none;"
        )
        title_lbl.setFixedWidth(CARD_SIZE - 4)
        fm = title_lbl.fontMetrics()
        title_lbl.setText(
            fm.elidedText(entry.get("title", "Untitled"), Qt.ElideRight, CARD_SIZE - 10)
        )
        title_lbl.setToolTip(entry.get("title", ""))
        layout.addWidget(title_lbl, alignment=Qt.AlignHCenter)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        t = entry.get("type", "Other")
        s = entry.get("status", "Plan to Watch")
        badge_row.addWidget(_badge(t, TYPE_COLORS.get(t, "#607d8b")))
        badge_row.addWidget(_badge(s[:9], STATUS_COLORS.get(s, "#95a5a6")))
        layout.addLayout(badge_row)

        # Progress info
        episodes = entry.get("episode_list", [])
        total_eps = entry.get("episodes", 0)
        if episodes or total_eps:
            latest = max(e.get("number", 0) for e in episodes) if episodes else 0
            prog_text = f"Prog: {latest}"
            if total_eps:
                prog_text += f" / {total_eps}"
            prog_lbl = QLabel(prog_text)
            prog_lbl.setAlignment(Qt.AlignCenter)
            prog_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
            layout.addWidget(prog_lbl)

        # Rating stars
        rating = entry.get("rating", 0)
        if rating:
            stars = "★" * rating + "☆" * (10 - rating)
            r_lbl = QLabel(stars[:10])
            r_lbl.setAlignment(Qt.AlignCenter)
            r_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(r_lbl, alignment=Qt.AlignHCenter)

    def _apply_thumbnail(self, path: str):
        if path and Path(path).exists():
            px = QPixmap(path).scaled(
                THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.thumb_label.setPixmap(px)
        else:
            self.thumb_label.setText(PLACEHOLDER)
            self.thumb_label.setStyleSheet(
                "font-size:48px;color:#4f545c;background:#23272a;border-radius:6px;border:none;"
            )

    def mousePressEvent(self, _ev):
        self.clicked.emit(self._id)


# -------------------------------------------------------------------
# Detail / edit panel
# -------------------------------------------------------------------
class _DetailPanel(QWidget):
    saved = Signal(dict)
    deleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry_id: Optional[str] = None
        self._image_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image picker
        img_row = QHBoxLayout()
        self.img_preview = QLabel()
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        img_row.addWidget(self.img_preview)
        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse_image)
        browse_btn.setFixedWidth(130)
        img_row.addWidget(browse_btn, alignment=Qt.AlignTop)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("e.g. Cowboy Bebop")
        self.f_type = QComboBox()
        self.f_type.addItems(ENTRY_TYPES)
        self.f_status = QComboBox()
        self.f_status.addItems(ENTRY_STATUS)
        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(0)
        self.f_year.setSpecialValueText("Unknown")
        self.f_episodes = QSpinBox()
        self.f_episodes.setRange(0, 99999)
        self.f_episodes.setSpecialValueText("—")
        self.f_genres = QLineEdit()
        self.f_genres.setPlaceholderText("e.g. Action, Drama")
        self.f_creator = QLineEdit()
        self.f_creator.setPlaceholderText("Studio / Author / Publisher")
        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Optional review or notes…")
        self.f_review.setFixedHeight(100)

        form.addRow("Title *", self.f_title)
        form.addRow("Type", self.f_type)
        form.addRow("Status", self.f_status)
        form.addRow("Rating (0-10)", self.f_rating)
        form.addRow("Year", self.f_year)
        form.addRow("Episodes / Pages", self.f_episodes)
        form.addRow("Genres", self.f_genres)
        form.addRow("Creator", self.f_creator)
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

        # ----------------------------

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

    def load_entry(self, entry: Dict[str, Any]):
        self._entry_id = entry.get("id")
        self._image_path = entry.get("image_path", "")
        self.f_title.setText(entry.get("title", ""))
        self.f_type.setCurrentText(entry.get("type", "Anime"))
        self.f_status.setCurrentText(entry.get("status", "Plan to Watch"))
        self.f_rating.setValue(entry.get("rating", 0))
        self.f_year.setValue(entry.get("year", 0))
        self.f_episodes.setValue(entry.get("episodes", 0))
        self.f_genres.setText(entry.get("genres", ""))
        self.f_creator.setText(entry.get("creator", ""))
        self.f_review.setPlainText(entry.get("review", ""))
        self._episode_data = entry.get("episode_list", [])
        self._refresh_image()
        self._refresh_episode_list()
        self.del_btn.setVisible(True)
        self.episode_group.setVisible(True)

    def clear_for_new(self):
        self._entry_id = None
        self._image_path = ""
        self._episode_data = []
        self.f_title.clear()
        self.f_type.setCurrentIndex(0)
        self.f_status.setCurrentIndex(0)
        self.f_rating.setValue(0)
        self.f_year.setValue(0)
        self.f_episodes.setValue(0)
        self.f_genres.clear()
        self.f_creator.clear()
        self.f_review.clear()
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        self._refresh_episode_list()
        self.del_btn.setVisible(False)
        self.episode_group.setVisible(False)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if path:
            self._image_path = path
            self._refresh_image()

    def _refresh_image(self):
        if self._image_path and Path(self._image_path).exists():
            px = QPixmap(self._image_path).scaled(
                160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
        else:
            self.img_preview.clear()
            self.img_preview.setText("No Image")
            self.img_preview.setStyleSheet(
                "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
            )

    def _refresh_episode_list(self):
        # Clear
        while self.ep_list_layout.count():
            item = self.ep_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Sort episodes by number
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

            # Thumbnail
            t_lbl = QLabel()
            t_lbl.setFixedSize(50, 40)
            t_lbl.setAlignment(Qt.AlignCenter)
            t_lbl.setStyleSheet("background:#1a1c1e; border-radius:3px;")
            if img_path and Path(img_path).exists():
                px = QPixmap(img_path).scaled(
                    50, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                t_lbl.setPixmap(px)
            else:
                t_lbl.setText("No Img")
                t_lbl.setStyleSheet(
                    "background:#1a1c1e; border-radius:3px; color:#555; font-size:8px;"
                )
            rl.addWidget(t_lbl)
            info = QLabel(f"<b>#{num}</b> {title}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet("color:#f1c40f; font-size:10px;")
                rl.addWidget(r_lbl)

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
        dlg = EpisodeDialog(parent=self)
        if dlg.exec():
            new_ep = dlg.get_data()
            self._episode_data.append(new_ep)
            self._refresh_episode_list()

    def _edit_episode(self, ep_data: Dict[str, Any]):
        dlg = EpisodeDialog(ep_data, parent=self)
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
            "rating": self.f_rating.value(),
            "year": self.f_year.value(),
            "episodes": self.f_episodes.value(),
            "genres": self.f_genres.text().strip(),
            "creator": self.f_creator.text().strip(),
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
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.deleted.emit(self._entry_id)


# -------------------------------------------------------------------
# Main tab
# -------------------------------------------------------------------
class ListingsTab(QWidget):
    """Media tracking tab: anime, movies, shows, books, etc."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_status = "All"
        self._search_query = ""

        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("📋 My Listings")
        title_lbl.setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search titles…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTRY_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_filter)
        toolbar.addWidget(self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Status"] + ENTRY_STATUS)
        self.status_combo.currentTextChanged.connect(self._on_status_filter)
        toolbar.addWidget(self.status_combo)

        add_btn = QPushButton("＋ Add Entry")
        add_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self._on_add_new)
        apply_shadow_effect(add_btn)
        toolbar.addWidget(add_btn)

        root.addLayout(toolbar)

        # ---- Stats bar ----
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#888;font-size:11px;")
        root.addWidget(self.stats_label)

        # ---- Splitter: gallery | detail ----
        splitter = QSplitter(Qt.Horizontal)

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
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
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
        self._detail = _DetailPanel()
        self._detail.saved.connect(self._on_entry_saved)
        self._detail.deleted.connect(self._on_entry_deleted)
        detail_scroll.setWidget(self._detail)
        splitter.addWidget(detail_scroll)

        splitter.setSizes([680, 340])
        splitter.setHandleWidth(6)
        root.addWidget(splitter, 1)

        # ---- Load data ----
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_data(self):
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            if LISTINGS_FILE.exists():
                with open(LISTINGS_FILE, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
        except Exception as e:
            print(f"[ListingsTab] Failed to load listings: {e}")
            self._entries = []

    def _save_data(self):
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            with open(LISTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ListingsTab] Failed to save listings: {e}")

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _filtered_entries(self) -> List[Dict[str, Any]]:
        result = self._entries
        if self._filter_type not in ("All", "All Types"):
            result = [e for e in result if e.get("type") == self._filter_type]
        if self._filter_status not in ("All", "All Status"):
            result = [e for e in result if e.get("status") == self._filter_status]
        if self._search_query:
            q = self._search_query.lower()
            result = [
                e
                for e in result
                if q in e.get("title", "").lower()
                or q in e.get("genres", "").lower()
                or q in e.get("creator", "").lower()
            ]
        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible = self._filtered_entries()

        if not visible:
            placeholder = QLabel(
                "No entries found.\nClick '＋ Add Entry' to get started."
            )
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entry in enumerate(visible):
                card = _ListingCard(entry)
                card.clicked.connect(self._on_card_clicked)
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entries)
        completed = sum(1 for e in self._entries if e.get("status") == "Completed")
        self.stats_label.setText(
            f"{total} entries total · {completed} completed · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_gallery()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    @Slot(str)
    def _on_card_clicked(self, entry_id: str):
        self._selected_id = entry_id
        entry = next((e for e in self._entries if e["id"] == entry_id), None)
        if entry:
            self._detail.load_entry(entry)

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
        self._rebuild_gallery()
        self._detail.load_entry(entry)

    @Slot(str)
    def _on_entry_deleted(self, entry_id: str):
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        self._save_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

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
