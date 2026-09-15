from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.helpers.image import _CARD_THUMB_CACHE
from gui.src.theming.theme_api import qss


class _AdvancedSearchDialog(QDialog):
    def __init__(self, parent=None, entries=None, entities=None, mode: str = "content"):  # noqa: C901
        """``mode``: 'content' (Series/Content Listings -- ``entities`` are
        the entities appearing IN each entry, via media_entity) or 'entity'
        (Entity Listings -- ``entities`` are PEER entities, via the
        undirected entity_entity association) -- only affects labels/titles,
        the dialog and its criteria dict shape are identical either way."""
        super().__init__(parent)
        self._mode = mode
        title = "🔍 Advanced Content Search" if mode == "content" else "🔍 Advanced Entity Search"
        self.setWindowTitle(f"{title} Settings")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(qss("advanced_search_dialog"))

        self.entries = entries or []
        self.entities = entities or []

        # Genres are just a tag subtype now (backend: 'Genre' is a tag
        # category, not a separate concept -- see tag_bucket_clause /
        # _advanced_media_conditions). Present ONE merged Tags list to the
        # user; per-name category membership is tracked so get_criteria()
        # still buckets each checked name into include_tags/include_genres
        # exactly as the backend query expects -- no backend change needed.
        all_tags = set()
        all_genres = set()
        self._tag_name_categories: dict[str, set[str]] = {}
        for e in self.entries:
            for t in e.get("tags", "").split(","):
                ts = t.strip()
                if ts:
                    all_tags.add(ts)
                    self._tag_name_categories.setdefault(ts, set()).add("tag")
            for g in e.get("genres", "").split(","):
                gs = g.strip()
                if gs:
                    all_genres.add(gs)
                    self._tag_name_categories.setdefault(gs, set()).add("genre")

        self.sorted_tags = sorted(all_tags | all_genres, key=lambda x: x.lower())
        self.sorted_entities = sorted(
            self.entities, key=lambda x: x.get("name", "").lower()
        )

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_title = QLabel(title)
        header_title.setStyleSheet(qss("asp_dialog_title"))
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

        ent_noun = "Entities" if mode == "content" else "Associated Entities"

        # Tab 1: Entities
        ent_tab = QWidget()
        ent_tab_layout = QVBoxLayout(ent_tab)
        ent_tab_layout.setContentsMargins(8, 8, 8, 8)
        ent_tab_layout.setSpacing(8)

        # Entity free-text filter
        self.ent_filter = QLineEdit()
        self.ent_filter.setPlaceholderText(f"Filter {ent_noun.lower()}...")
        self.ent_filter.setClearButtonEnabled(True)
        self.ent_filter.textChanged.connect(self._on_ent_filter_changed)
        ent_tab_layout.addWidget(self.ent_filter)

        self.inc_ent_filter = self.ent_filter
        self.exc_ent_filter = self.ent_filter

        ent_lists_layout = QHBoxLayout()
        ent_lists_layout.setSpacing(12)

        # Include Entities
        inc_ent_box = QVBoxLayout()
        inc_ent_box.addWidget(QLabel(f"👥 Include {ent_noun}:"))
        self.inc_ent_list = QListWidget()
        self.inc_ent_list.setIconSize(QSize(40, 40))
        inc_ent_box.addWidget(self.inc_ent_list)
        ent_lists_layout.addLayout(inc_ent_box)

        # Exclude Entities
        exc_ent_box = QVBoxLayout()
        exc_ent_box.addWidget(QLabel(f"🚫 Exclude {ent_noun}:"))
        self.exc_ent_list = QListWidget()
        self.exc_ent_list.setIconSize(QSize(40, 40))
        exc_ent_box.addWidget(self.exc_ent_list)
        ent_lists_layout.addLayout(exc_ent_box)

        # Populate entities with deferred uncached icon loading
        self._pending_icon_items: list[tuple[QListWidgetItem, str]] = []
        for ent in self.sorted_entities:
            name = ent.get("name", "Unnamed")
            ent_id = ent.get("id")
            path = ent.get("image_path", "")

            inc_item = QListWidgetItem(name)
            inc_item.setFlags(inc_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            inc_item.setCheckState(Qt.CheckState.Unchecked)
            inc_item.setData(Qt.ItemDataRole.UserRole, ent_id)
            self.inc_ent_list.addItem(inc_item)

            exc_item = QListWidgetItem(name)
            exc_item.setFlags(exc_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            exc_item.setCheckState(Qt.CheckState.Unchecked)
            exc_item.setData(Qt.ItemDataRole.UserRole, ent_id)
            self.exc_ent_list.addItem(exc_item)

            if path:
                cached = _CARD_THUMB_CACHE.get(path)
                if cached is not None:
                    icon = QIcon(QPixmap.fromImage(cached))
                    inc_item.setIcon(icon)
                    exc_item.setIcon(icon)
                else:
                    self._pending_icon_items.append((inc_item, path))
                    self._pending_icon_items.append((exc_item, path))

        ent_tab_layout.addLayout(ent_lists_layout)
        self.tabs.addTab(ent_tab, f"👥 {ent_noun}")

        # Tab 2: Tags
        tag_tab = QWidget()
        tag_tab_layout = QVBoxLayout(tag_tab)
        tag_tab_layout.setContentsMargins(8, 8, 8, 8)
        tag_tab_layout.setSpacing(8)

        # Tag free-text filter
        self.tag_filter = QLineEdit()
        self.tag_filter.setPlaceholderText("Filter tags...")
        self.tag_filter.setClearButtonEnabled(True)
        self.tag_filter.textChanged.connect(self._on_tag_filter_changed)
        tag_tab_layout.addWidget(self.tag_filter)

        self.inc_tag_filter = self.tag_filter
        self.exc_tag_filter = self.tag_filter

        tag_lists_layout = QHBoxLayout()
        tag_lists_layout.setSpacing(12)

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
        tag_lists_layout.addLayout(inc_tag_box)

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
        tag_lists_layout.addLayout(exc_tag_box)

        tag_tab_layout.addLayout(tag_lists_layout)
        self.tabs.addTab(tag_tab, "🏷 Tags")

        layout.addWidget(self.tabs, 1)

        # Actions buttons
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(12)
        btns_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setStyleSheet(qss("database_dialog_cancel_btn"))
        self.cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(self.cancel_btn)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(120)
        self.search_btn.setStyleSheet(qss("database_dialog_accent_btn"))
        self.search_btn.clicked.connect(self.accept)
        btns_layout.addWidget(self.search_btn)

        layout.addLayout(btns_layout)

        self._is_closed = False
        if self._pending_icon_items:
            QTimer.singleShot(0, self._process_deferred_icons)

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

        # Tags (merged tag+genre list -- a name checks if it was saved under
        # either bucket, so criteria saved before the Genres tab merge still
        # restore correctly).
        for idx in range(self.inc_tag_list.count()):
            item = self.inc_tag_list.item(idx)
            if item.text() in inc_tag or item.text() in inc_genre:
                item.setCheckState(Qt.CheckState.Checked)
        for idx in range(self.exc_tag_list.count()):
            item = self.exc_tag_list.item(idx)
            if item.text() in exc_tag or item.text() in exc_genre:
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

        # Tags (merged tag+genre list -- bucket each checked name back into
        # include_tags/include_genres per its real category membership, so
        # the backend query in _advanced_media_conditions -- which still
        # distinguishes the 'Tag'/'Genre' tag categories -- needs no change).
        for idx in range(self.inc_tag_list.count()):
            item = self.inc_tag_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                name = item.text()
                cats = self._tag_name_categories.get(name, {"tag"})
                if "tag" in cats:
                    crit["include_tags"].append(name)
                if "genre" in cats:
                    crit["include_genres"].append(name)
        for idx in range(self.exc_tag_list.count()):
            item = self.exc_tag_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                name = item.text()
                cats = self._tag_name_categories.get(name, {"tag"})
                if "tag" in cats:
                    crit["exclude_tags"].append(name)
                if "genre" in cats:
                    crit["exclude_genres"].append(name)

        return crit

    @staticmethod
    def _filter_list(list_widget: QListWidget, filter_text: str) -> None:
        query = filter_text.strip().lower()
        for idx in range(list_widget.count()):
            item = list_widget.item(idx)
            item.setHidden(bool(query and query not in item.text().lower()))

    def _on_ent_filter_changed(self, text: str) -> None:
        self._filter_list(self.inc_ent_list, text)
        self._filter_list(self.exc_ent_list, text)

    def _on_tag_filter_changed(self, text: str) -> None:
        self._filter_list(self.inc_tag_list, text)
        self._filter_list(self.exc_tag_list, text)

    def _process_deferred_icons(self, chunk_size: int = 25) -> None:
        if self._is_closed or not self._pending_icon_items:
            return

        count = 0
        while self._pending_icon_items and count < chunk_size:
            item, path = self._pending_icon_items.pop(0)
            count += 1
            if not path:
                continue
            cached = _CARD_THUMB_CACHE.get(path)
            if cached is None:
                try:
                    p = Path(path)
                    if p.exists():
                        pix = QPixmap(str(p))
                        if not pix.isNull():
                            scaled = pix.scaled(
                                40,
                                40,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                            cached = scaled.toImage()
                            _CARD_THUMB_CACHE[path] = cached
                except OSError:
                    continue
            if cached is not None:
                item.setIcon(QIcon(QPixmap.fromImage(cached)))

        if self._pending_icon_items and not self._is_closed:
            QTimer.singleShot(5, self._process_deferred_icons)

    def flush_pending_icons(self) -> None:
        """Process all remaining pending icons immediately (useful for tests)."""
        while self._pending_icon_items and not self._is_closed:
            self._process_deferred_icons(chunk_size=len(self._pending_icon_items))

    def done(self, r: int) -> None:
        self._is_closed = True
        self._pending_icon_items.clear()
        super().done(r)
