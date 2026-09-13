"""Widget construction for ``CBIRTrainTab`` (``_init_ui``).

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .....components import SectionedFormBuilder
from .....styles import set_button_role
from .....theming.theme_api import qss
from ._sparkline import _SparkLine
from ._tab_bound import TabBoundController


class CBIRTrainUIBuilder(TabBoundController):
    """Builds the config/telemetry splitter panels (§5 R2.f, #567)."""

    def init_ui(self) -> None:
        root = QVBoxLayout(self.tab)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # Left panel: configuration with SectionedFormBuilder (§5 R2.f, #567)
        builder = SectionedFormBuilder(splitter, scrollable=True, spacing=6, margins=(0, 0, 4, 0))
        self._build_dataset_group(builder)
        self._build_backbone_group(builder)
        self._build_loss_group(builder)
        self._build_training_group(builder)
        self._build_faiss_group(builder)
        builder.add_stretch()
        splitter.addWidget(builder.root_widget)

        # Right panel: telemetry
        self._build_telemetry_panel(splitter)
        splitter.setSizes([420, 420])

    _init_ui = init_ui
    _build_ui = init_ui

    def _build_dataset_group(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Dataset")

        self._img_dir = QLineEdit()
        self._img_dir.setPlaceholderText("Folder of images used for training / indexing")
        btn_img = QPushButton("Browse…")
        btn_img.setFixedWidth(80)
        btn_img.clicked.connect(lambda: self._browse_dir(self._img_dir))
        sec.add_path_picker(self._img_dir, btn_img, label="Image dir:", apply_shadow=False)

        self._out_dir = QLineEdit("cbir_checkpoints")
        btn_out = QPushButton("Browse…")
        btn_out.setFixedWidth(80)
        btn_out.clicked.connect(lambda: self._browse_dir(self._out_dir))
        sec.add_path_picker(self._out_dir, btn_out, label="Output dir:", apply_shadow=False)

        self._val_split = QDoubleSpinBox()
        self._val_split.setRange(0.01, 0.40)
        self._val_split.setValue(0.10)
        self._val_split.setDecimals(2)
        self._val_split.setSingleStep(0.05)
        self._val_split.setToolTip("Fraction of images held out for Recall@K validation")
        sec.add_row("Val split:", self._val_split)

    def _build_backbone_group(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Backbone / Architecture")

        self._backbone = QComboBox()
        self._backbone.addItem("CLIP ViT-B/32  (openai/clip-vit-base-patch32)", "clip")
        self._backbone.addItem("ResNet-50  (ImageNet pretrained)", "resnet50")
        self._backbone.addItem("EfficientNet-V2-S  (ImageNet pretrained)", "efficientnet")
        self._backbone.setToolTip(
            "CLIP usually gives the best CBIR quality on photographic and "
            "anime images.  ResNet-50 / EfficientNet are lighter alternatives."
        )
        sec.add_row("Backbone:", self._backbone)

        self._embed_dim = QComboBox()
        for d in [64, 128, 256, 512]:
            self._embed_dim.addItem(str(d), d)
        self._embed_dim.setCurrentIndex(2)
        self._embed_dim.setToolTip(
            "Projection head output dimension.  Smaller → faster search and less RAM.  "
            "Larger → higher discriminative capacity."
        )
        sec.add_row("Embedding dim:", self._embed_dim)

        self._proj_layers = QSpinBox()
        self._proj_layers.setRange(1, 4)
        self._proj_layers.setValue(2)
        self._proj_layers.setToolTip(
            "Number of linear layers in the MLP projection head.\n"
            "2 is sufficient for most cases; 3–4 for very large datasets."
        )
        sec.add_row("Projection layers:", self._proj_layers)

        self._freeze_epochs = QSpinBox()
        self._freeze_epochs.setRange(0, 20)
        self._freeze_epochs.setValue(2)
        self._freeze_epochs.setToolTip(
            "Train only the projection head for this many epochs, then unfreeze\n"
            "the backbone.  0 = unfreeze from the start."
        )
        sec.add_row("Freeze backbone (epochs):", self._freeze_epochs)

        self._image_size = QComboBox()
        for s in [224, 256, 336]:
            self._image_size.addItem(f"{s}×{s}", s)
        self._image_size.setCurrentIndex(0)
        sec.add_row("Input resolution:", self._image_size)

    def _build_loss_group(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Loss Function")

        self._loss_fn = QComboBox()
        self._loss_fn.addItem("InfoNCE / NT-Xent  (SimCLR — recommended, batch≥64)", "infonce")
        self._loss_fn.addItem("TripletMargin  (classic, works well at smaller batch sizes)", "triplet")
        self._loss_fn.currentIndexChanged.connect(self._on_loss_changed)
        sec.add_row("Loss function:", self._loss_fn)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.01, 1.0)
        self._temperature.setValue(0.07)
        self._temperature.setDecimals(3)
        self._temperature.setSingleStep(0.01)
        self._temperature.setToolTip(
            "InfoNCE softmax temperature τ.  Lower values → sharper distribution.\nTypical range: 0.05–0.20."
        )
        sec.add_row("Temperature (τ):", self._temperature)

        self._margin = QDoubleSpinBox()
        self._margin.setRange(0.01, 2.0)
        self._margin.setValue(0.30)
        self._margin.setDecimals(2)
        self._margin.setSingleStep(0.05)
        self._margin.setToolTip("TripletMarginLoss margin.  Typical range: 0.1–0.5.")
        self._margin.setEnabled(False)
        sec.add_row("Triplet margin:", self._margin)

        self._jitter = QDoubleSpinBox()
        self._jitter.setRange(0.0, 1.5)
        self._jitter.setValue(0.5)
        self._jitter.setDecimals(2)
        self._jitter.setToolTip(
            "Colour-jitter augmentation strength.  0 = disabled.  Higher values teach more colour-invariant embeddings."
        )
        sec.add_row("Colour jitter strength:", self._jitter)

    def _build_training_group(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Training")

        self._epochs = QSpinBox()
        self._epochs.setRange(1, 500)
        self._epochs.setValue(20)
        sec.add_row("Epochs:", self._epochs)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(8, 512)
        self._batch_size.setValue(64)
        self._batch_size.setSingleStep(8)
        self._batch_size.setToolTip("InfoNCE loss quality scales with batch size — aim for 64+ if VRAM allows.")
        sec.add_row("Batch size:", self._batch_size)

        self._lr = QDoubleSpinBox()
        self._lr.setRange(1e-6, 1e-2)
        self._lr.setValue(3e-4)
        self._lr.setDecimals(6)
        self._lr.setSingleStep(1e-4)
        sec.add_row("Learning rate:", self._lr)

        self._bb_lr_scale = QDoubleSpinBox()
        self._bb_lr_scale.setRange(0.001, 1.0)
        self._bb_lr_scale.setValue(0.1)
        self._bb_lr_scale.setDecimals(3)
        self._bb_lr_scale.setToolTip(
            "Backbone LR = main LR × this scale (applied after backbone is unfrozen).\n"
            "Keep low (0.05–0.1) to avoid catastrophic forgetting of pretrained features."
        )
        sec.add_row("Backbone LR scale:", self._bb_lr_scale)

        self._warmup = QSpinBox()
        self._warmup.setRange(0, 20)
        self._warmup.setValue(2)
        sec.add_row("LR warmup (epochs):", self._warmup)

        self._workers = QSpinBox()
        self._workers.setRange(0, 16)
        self._workers.setValue(4)
        sec.add_row("DataLoader workers:", self._workers)

        self._amp = QCheckBox("Mixed precision (AMP / fp16)")
        self._amp.setChecked(True)
        sec.add_row("", self._amp)

    def _build_faiss_group(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("FAISS Index Builder  (post-training step)")

        self._ckpt_path = QLineEdit()
        self._ckpt_path.setPlaceholderText("Path to cbir_best.pt or cbir_final.pt")
        btn_ckpt = QPushButton("Browse…")
        btn_ckpt.setFixedWidth(80)
        btn_ckpt.clicked.connect(self._browse_checkpoint)
        sec.add_path_picker(self._ckpt_path, btn_ckpt, label="Checkpoint:", apply_shadow=False)

        self._index_img_dir = QLineEdit()
        self._index_img_dir.setPlaceholderText("Image library to index (defaults to training image dir)")
        btn_idx_img = QPushButton("Browse…")
        btn_idx_img.setFixedWidth(80)
        btn_idx_img.clicked.connect(lambda: self._browse_dir(self._index_img_dir))
        sec.add_path_picker(self._index_img_dir, btn_idx_img, label="Library dir:", apply_shadow=False)

        idx_default = str(Path.home() / ".image-toolkit" / "cbir_index")
        self._index_out_dir = QLineEdit(idx_default)
        btn_idx_out = QPushButton("Browse…")
        btn_idx_out.setFixedWidth(80)
        btn_idx_out.clicked.connect(lambda: self._browse_dir(self._index_out_dir))
        sec.add_path_picker(self._index_out_dir, btn_idx_out, label="Index output:", apply_shadow=False)

        self._btn_build_index = QPushButton("▶  Build FAISS Index")
        set_button_role(self._btn_build_index, "success")
        self._btn_build_index.clicked.connect(self._start_build_index)
        sec.add_row("", self._btn_build_index)

        self._index_progress = QProgressBar()
        self._index_progress.setRange(0, 100)
        self._index_progress.setValue(0)
        self._index_progress.setVisible(False)
        sec.add_row("Progress:", self._index_progress)

    def _build_telemetry_panel(self, splitter: QSplitter) -> None:
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
        self._recall_label.setStyleSheet(qss("monospace_medium"))
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
        self._log_box.setStyleSheet(qss("monospace_small"))
        right_layout.addWidget(self._log_box, 1)

        splitter.setSizes([420, 420])

    _init_ui = init_ui

    @staticmethod
    def _make_metric_label(title: str, value: str) -> QLabel:
        w = QLabel(f"<b>{title}</b><br/>{value}")
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setStyleSheet(qss("cbir_metric_label"))
        return w


__all__ = ["CBIRTrainUIBuilder"]
