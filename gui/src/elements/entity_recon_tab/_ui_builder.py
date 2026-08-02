"""Widget construction for ``EntityReconTab`` (``_build_ui``).

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.web.recon.config import (
    EMBED_CLIP,
    EMBED_FACE,
    SCOPE_BOTH,
    SCOPE_LOCAL,
    SCOPE_WEB,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from ...styles import apply_shadow_effect
from ._clickable_label import _ClickableImageLabel


class _UIBuilderMixin:
    """Builds the config bar, three-pane splitter, and batch dataset builder."""

    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- dataset / config bar ------------------------------------------
        cfg_group = QGroupBox("Identity Dataset and Discovery")
        cfg_form = QFormLayout(cfg_group)

        ds_row = QHBoxLayout()
        self.dataset_edit = QLineEdit()
        self.dataset_edit.setPlaceholderText("Dataset root — /Dataset/FirstName_LastName/image.jpg ...")
        ds_row.addWidget(self.dataset_edit)
        btn_ds = QPushButton("Browse...")
        btn_ds.clicked.connect(self._browse_dataset)
        ds_row.addWidget(btn_ds)
        self.btn_build = QPushButton("Build Identity Index")
        self.btn_build.clicked.connect(self._build_index)
        apply_shadow_effect(self.btn_build, "#000000", 8, 0, 3)
        ds_row.addWidget(self.btn_build)
        cfg_form.addRow("Dataset root:", ds_row)

        opts_row = QHBoxLayout()
        self.embed_combo = QComboBox()
        self.embed_combo.addItem("Faces (ArcFace)", EMBED_FACE)
        self.embed_combo.addItem("Characters / objects (CLIP)", EMBED_CLIP)
        self.embed_combo.currentIndexChanged.connect(self._on_embed_changed)
        opts_row.addWidget(QLabel("Embedding:"))
        opts_row.addWidget(self.embed_combo)
        opts_row.addSpacing(16)
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Local only (offline)", SCOPE_LOCAL)
        self.scope_combo.addItem("Web only", SCOPE_WEB)
        self.scope_combo.addItem("Local + Web", SCOPE_BOTH)
        self.scope_combo.setToolTip(
            "Local only — resolve against the local identity index, fully offline.\n"
            "Web only — reverse-image web discovery only (skips the local index).\n"
            "Local + Web — try the local index first, fall back to web on no match."
        )
        self.scope_combo.setCurrentIndex(self.scope_combo.findData(getattr(self._config, "search_scope", SCOPE_LOCAL)))
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        opts_row.addWidget(QLabel("Search scope:"))
        opts_row.addWidget(self.scope_combo)
        opts_row.addStretch(1)
        cfg_form.addRow("Options:", opts_row)
        # Apply the initial scope so privacy_mode/search_scope start consistent.
        self._apply_scope(getattr(self._config, "search_scope", SCOPE_LOCAL))
        root.addWidget(cfg_group)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        root.addWidget(self.progress)

        # --- three-pane splitter -------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: source + segmentation
        left = QWidget()
        left_v = QVBoxLayout(left)
        left_v.addWidget(QLabel("Source"))
        self.image_label = _ClickableImageLabel()
        self.image_label.clicked.connect(self._on_image_clicked)
        img_scroll = QScrollArea()
        img_scroll.setWidgetResizable(True)
        img_scroll.setWidget(self.image_label)
        left_v.addWidget(img_scroll, 1)
        src_btns = QHBoxLayout()
        btn_load = QPushButton("Load Image...")
        btn_load.clicked.connect(self._browse_source)
        src_btns.addWidget(btn_load)
        self.btn_resolve = QPushButton("Resolve Identity")
        self.btn_resolve.clicked.connect(self._resolve)
        apply_shadow_effect(self.btn_resolve, "#000000", 8, 0, 3)
        src_btns.addWidget(self.btn_resolve)
        left_v.addLayout(src_btns)
        self.hint_label = QLabel("Click a subject in the image to segment it, or Resolve the whole frame.")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #99aab5; font-size: 11px;")
        left_v.addWidget(self.hint_label)
        splitter.addWidget(left)

        # Center: identity card
        center = QWidget()
        center_v = QVBoxLayout(center)
        center_v.addWidget(QLabel("Identity"))
        card = QGroupBox()
        card_v = QVBoxLayout(card)
        self.name_label = QLabel("—")
        self.name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_v.addWidget(self.name_label)
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setFormat("%p%")
        card_v.addWidget(self.conf_bar)
        self.method_label = QLabel("Method: —")
        self.method_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.method_label.setStyleSheet("color: #b9bbbe;")
        card_v.addWidget(self.method_label)
        self.origin_label = QLabel("Origin: —")
        self.origin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.origin_label.setStyleSheet("color: #b9bbbe;")
        card_v.addWidget(self.origin_label)
        card_v.addStretch(1)
        exp_row = QHBoxLayout()
        self.btn_export_json = QPushButton("Export JSON")
        self.btn_export_json.clicked.connect(lambda: self._export("json"))
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.clicked.connect(lambda: self._export("csv"))
        exp_row.addWidget(self.btn_export_json)
        exp_row.addWidget(self.btn_export_csv)
        card_v.addLayout(exp_row)
        center_v.addWidget(card, 1)
        splitter.addWidget(center)

        # Right: provenance trail
        right = QWidget()
        right_v = QVBoxLayout(right)
        right_v.addWidget(QLabel("Provenance"))
        self.prov_tree = QTreeWidget()
        self.prov_tree.setHeaderLabels(["Source", "Score"])
        self.prov_tree.setRootIsDecorated(True)
        self.prov_tree.itemDoubleClicked.connect(self._on_prov_activated)
        self.prov_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.prov_tree.customContextMenuRequested.connect(self._on_prov_context_menu)
        self.prov_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        right_v.addWidget(self.prov_tree, 1)
        splitter.addWidget(right)

        splitter.setSizes([420, 320, 380])
        root.addWidget(splitter, 1)

        # --- batch dataset builder -----------------------------------------
        batch_group = QGroupBox("Batch Dataset Builder")
        batch_v = QVBoxLayout(batch_group)

        # Target directory: approved images are moved into
        # <target>/<FirstName_LastName>/. Defaults to the dataset root, or —
        # when blank — next to each source image (original behaviour).
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target directory:"))
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("Where identity folders are created (defaults to the dataset root)")
        target_row.addWidget(self.target_edit, 1)
        btn_target = QPushButton("Browse...")
        btn_target.clicked.connect(self._browse_target)
        target_row.addWidget(btn_target)
        batch_v.addLayout(target_row)

        batch_btns = QHBoxLayout()
        btn_add = QPushButton("Add Images...")
        btn_add.clicked.connect(self._browse_batch)
        batch_btns.addWidget(btn_add)
        self.btn_approve = QPushButton("Approve All → Move to Identity Folders")
        self.btn_approve.clicked.connect(self._approve_batch)
        self.btn_approve.setEnabled(False)
        batch_btns.addWidget(self.btn_approve)
        batch_btns.addStretch(1)
        batch_v.addLayout(batch_btns)
        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels(["Image", "Suggested identity", "Score"])
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.batch_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.batch_table.setMaximumHeight(180)
        batch_v.addWidget(self.batch_table)
        root.addWidget(batch_group)

        self.status_label = QLabel("Ready. Build an identity index to begin.")
        self.status_label.setStyleSheet("color: #b9bbbe;")
        root.addWidget(self.status_label)


__all__ = ["_UIBuilderMixin"]
