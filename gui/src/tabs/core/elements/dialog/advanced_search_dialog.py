from pathlib import Path
from PySide6.QtCore import Qt, QSize, QThreadPool
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTabWidget,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)

from gui.src.helpers.image import (
    _CARD_THUMB_CACHE,
    _ThumbWorker,
)



class _AdvancedSearchDialog(QDialog):
    def __init__(self, parent=None, entries=None, entities=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Advanced Search Settings")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(
            "QDialog { background: #23272a; color: white; }"
            "QLabel { color: #00bcd4; font-weight: bold; font-size: 12px; }"
            "QListWidget { background: #2c2f33; border: 1px solid #4f545c; border-radius: 6px; color: white; }"
            "QListWidget::item:hover { background: #00bcd4; color: black; }"
            "QComboBox { background: #2c2f33; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 4px; }"
            "QTabWidget::pane { border: 1px solid #4f545c; background: #23272a; border-radius: 6px; }"
            "QTabBar::tab { background: #2c2f33; color: #888; padding: 8px 16px; border: 1px solid #4f545c; border-top-left-radius: 4px; border-top-right-radius: 4px; }"
            "QTabBar::tab:selected { background: #23272a; color: #00bcd4; border-bottom-color: #23272a; font-weight: bold; }"
        )

        self.entries = entries or []
        self.entities = entities or []

        # Extract unique tags & genres
        all_tags = set()
        all_genres = set()
        for e in self.entries:
            for t in e.get("tags", "").split(","):
                ts = t.strip()
                if ts:
                    all_tags.add(ts)
            for g in e.get("genres", "").split(","):
                gs = g.strip()
                if gs:
                    all_genres.add(gs)

        self.sorted_tags = sorted(list(all_tags), key=lambda x: x.lower())
        self.sorted_genres = sorted(list(all_genres), key=lambda x: x.lower())
        self.sorted_entities = sorted(
            self.entities, key=lambda x: x.get("name", "").lower()
        )

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_title = QLabel("🔍 Advanced Content Search")
        header_title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #00bcd4;"
        )
        header_layout.addWidget(header_title)
        layout.addLayout(header_layout)

        # Match mode combo
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Match Mode (Inclusions):")
        mode_label.setFixedWidth(180)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(
            ["Match ALL positive criteria (AND)", "Match ANY positive criteria (OR)"]
        )
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # Tab widget
        self.tabs = QTabWidget()

        # Tab 1: Entities
        ent_tab = QWidget()
        ent_layout = QHBoxLayout(ent_tab)
        ent_layout.setContentsMargins(8, 8, 8, 8)
        ent_layout.setSpacing(12)

        # Helper to apply icons asynchronously
        def _apply_icon(item, path):
            if not path or not Path(path).exists():
                return
            cached = _CARD_THUMB_CACHE.get(path)
            if cached is not None:
                item.setIcon(QIcon(QPixmap.fromImage(cached)))
            else:

                def _on_ready(p, img):
                    if p == path:
                        item.setIcon(QIcon(QPixmap.fromImage(img)))

                w = _ThumbWorker(path, 40)
                w.signals.ready.connect(_on_ready)
                QThreadPool.globalInstance().start(w)

        # Include Entities
        inc_ent_box = QVBoxLayout()
        inc_ent_box.addWidget(QLabel("👥 Include Entities:"))
        self.inc_ent_list = QListWidget()
        self.inc_ent_list.setIconSize(QSize(40, 40))
        for ent in self.sorted_entities:
            item = QListWidgetItem(ent.get("name", "Unnamed"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, ent.get("id"))
            self.inc_ent_list.addItem(item)
            _apply_icon(item, ent.get("image_path", ""))
        inc_ent_box.addWidget(self.inc_ent_list)
        ent_layout.addLayout(inc_ent_box)

        # Exclude Entities
        exc_ent_box = QVBoxLayout()
        exc_ent_box.addWidget(QLabel("🚫 Exclude Entities:"))
        self.exc_ent_list = QListWidget()
        self.exc_ent_list.setIconSize(QSize(40, 40))
        for ent in self.sorted_entities:
            item = QListWidgetItem(ent.get("name", "Unnamed"))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, ent.get("id"))
            self.exc_ent_list.addItem(item)
            _apply_icon(item, ent.get("image_path", ""))
        exc_ent_box.addWidget(self.exc_ent_list)
        ent_layout.addLayout(exc_ent_box)

        self.tabs.addTab(ent_tab, "👥 Entities")

        # Tab 2: Tags
        tag_tab = QWidget()
        tag_layout = QHBoxLayout(tag_tab)
        tag_layout.setContentsMargins(8, 8, 8, 8)
        tag_layout.setSpacing(12)

        # Include Tags
        inc_tag_box = QVBoxLayout()
        inc_tag_box.addWidget(QLabel("🏷 Include Tags:"))
        self.inc_tag_list = QListWidget()
        for tag in self.sorted_tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.inc_tag_list.addItem(item)
        inc_tag_box.addWidget(self.inc_tag_list)
        tag_layout.addLayout(inc_tag_box)

        # Exclude Tags
        exc_tag_box = QVBoxLayout()
        exc_tag_box.addWidget(QLabel("🚫 Exclude Tags:"))
        self.exc_tag_list = QListWidget()
        for tag in self.sorted_tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.exc_tag_list.addItem(item)
        exc_tag_box.addWidget(self.exc_tag_list)
        tag_layout.addLayout(exc_tag_box)

        self.tabs.addTab(tag_tab, "🏷 Tags")

        # Tab 3: Genres
        genre_tab = QWidget()
        genre_layout = QHBoxLayout(genre_tab)
        genre_layout.setContentsMargins(8, 8, 8, 8)
        genre_layout.setSpacing(12)

        # Include Genres
        inc_genre_box = QVBoxLayout()
        inc_genre_box.addWidget(QLabel("🎭 Include Genres:"))
        self.inc_genre_list = QListWidget()
        for genre in self.sorted_genres:
            item = QListWidgetItem(genre)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.inc_genre_list.addItem(item)
        inc_genre_box.addWidget(self.inc_genre_list)
        genre_layout.addLayout(inc_genre_box)

        # Exclude Genres
        exc_genre_box = QVBoxLayout()
        exc_genre_box.addWidget(QLabel("🚫 Exclude Genres:"))
        self.exc_genre_list = QListWidget()
        for genre in self.sorted_genres:
            item = QListWidgetItem(genre)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.exc_genre_list.addItem(item)
        exc_genre_box.addWidget(self.exc_genre_list)
        genre_layout.addLayout(exc_genre_box)

        self.tabs.addTab(genre_tab, "🎭 Genres")

        layout.addWidget(self.tabs, 1)

        # Actions buttons
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(12)
        btns_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setStyleSheet(
            "QPushButton { background: #2f3136; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #4f545c; }"
        )
        self.cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(self.cancel_btn)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(120)
        self.search_btn.setStyleSheet(
            "QPushButton { background: #00bcd4; color: black; border: none; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #008ba3; color: white; }"
        )
        self.search_btn.clicked.connect(self.accept)
        btns_layout.addWidget(self.search_btn)

        layout.addLayout(btns_layout)

    def load_criteria(self, crit):
        if not crit:
            return

        # Set match mode
        if crit.get("match_mode") == "OR":
            self.mode_combo.setCurrentIndex(1)
        else:
            self.mode_combo.setCurrentIndex(0)

        # Set check states
        inc_ent = set(crit.get("include_entities", []))
        exc_ent = set(crit.get("exclude_entities", []))
        inc_tag = set(crit.get("include_tags", []))
        exc_tag = set(crit.get("exclude_tags", []))
        inc_genre = set(crit.get("include_genres", []))
        exc_genre = set(crit.get("exclude_genres", []))

        # Entities
        for idx in range(self.inc_ent_list.count()):
            item = self.inc_ent_list.item(idx)
            ent_id = item.data(Qt.ItemDataRole.UserRole)
            if ent_id in inc_ent:
                item.setCheckState(Qt.CheckState.Checked)
        for idx in range(self.exc_ent_list.count()):
            item = self.exc_ent_list.item(idx)
            ent_id = item.data(Qt.ItemDataRole.UserRole)
            if ent_id in exc_ent:
                item.setCheckState(Qt.CheckState.Checked)

        # Tags
        for idx in range(self.inc_tag_list.count()):
            item = self.inc_tag_list.item(idx)
            if item.text() in inc_tag:
                item.setCheckState(Qt.CheckState.Checked)
        for idx in range(self.exc_tag_list.count()):
            item = self.exc_tag_list.item(idx)
            if item.text() in exc_tag:
                item.setCheckState(Qt.CheckState.Checked)

        # Genres
        for idx in range(self.inc_genre_list.count()):
            item = self.inc_genre_list.item(idx)
            if item.text() in inc_genre:
                item.setCheckState(Qt.CheckState.Checked)
        for idx in range(self.exc_genre_list.count()):
            item = self.exc_genre_list.item(idx)
            if item.text() in exc_genre:
                item.setCheckState(Qt.CheckState.Checked)

    def get_criteria(self):
        crit = {
            "include_entities": [],
            "exclude_entities": [],
            "include_tags": [],
            "exclude_tags": [],
            "include_genres": [],
            "exclude_genres": [],
            "match_mode": "AND" if self.mode_combo.currentIndex() == 0 else "OR",
        }

        # Entities
        for idx in range(self.inc_ent_list.count()):
            item = self.inc_ent_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                crit["include_entities"].append(item.data(Qt.ItemDataRole.UserRole))
        for idx in range(self.exc_ent_list.count()):
            item = self.exc_ent_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                crit["exclude_entities"].append(item.data(Qt.ItemDataRole.UserRole))

        # Tags
        for idx in range(self.inc_tag_list.count()):
            item = self.inc_tag_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                crit["include_tags"].append(item.text())
        for idx in range(self.exc_tag_list.count()):
            item = self.exc_tag_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                crit["exclude_tags"].append(item.text())

        # Genres
        for idx in range(self.inc_genre_list.count()):
            item = self.inc_genre_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                crit["include_genres"].append(item.text())
        for idx in range(self.exc_genre_list.count()):
            item = self.exc_genre_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                crit["exclude_genres"].append(item.text())

        return crit
