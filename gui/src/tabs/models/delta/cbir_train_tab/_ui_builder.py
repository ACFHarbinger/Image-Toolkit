"""Widget construction for ``CBIRTrainTab`` (``_init_ui``).

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .....styles import set_button_role
from ._sparkline import _SparkLine

if TYPE_CHECKING:
    from ...protos.cbir_train_tab import CBIRTrainTabHostProtocol


class _UIBuilderMixin:
    """Builds the config/telemetry splitter panels."""

    def _init_ui(self: "CBIRTrainTabHostProtocol") -> None:
        root = QVBoxLayout(cast(QWidget, self))
        root.setSpacing(6)

        # Left / Right splitter so config and log sit side-by-side on wide screens
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # ── Left panel: configuration ──────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setWidget(left)
        splitter.addWidget(left_scroll)

        # Dataset ──────────────────────────────────────────────────────────
        dg = QGroupBox("Dataset")
        dgl = QFormLayout(dg)

        self._img_dir = QLineEdit()
        self._img_dir.setPlaceholderText("Folder of images used for training / indexing")
        btn_img = QPushButton("Browse…")
        btn_img.setFixedWidth(80)
        btn_img.clicked.connect(lambda: self._browse_dir(self._img_dir))
        row_img = QHBoxLayout()
        row_img.addWidget(self._img_dir)
        row_img.addWidget(btn_img)
        dgl.addRow("Image dir:", row_img)

        self._out_dir = QLineEdit("cbir_checkpoints")
        btn_out = QPushButton("Browse…")
        btn_out.setFixedWidth(80)
        btn_out.clicked.connect(lambda: self._browse_dir(self._out_dir))
        row_out = QHBoxLayout()
        row_out.addWidget(self._out_dir)
        row_out.addWidget(btn_out)
        dgl.addRow("Output dir:", row_out)

        self._val_split = QDoubleSpinBox()
        self._val_split.setRange(0.01, 0.40)
        self._val_split.setValue(0.10)
        self._val_split.setDecimals(2)
        self._val_split.setSingleStep(0.05)
        self._val_split.setToolTip("Fraction of images held out for Recall@K validation")
        dgl.addRow("Val split:", self._val_split)

        left_layout.addWidget(dg)

        # Backbone / Architecture ──────────────────────────────────────────
        bg = QGroupBox("Backbone / Architecture")
        bgl = QFormLayout(bg)

        self._backbone = QComboBox()
        self._backbone.addItem("CLIP ViT-B/32  (openai/clip-vit-base-patch32)", "clip")
        self._backbone.addItem("ResNet-50  (ImageNet pretrained)", "resnet50")
        self._backbone.addItem("EfficientNet-V2-S  (ImageNet pretrained)", "efficientnet")
        self._backbone.setToolTip(
            "CLIP usually gives the best CBIR quality on photographic and "
            "anime images.  ResNet-50 / EfficientNet are lighter alternatives."
        )
        bgl.addRow("Backbone:", self._backbone)

        self._embed_dim = QComboBox()
        for d in [64, 128, 256, 512]:
            self._embed_dim.addItem(str(d), d)
        self._embed_dim.setCurrentIndex(2)  # 256
        self._embed_dim.setToolTip(
            "Projection head output dimension.  Smaller → faster search and less RAM.  "
            "Larger → higher discriminative capacity."
        )
        bgl.addRow("Embedding dim:", self._embed_dim)

        self._proj_layers = QSpinBox()
        self._proj_layers.setRange(1, 4)
        self._proj_layers.setValue(2)
        self._proj_layers.setToolTip(
            "Number of linear layers in the MLP projection head.\n"
            "2 is sufficient for most cases; 3–4 for very large datasets."
        )
        bgl.addRow("Projection layers:", self._proj_layers)

        self._freeze_epochs = QSpinBox()
        self._freeze_epochs.setRange(0, 20)
        self._freeze_epochs.setValue(2)
        self._freeze_epochs.setToolTip(
            "Train only the projection head for this many epochs, then unfreeze\n"
            "the backbone.  0 = unfreeze from the start."
        )
        bgl.addRow("Freeze backbone (epochs):", self._freeze_epochs)

        self._image_size = QComboBox()
        for s in [224, 256, 336]:
            self._image_size.addItem(f"{s}×{s}", s)
        self._image_size.setCurrentIndex(0)
        bgl.addRow("Input resolution:", self._image_size)

        left_layout.addWidget(bg)

        # Loss ──────────────────────────────────────────────────────────────
        lg = QGroupBox("Loss Function")
        lgl = QFormLayout(lg)

        self._loss_fn = QComboBox()
        self._loss_fn.addItem(
            "InfoNCE / NT-Xent  (SimCLR — recommended, batch≥64)", "infonce"
        )
        self._loss_fn.addItem(
            "TripletMargin  (classic, works well at smaller batch sizes)", "triplet"
        )
        self._loss_fn.currentIndexChanged.connect(self._on_loss_changed)
        lgl.addRow("Loss function:", self._loss_fn)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.01, 1.0)
        self._temperature.setValue(0.07)
        self._temperature.setDecimals(3)
        self._temperature.setSingleStep(0.01)
        self._temperature.setToolTip(
            "InfoNCE softmax temperature τ.  Lower values → sharper distribution.\n"
            "Typical range: 0.05–0.20."
        )
        lgl.addRow("Temperature (τ):", self._temperature)

        self._margin = QDoubleSpinBox()
        self._margin.setRange(0.01, 2.0)
        self._margin.setValue(0.30)
        self._margin.setDecimals(2)
        self._margin.setSingleStep(0.05)
        self._margin.setToolTip("TripletMarginLoss margin.  Typical range: 0.1–0.5.")
        self._margin.setEnabled(False)
        lgl.addRow("Triplet margin:", self._margin)

        self._jitter = QDoubleSpinBox()
        self._jitter.setRange(0.0, 1.5)
        self._jitter.setValue(0.5)
        self._jitter.setDecimals(2)
        self._jitter.setToolTip(
            "Colour-jitter augmentation strength.  0 = disabled.  "
            "Higher values teach more colour-invariant embeddings."
        )
        lgl.addRow("Colour jitter strength:", self._jitter)

        left_layout.addWidget(lg)

        # Training ──────────────────────────────────────────────────────────
        tg = QGroupBox("Training")
        tgl = QFormLayout(tg)

        self._epochs = QSpinBox()
        self._epochs.setRange(1, 500)
        self._epochs.setValue(20)
        tgl.addRow("Epochs:", self._epochs)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(8, 512)
        self._batch_size.setValue(64)
        self._batch_size.setSingleStep(8)
        self._batch_size.setToolTip(
            "InfoNCE loss quality scales with batch size — aim for 64+ if VRAM allows."
        )
        tgl.addRow("Batch size:", self._batch_size)

        self._lr = QDoubleSpinBox()
        self._lr.setRange(1e-6, 1e-2)
        self._lr.setValue(3e-4)
        self._lr.setDecimals(6)
        self._lr.setSingleStep(1e-4)
        tgl.addRow("Learning rate:", self._lr)

        self._bb_lr_scale = QDoubleSpinBox()
        self._bb_lr_scale.setRange(0.001, 1.0)
        self._bb_lr_scale.setValue(0.1)
        self._bb_lr_scale.setDecimals(3)
        self._bb_lr_scale.setToolTip(
            "Backbone LR = main LR × this scale (applied after backbone is unfrozen).\n"
            "Keep low (0.05–0.1) to avoid catastrophic forgetting of pretrained features."
        )
        tgl.addRow("Backbone LR scale:", self._bb_lr_scale)

        self._warmup = QSpinBox()
        self._warmup.setRange(0, 20)
        self._warmup.setValue(2)
        tgl.addRow("LR warmup (epochs):", self._warmup)

        self._workers = QSpinBox()
        self._workers.setRange(0, 16)
        self._workers.setValue(4)
        tgl.addRow("DataLoader workers:", self._workers)

        self._amp = QCheckBox("Mixed precision (AMP / fp16)")
        self._amp.setChecked(True)
        tgl.addRow("", self._amp)

        left_layout.addWidget(tg)

        # FAISS index builder ───────────────────────────────────────────────
        fg = QGroupBox("FAISS Index Builder  (post-training step)")
        fgl = QFormLayout(fg)

        self._ckpt_path = QLineEdit()
        self._ckpt_path.setPlaceholderText("Path to cbir_best.pt or cbir_final.pt")
        btn_ckpt = QPushButton("Browse…")
        btn_ckpt.setFixedWidth(80)
        btn_ckpt.clicked.connect(self._browse_checkpoint)
        row_ckpt = QHBoxLayout()
        row_ckpt.addWidget(self._ckpt_path)
        row_ckpt.addWidget(btn_ckpt)
        fgl.addRow("Checkpoint:", row_ckpt)

        self._index_img_dir = QLineEdit()
        self._index_img_dir.setPlaceholderText(
            "Image library to index (defaults to training image dir)"
        )
        btn_idx_img = QPushButton("Browse…")
        btn_idx_img.setFixedWidth(80)
        btn_idx_img.clicked.connect(lambda: self._browse_dir(self._index_img_dir))
        row_idx_img = QHBoxLayout()
        row_idx_img.addWidget(self._index_img_dir)
        row_idx_img.addWidget(btn_idx_img)
        fgl.addRow("Library dir:", row_idx_img)

        idx_default = str(Path.home() / ".image-toolkit" / "cbir_index")
        self._index_out_dir = QLineEdit(idx_default)
        btn_idx_out = QPushButton("Browse…")
        btn_idx_out.setFixedWidth(80)
        btn_idx_out.clicked.connect(lambda: self._browse_dir(self._index_out_dir))
        row_idx_out = QHBoxLayout()
        row_idx_out.addWidget(self._index_out_dir)
        row_idx_out.addWidget(btn_idx_out)
        fgl.addRow("Index output:", row_idx_out)

        self._btn_build_index = QPushButton("▶  Build FAISS Index")
        self._btn_build_index.setStyleSheet(
            "background:#1565C0; color:white; font-weight:bold; padding:6px 14px;"
        )
        self._btn_build_index.clicked.connect(self._start_build_index)
        fgl.addRow("", self._btn_build_index)

        self._index_progress = QProgressBar()
        self._index_progress.setRange(0, 100)
        self._index_progress.setValue(0)
        self._index_progress.setVisible(False)
        fgl.addRow("Progress:", self._index_progress)

        left_layout.addWidget(fg)
        left_layout.addStretch()

        # ── Right panel: live telemetry ─────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)
        splitter.addWidget(right)

        # Control buttons
        ctrl = QHBoxLayout()
        self._btn_start = QPushButton("▶  Start Training")
        self._btn_cancel = QPushButton("■  Cancel")
        self._btn_cancel.setEnabled(False)
        set_button_role(self._btn_start, "success")
        set_button_role(self._btn_cancel, "danger")
        self._btn_start.clicked.connect(self._start_training)
        self._btn_cancel.clicked.connect(self._cancel_training)
        ctrl.addWidget(self._btn_start)
        ctrl.addWidget(self._btn_cancel)
        right_layout.addLayout(ctrl)

        # Epoch progress
        self._epoch_progress = QProgressBar()
        self._epoch_progress.setRange(0, self._epochs.value())
        self._epoch_progress.setValue(0)
        self._epoch_progress.setFormat("Epoch %v / %m")
        right_layout.addWidget(self._epoch_progress)

        # Loss sparkline
        self._loss_chart = _SparkLine("loss")
        right_layout.addWidget(self._loss_chart)

        # Recall@K display
        self._recall_label = QLabel("Recall@1: —   Recall@5: —   Recall@10: —")
        self._recall_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        right_layout.addWidget(self._recall_label)

        # Metric grid
        metrics_row = QHBoxLayout()
        self._lbl_best_r1 = self._make_metric_label("Best R@1", "—")
        self._lbl_epoch_loss = self._make_metric_label("Last loss", "—")
        self._lbl_lr_now = self._make_metric_label("LR", "—")
        metrics_row.addWidget(self._lbl_best_r1)
        metrics_row.addWidget(self._lbl_epoch_loss)
        metrics_row.addWidget(self._lbl_lr_now)
        right_layout.addLayout(metrics_row)

        # Log box
        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setStyleSheet("font-family: monospace; font-size: 11px;")
        right_layout.addWidget(self._log_box, 1)

        splitter.setSizes([420, 420])

    @staticmethod
    def _make_metric_label(title: str, value: str) -> QLabel:
        w = QLabel(f"<b>{title}</b><br/>{value}")
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setStyleSheet(
            "border:1px solid #555; border-radius:4px; padding:4px; min-width:90px;"
        )
        return w


__all__ = ["_UIBuilderMixin"]
