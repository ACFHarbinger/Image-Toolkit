"""Widget construction for ``SeriesListingsSubTab`` (``_build_ui``).

Extracted from ``series_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from gui.src.constants.listings import ENTRY_STATUS, ENTRY_TYPES
from gui.src.styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from gui.src.tabs.core.elements.common.listings_common import _persist_splitter
from gui.src.elements.database.display.detail_panel import _DetailPanel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class _UIBuilderMixin:
    """Builds the toolbar, stats bar, and gallery/detail splitter."""

    def _build_ui(self) -> None:
        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("🎬 Series Listings")
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

        # ── Semantic search pair (stacked vertically, DB.7) ───────────
        _semantic_pair = QWidget()
        _semantic_vbox = QVBoxLayout(_semantic_pair)
        _semantic_vbox.setContentsMargins(0, 0, 0, 0)
        _semantic_vbox.setSpacing(3)

        semantic_btn = QPushButton("🧠 Search by\nMeaning")
        semantic_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        semantic_btn.setFixedWidth(140)
        semantic_btn.clicked.connect(self._on_semantic_search)
        apply_shadow_effect(semantic_btn)

        build_index_btn = QPushButton("⚙️ Build Search\nIndex")
        build_index_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        build_index_btn.setFixedWidth(140)
        build_index_btn.clicked.connect(self._on_build_search_index)
        apply_shadow_effect(build_index_btn)

        _semantic_vbox.addWidget(semantic_btn)
        _semantic_vbox.addWidget(build_index_btn)
        toolbar.addWidget(_semantic_pair)

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

        self.clear_semantic_btn = QPushButton("❌ Clear Semantic")
        self.clear_semantic_btn.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border:none; border-radius:4px; padding:2px 8px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#e74c3c; }"
        )
        self.clear_semantic_btn.setFixedWidth(130)
        self.clear_semantic_btn.clicked.connect(self._clear_semantic_search)
        self.clear_semantic_btn.hide()

        _clear_vbox.addWidget(self.clear_adv_btn)
        _clear_vbox.addWidget(self.clear_rec_btn)
        _clear_vbox.addWidget(self.clear_semantic_btn)
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

        # ── Pair 2: Load Backup (top) / Sync Backup (bottom) ─────────
        backup_pair = QWidget()
        backup_pair_vbox = QVBoxLayout(backup_pair)
        backup_pair_vbox.setContentsMargins(0, 0, 0, 0)
        backup_pair_vbox.setSpacing(3)

        sync_btn = QPushButton("🔄 Load Backup")
        sync_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        sync_btn.setFixedWidth(130)
        sync_btn.clicked.connect(self._synchronize_listings)
        apply_shadow_effect(sync_btn)

        update_btn = QPushButton("⚡ Sync Backup")
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
        _persist_splitter(splitter, "SeriesListingsSubTab_main")

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


__all__ = ["_UIBuilderMixin"]
