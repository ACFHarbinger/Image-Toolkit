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
)

from ....styles import apply_shadow_effect
from ._clickable_label import _ClickableImageLabel
from ._tab_bound import TabBoundController


class EntityReconUIBuilder(TabBoundController):
    """Builds the config bar, three-pane splitter, and batch dataset builder."""

    def _build_ui(self):
        root = QVBoxLayout(self.tab)

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
        opts_row.addWidget(QLabel("Embedding mode:"))
        self.embed_combo = QComboBox()
        self.embed_combo.addItem("Face (InsightFace)", EMBED_FACE)
        self.embed_combo.addItem("Whole image (CLIP)", EMBED_CLIP)
        self.embed_combo.currentIndexChanged.connect(self._on_embed_changed)
        opts_row.addWidget(self.embed_combo)

        opts_row.addSpacing(16)
        opts_row.addWidget(QLabel("Search scope:"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Local dataset only (offline)", SCOPE_LOCAL)
        self.scope_combo.addItem("Web discovery only", SCOPE_WEB)
        self.scope_combo.addItem("Local + Web fallback", SCOPE_BOTH)
        self.scope_combo.setCurrentIndex(0)
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        opts_row.addWidget(self.scope_combo)

        opts_row.addStretch(1)
        cfg_form.addRow("Discovery scope:", opts_row)

        root.addWidget(cfg_group)

        # --- three-pane splitter -------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Pane 1: Source image & segmentation
        p1 = QGroupBox("Source Subject")
        p1_v = QVBoxLayout(p1)
        p1_top = QHBoxLayout()
        btn_src = QPushButton("Load Image...")
        btn_src.clicked.connect(self._browse_source)
        apply_shadow_effect(btn_src, "#000000", 8, 0, 3)
        p1_top.addWidget(btn_src)
        p1_top.addStretch(1)
        p1_v.addLayout(p1_top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.image_label = _ClickableImageLabel()
        self.image_label.clicked.connect(self._on_image_clicked)
        self.scroll.setWidget(self.image_label)
        p1_v.addWidget(self.scroll, 1)

        self.btn_resolve = QPushButton("Resolve Identity")
        self.btn_resolve.clicked.connect(self._resolve)
        apply_shadow_effect(self.btn_resolve, "#000000", 8, 0, 3)
        p1_v.addWidget(self.btn_resolve)
        splitter.addWidget(p1)

        # Pane 2: Identity result card
        p2 = QGroupBox("Identity")
        p2_v = QVBoxLayout(p2)
        self.name_label = QLabel("—")
        self.name_label.setStyleSheet("font-size: 20pt; font-weight: bold; color: #ffffff;")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        p2_v.addWidget(self.name_label)

        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setTextVisible(True)
        self.conf_bar.setFormat("Confidence: %p%")
        p2_v.addWidget(self.conf_bar)

        self.method_label = QLabel("Method: —")
        self.origin_label = QLabel("Origin: —")
        p2_v.addWidget(self.method_label)
        p2_v.addWidget(self.origin_label)

        p2_v.addStretch(1)
        splitter.addWidget(p2)

        # Pane 3: Provenance tree & export
        p3 = QGroupBox("Provenance & Evidence")
        p3_v = QVBoxLayout(p3)
        self.prov_tree = QTreeWidget()
        self.prov_tree.setHeaderLabels(["Source / Match", "Score / Hits"])
        self.prov_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.prov_tree.itemActivated.connect(self._on_prov_activated)
        self.prov_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.prov_tree.customContextMenuRequested.connect(self._on_prov_context_menu)
        p3_v.addWidget(self.prov_tree, 1)

        exp_h = QHBoxLayout()
        btn_json = QPushButton("Export JSON")
        btn_json.clicked.connect(lambda: self._export("json"))
        exp_h.addWidget(btn_json)
        btn_csv = QPushButton("Export CSV")
        btn_csv.clicked.connect(lambda: self._export("csv"))
        exp_h.addWidget(btn_csv)
        exp_h.addStretch(1)
        p3_v.addLayout(exp_h)
        splitter.addWidget(p3)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)
        root.addWidget(splitter, 1)

        # --- progress & status ---------------------------------------------
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # --- batch dataset builder -----------------------------------------
        batch_group = QGroupBox("Batch Dataset Builder")
        batch_v = QVBoxLayout(batch_group)

        # Target directory row: where approved identity folders should be created,
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


_UIBuilderMixin = EntityReconUIBuilder  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["EntityReconUIBuilder", "_UIBuilderMixin"]
