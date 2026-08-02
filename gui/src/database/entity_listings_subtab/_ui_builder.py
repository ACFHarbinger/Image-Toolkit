"""Widget construction for ``EntityListingsSubTab`` (``_build_ui``).

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from gui.src.constants.listings import ENTITY_ROLES, ENTITY_TYPES
from gui.src.styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from gui.src.tabs.core.elements.common.listings_common import _persist_splitter
from gui.src.database.display.entity_detail_panel import _EntityDetailPanel
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

        # ── Semantic search pair (stacked vertically, DB.7) ───────────
        _semantic_pair = QWidget()
        _semantic_vbox = QVBoxLayout(_semantic_pair)
        _semantic_vbox.setContentsMargins(0, 0, 0, 0)
        _semantic_vbox.setSpacing(3)

        semantic_btn = QPushButton("🧠 Search by Meaning")
        semantic_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        semantic_btn.setFixedWidth(140)
        semantic_btn.clicked.connect(self._on_semantic_search)
        apply_shadow_effect(semantic_btn)

        build_index_btn = QPushButton("⚙️ Build Search Index")
        build_index_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        build_index_btn.setFixedWidth(140)
        build_index_btn.clicked.connect(self._on_build_search_index)
        apply_shadow_effect(build_index_btn)

        _semantic_vbox.addWidget(semantic_btn)
        _semantic_vbox.addWidget(build_index_btn)
        toolbar.addWidget(_semantic_pair)

        self.clear_semantic_btn = QPushButton("❌ Clear Semantic")
        self.clear_semantic_btn.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border:none; border-radius:4px; padding:2px 8px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#e74c3c; }"
        )
        self.clear_semantic_btn.setFixedWidth(130)
        self.clear_semantic_btn.clicked.connect(self._clear_semantic_search)
        self.clear_semantic_btn.hide()
        toolbar.addWidget(self.clear_semantic_btn)

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


__all__ = ["_UIBuilderMixin"]
