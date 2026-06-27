"""Training tab for the CBIR (Reverse Image Search) embedding model.

Plugs into :class:`~gui.src.tabs.models.train_tab.UnifiedTrainTab` as a
fourth option alongside LoRA, R3GAN, and AnimeStitchNet.

Architecture overview
---------------------
* Dataset group  — image directory, output directory, val split.
* Backbone group — CLIP ViT-B/32 / ResNet-50 / EfficientNet-V2-S, projection
                   head width and depth, freeze-backbone warm-up epochs.
* Loss group     — InfoNCE (NT-Xent) or TripletMargin; temperature / margin.
* Training group — epochs, batch size, learning rate, warmup, AMP, workers.
* Logging group  — TensorBoard run name, optional W&B toggle.
* FAISS group    — "Build Index" button + image directory / output directory
                   for the post-training index construction step.
* Live telemetry — mini loss chart (unicode sparkline), Recall@1/5/10 display,
                   epoch progress bar, scrollable log box.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from backend.src.models.tuning.cbir_tuner import CBIRTuner

    _TRAINER_OK = True
except ImportError:
    _TRAINER_OK = False
    CBIRTuner = None  # type: ignore[assignment,misc]

try:
    from backend.src.models.tuning.cbir_index_builder import build_cbir_index

    _INDEX_OK = True
except ImportError:
    _INDEX_OK = False
    build_cbir_index = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Mini sparkline chart
# ---------------------------------------------------------------------------

class _SparkLine(QLabel):
    """Rolling unicode sparkline showing up to MAX_POINTS scalar values."""

    MAX_POINTS = 64
    _BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(self, label: str = "loss") -> None:
        super().__init__()
        self._label = label
        self._values: list = []
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(20)
        self.setStyleSheet("font-family: monospace; font-size: 11px;")

    def push(self, v: float) -> None:
        self._values.append(v)
        if len(self._values) > self.MAX_POINTS:
            self._values.pop(0)
        self._redraw()

    def reset(self) -> None:
        self._values.clear()
        self.setText("")

    def _redraw(self) -> None:
        if not self._values:
            return
        lo, hi = min(self._values), max(self._values)
        span = hi - lo or 1e-9
        bar = "".join(
            self._BLOCKS[min(8, int(((v - lo) / span) * 8))] for v in self._values
        )
        self.setText(f"{self._label}  {bar}  {self._values[-1]:.4f}")


# ---------------------------------------------------------------------------
# CBIRTrainTab
# ---------------------------------------------------------------------------

class CBIRTrainTab(QWidget):
    """Training UI for fine-tuning a CBIR embedding model.

    Follows the same ``collect()`` / ``set_config()`` / ``get_default_config()``
    contract as the other ``UnifiedTrainTab`` children so the parent can save
    and restore session settings.
    """

    # Signals emitted from the background thread (thread-safe)
    sig_log = Signal(str)
    sig_metrics = Signal(dict)
    sig_epoch = Signal(int, dict)
    sig_done = Signal(str, str)          # (status: "ok"|"error"|"cancel", message)
    sig_index_progress = Signal(int, int)  # (n_done, n_total)
    sig_index_done = Signal(str, str)    # (status, message)

    def __init__(self) -> None:
        super().__init__()
        self._train_thread: Optional[threading.Thread] = None
        self._index_thread: Optional[threading.Thread] = None
        self._init_ui()
        self.sig_log.connect(self._on_log)
        self.sig_metrics.connect(self._on_metrics)
        self.sig_epoch.connect(self._on_epoch)
        self.sig_done.connect(self._on_done)
        self.sig_index_progress.connect(self._on_index_progress)
        self.sig_index_done.connect(self._on_index_done)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
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
            "Projection head output dimension.  Smaller → faster search & less RAM.  "
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
        self._btn_start.setStyleSheet(
            "background:#4CAF50; color:white; font-weight:bold; padding:8px 16px;"
        )
        self._btn_cancel.setStyleSheet(
            "background:#f44336; color:white; font-weight:bold; padding:8px 16px;"
        )
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

    # ------------------------------------------------------------------
    # Slots (main thread only)
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_log(self, msg: str) -> None:
        self._log_box.append(msg)
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot(dict)
    def _on_metrics(self, m: dict) -> None:
        if "total" in m:
            self._loss_chart.push(float(m["total"]))

    @Slot(int, dict)
    def _on_epoch(self, epoch: int, m: dict) -> None:
        self._epoch_progress.setMaximum(self._epochs.value())
        self._epoch_progress.setValue(epoch)

        r1 = m.get("recall_at_1", 0.0)
        r5 = m.get("recall_at_5", 0.0)
        r10 = m.get("recall_at_10", 0.0)
        loss = m.get("total", 0.0)

        self._recall_label.setText(
            f"Recall@1: {r1:.3f}   Recall@5: {r5:.3f}   Recall@10: {r10:.3f}"
        )
        self._lbl_epoch_loss.setText(f"<b>Last loss</b><br/>{loss:.4f}")

        # Update best R@1 label
        current_best = getattr(self, "_best_r1", 0.0)
        if r1 > current_best:
            self._best_r1 = r1
            self._lbl_best_r1.setText(f"<b>Best R@1</b><br/>{r1:.3f}")

    @Slot(str, str)
    def _on_done(self, status: str, msg: str) -> None:
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        if _TRAINER_OK and CBIRTuner is not None:
            CBIRTuner.is_cancelled = False
        if status == "ok":
            QMessageBox.information(self, "Training complete", msg)
        elif status == "cancel":
            QMessageBox.warning(self, "Cancelled", msg)
        else:
            QMessageBox.critical(self, "Training error", msg)

    @Slot(int, int)
    def _on_index_progress(self, done: int, total: int) -> None:
        self._index_progress.setValue(int(done / max(total, 1) * 100))

    @Slot(str, str)
    def _on_index_done(self, status: str, msg: str) -> None:
        self._btn_build_index.setEnabled(True)
        self._index_progress.setVisible(False)
        if status == "ok":
            QMessageBox.information(self, "Index built", msg)
        else:
            QMessageBox.critical(self, "Index build failed", msg)

    # ------------------------------------------------------------------
    # Loss function toggle
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_loss_changed(self, idx: int) -> None:
        loss_id = self._loss_fn.currentData()
        self._temperature.setEnabled(loss_id == "infonce")
        self._margin.setEnabled(loss_id == "triplet")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Select directory", line_edit.text() or ".",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            line_edit.setText(d)

    def _browse_checkpoint(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CBIR checkpoint", self._out_dir.text(),
            "PyTorch checkpoints (*.pt *.pth)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._ckpt_path.setText(path)

    def _start_training(self) -> None:
        if not _TRAINER_OK or CBIRTuner is None:
            QMessageBox.critical(
                self, "Missing dependencies",
                "Could not import CBIRTuner.\n"
                "Ensure PyTorch and transformers are installed.",
            )
            return

        img_dir = self._img_dir.text().strip()
        if not img_dir:
            QMessageBox.warning(self, "No directory", "Please select an image directory.")
            return

        self._btn_start.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._best_r1 = 0.0
        self._loss_chart.reset()
        self._log_box.clear()
        self._epoch_progress.setValue(0)
        self._epoch_progress.setMaximum(self._epochs.value())

        config = self.collect()

        tuner = CBIRTuner(
            config=config,
            on_log=lambda m: self.sig_log.emit(m),
            on_metrics=lambda m: self.sig_metrics.emit(m),
            on_epoch_end=lambda e, m: self.sig_epoch.emit(e, m),
        )

        def _run() -> None:
            try:
                tuner.train()
                # Auto-populate checkpoint path on success
                best = Path(config["output_dir"]) / "cbir_best.pt"
                if best.is_file():
                    self._ckpt_path.setText(str(best))
                self.sig_done.emit("ok", "Training finished successfully.")
            except Exception as exc:
                if _TRAINER_OK and CBIRTuner is not None and CBIRTuner.is_cancelled:
                    self.sig_done.emit("cancel", "Training cancelled by user.")
                else:
                    self.sig_done.emit("error", str(exc))

        self._train_thread = threading.Thread(target=_run, daemon=True)
        self._train_thread.start()

    def _cancel_training(self) -> None:
        if _TRAINER_OK and CBIRTuner is not None:
            CBIRTuner.cancel()
        self._btn_cancel.setEnabled(False)
        self._on_log("Cancellation requested…")

    def _start_build_index(self) -> None:
        if not _INDEX_OK or build_cbir_index is None:
            QMessageBox.critical(
                self, "Missing dependencies",
                "Could not import build_cbir_index.\n"
                "Ensure faiss-cpu and transformers are installed.",
            )
            return

        ckpt = self._ckpt_path.text().strip()
        if not ckpt:
            QMessageBox.warning(
                self, "No checkpoint",
                "Please specify a checkpoint file (cbir_best.pt) before building the index.",
            )
            return

        img_dir = self._index_img_dir.text().strip() or self._img_dir.text().strip()
        if not img_dir:
            QMessageBox.warning(self, "No image directory", "Please specify the image library directory.")
            return

        out_dir = self._index_out_dir.text().strip()
        self._btn_build_index.setEnabled(False)
        self._index_progress.setValue(0)
        self._index_progress.setVisible(True)
        self._on_log(f"Building FAISS index from: {ckpt}")
        self._on_log(f"  Image library : {img_dir}")
        self._on_log(f"  Output dir    : {out_dir}")

        def _run() -> None:
            try:
                n, index_path = build_cbir_index(
                    checkpoint_path=ckpt,
                    image_dir=img_dir,
                    output_dir=out_dir or None,
                    on_progress=lambda d, t: self.sig_index_progress.emit(d, t),
                )
                self.sig_index_done.emit(
                    "ok",
                    f"Index built successfully.\n"
                    f"{n} images indexed.\n"
                    f"FAISS index: {index_path}",
                )
            except Exception as exc:
                self.sig_index_done.emit("error", str(exc))

        self._index_thread = threading.Thread(target=_run, daemon=True)
        self._index_thread.start()

    # ------------------------------------------------------------------
    # Config persistence (UnifiedTrainTab contract)
    # ------------------------------------------------------------------

    def collect(self) -> dict:
        """Return all widget values as a config dict."""
        return {
            "image_dir": self._img_dir.text().strip(),
            "output_dir": self._out_dir.text().strip() or "cbir_checkpoints",
            "val_split": self._val_split.value(),
            "backbone": self._backbone.currentData(),
            "embed_dim": self._embed_dim.currentData(),
            "proj_layers": self._proj_layers.value(),
            "freeze_backbone_epochs": self._freeze_epochs.value(),
            "image_size": self._image_size.currentData(),
            "loss_fn": self._loss_fn.currentData(),
            "temperature": self._temperature.value(),
            "triplet_margin": self._margin.value(),
            "jitter_strength": self._jitter.value(),
            "epochs": self._epochs.value(),
            "batch_size": self._batch_size.value(),
            "lr": self._lr.value(),
            "backbone_lr_scale": self._bb_lr_scale.value(),
            "warmup_epochs": self._warmup.value(),
            "num_workers": self._workers.value(),
            "amp": self._amp.isChecked(),
            # Index builder
            "ckpt_path": self._ckpt_path.text().strip(),
            "index_img_dir": self._index_img_dir.text().strip(),
            "index_out_dir": self._index_out_dir.text().strip(),
        }

    def set_config(self, cfg: dict) -> None:
        """Restore widget values from a config dict."""
        _set = {
            "image_dir": lambda v: self._img_dir.setText(v),
            "output_dir": lambda v: self._out_dir.setText(v),
            "val_split": lambda v: self._val_split.setValue(float(v)),
            "backbone": lambda v: self._backbone.setCurrentIndex(
                max(0, self._backbone.findData(v))
            ),
            "embed_dim": lambda v: self._embed_dim.setCurrentIndex(
                max(0, self._embed_dim.findData(int(v)))
            ),
            "proj_layers": lambda v: self._proj_layers.setValue(int(v)),
            "freeze_backbone_epochs": lambda v: self._freeze_epochs.setValue(int(v)),
            "image_size": lambda v: self._image_size.setCurrentIndex(
                max(0, self._image_size.findData(int(v)))
            ),
            "loss_fn": lambda v: self._loss_fn.setCurrentIndex(
                max(0, self._loss_fn.findData(v))
            ),
            "temperature": lambda v: self._temperature.setValue(float(v)),
            "triplet_margin": lambda v: self._margin.setValue(float(v)),
            "jitter_strength": lambda v: self._jitter.setValue(float(v)),
            "epochs": lambda v: self._epochs.setValue(int(v)),
            "batch_size": lambda v: self._batch_size.setValue(int(v)),
            "lr": lambda v: self._lr.setValue(float(v)),
            "backbone_lr_scale": lambda v: self._bb_lr_scale.setValue(float(v)),
            "warmup_epochs": lambda v: self._warmup.setValue(int(v)),
            "num_workers": lambda v: self._workers.setValue(int(v)),
            "amp": lambda v: self._amp.setChecked(bool(v)),
            "ckpt_path": lambda v: self._ckpt_path.setText(v),
            "index_img_dir": lambda v: self._index_img_dir.setText(v),
            "index_out_dir": lambda v: self._index_out_dir.setText(v),
        }
        for key, setter in _set.items():
            if key in cfg:
                try:
                    setter(cfg[key])
                except Exception:
                    pass

    def get_default_config(self) -> dict:
        return {
            "image_dir": "",
            "output_dir": "cbir_checkpoints",
            "val_split": 0.10,
            "backbone": "clip",
            "embed_dim": 256,
            "proj_layers": 2,
            "freeze_backbone_epochs": 2,
            "image_size": 224,
            "loss_fn": "infonce",
            "temperature": 0.07,
            "triplet_margin": 0.30,
            "jitter_strength": 0.5,
            "epochs": 20,
            "batch_size": 64,
            "lr": 3e-4,
            "backbone_lr_scale": 0.1,
            "warmup_epochs": 2,
            "num_workers": 4,
            "amp": True,
            "ckpt_path": "",
            "index_img_dir": "",
            "index_out_dir": str(Path.home() / ".image-toolkit" / "cbir_index"),
        }
