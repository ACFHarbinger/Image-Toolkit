"""Entity Recon and Provenance tab — localized OSINT identity resolution.

A native three-pane QWidget (this app is widget-based, not QML-based):

    Left    source image; click a subject to segment it (SAM 2 → GrabCut
            fallback) or resolve the whole frame
    Center  resolved identity card (name, confidence, method, origin) with
            JSON/CSV provenance export
    Right   provenance trail (local dataset matches or grouped web domains)

Plus a dataset indexer (``/Dataset/FirstName_LastName/image.jpg`` → HNSW
identity index), a Strict Privacy Mode toggle (offline-only), and a batch
dataset builder that auto-sorts dropped images into identity folders.

Heavy work (indexing, segmentation, embedding, resolution) runs in QThread
workers; the C++ ``base.recon`` HNSW index and the torch/SAM models sit behind
graceful fallbacks so the tab stays usable fully offline.
"""

import logging
import os
import subprocess
import sys
import tempfile
from typing import List, Optional

from backend.src.web.recon import (
    ReconConfig,
    ReconEngine,
    export_provenance,
)
from backend.src.web.recon.config import (
    EMBED_CLIP,
    EMBED_FACE,
    SCOPE_BOTH,
    SCOPE_LOCAL,
    SCOPE_WEB,
)
from backend.src.web.recon.provenance import ProvenanceReport
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...helpers.web.recon_worker import (
    BatchSuggestWorker,
    IndexBuildWorker,
    ResolveWorker,
)
from ...styles import apply_shadow_effect

logger = logging.getLogger(__name__)

_DIALOG_OPTS = QFileDialog.Option.DontUseNativeDialog
_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"


class _ClickableImageLabel(QLabel):
    """Displays the source image and reports clicks in *original* image
    coordinates (accounting for the letterboxed scale)."""

    clicked = Signal(int, int)  # x, y in original-image pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 320)
        self.setText("Load an image to begin.")
        self.setStyleSheet("color: #999; border: 1px dashed #4f545c; background: #2c2f33;")
        self._src_w = 0
        self._src_h = 0
        self._scaled_w = 0
        self._scaled_h = 0
        self._off_x = 0
        self._off_y = 0

    def set_source_pixmap(self, pixmap: QPixmap, src_w: int, src_h: int):
        self._src_w, self._src_h = src_w, src_h
        self._rescale(pixmap)

    def _rescale(self, pixmap: QPixmap):
        if pixmap.isNull():
            return
        area = self.size()
        scaled = pixmap.scaled(area, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._scaled_w, self._scaled_h = scaled.width(), scaled.height()
        self._off_x = max(0, (area.width() - self._scaled_w) // 2)
        self._off_y = max(0, (area.height() - self._scaled_h) // 2)
        self.setPixmap(scaled)

    def mousePressEvent(self, event):
        if self._src_w and self._scaled_w and self.pixmap() and not self.pixmap().isNull():
            lx = event.position().x() - self._off_x
            ly = event.position().y() - self._off_y
            if 0 <= lx < self._scaled_w and 0 <= ly < self._scaled_h:
                x = int(lx / self._scaled_w * self._src_w)
                y = int(ly / self._scaled_h * self._src_h)
                self.clicked.emit(x, y)
        super().mousePressEvent(event)


class EntityReconTab(QWidget):
    """Native three-pane Entity Recon and Provenance tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ReconConfig()
        self._engine: Optional[ReconEngine] = None
        self._indexer = None
        self._report: Optional[ProvenanceReport] = None

        self._source_path = ""
        self._source_rgb = None  # np.ndarray (RGB)
        self._cur_alpha = None
        self._cur_bbox = None
        self._batch_rows: List[dict] = []

        self._tmp_dir = os.path.join(tempfile.gettempdir(), "image-toolkit-recon")
        os.makedirs(self._tmp_dir, exist_ok=True)
        self._threads: list = []
        self._warmed_modes: set = set()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str):
        self.status_label.setText(msg)

    def _set_busy(self, busy: bool):
        self.progress.setVisible(busy)
        self.btn_build.setEnabled(not busy)
        self.btn_resolve.setEnabled(not busy)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _on_embed_changed(self, _idx: int):
        self._config.embed_mode = self.embed_combo.currentData()
        if self._engine is not None:
            self._engine.config = self._config

    def _apply_scope(self, scope: str):
        """Push a discovery scope onto the config, keeping the legacy
        ``privacy_mode`` network gate in sync (offline only for local scope)."""
        self._config.search_scope = scope
        self._config.privacy_mode = scope == SCOPE_LOCAL
        if self._engine is not None:
            self._engine.config = self._config

    def _on_scope_changed(self, _idx: int):
        scope = self.scope_combo.currentData()
        self._apply_scope(scope)
        msg = {
            SCOPE_LOCAL: "Search scope: Local only — offline, local index only.",
            SCOPE_WEB: "Search scope: Web only — reverse-image web discovery.",
            SCOPE_BOTH: "Search scope: Local + Web — local first, web fallback.",
        }.get(scope, "Search scope updated.")
        self._set_status(msg)

    # ------------------------------------------------------------------
    # Dataset indexing
    # ------------------------------------------------------------------

    def _browse_dataset(self):
        start = self.dataset_edit.text() if os.path.isdir(self.dataset_edit.text()) else ""
        d = QFileDialog.getExistingDirectory(self, "Select Dataset Root", start, _DIALOG_OPTS)
        if d:
            self.dataset_edit.setText(d)
            self._config.dataset_root = d
            # Default the batch target to the dataset root until the user picks
            # a different destination.
            if not self.target_edit.text().strip():
                self.target_edit.setText(d)

    def _browse_target(self):
        start = self.target_edit.text() if os.path.isdir(self.target_edit.text()) else ""
        d = QFileDialog.getExistingDirectory(self, "Select Target Directory", start, _DIALOG_OPTS)
        if d:
            self.target_edit.setText(d)

    def _build_index(self):
        root_dir = self.dataset_edit.text().strip()
        if not root_dir or not os.path.isdir(root_dir):
            QMessageBox.warning(self, "Invalid Dataset", "Select a valid dataset root directory.")
            return
        self._config.dataset_root = root_dir
        self._set_busy(True)
        self._set_status("Loading embedding model...")
        self._warm_embedder()
        self._set_status("Building identity index...")
        worker = IndexBuildWorker(self._config)
        self._run_worker(worker, self._on_index_built)

    def _on_index_built(self, indexer, stats):
        self._indexer = indexer
        self._engine = ReconEngine(self._config, indexer=indexer)
        self._set_busy(False)
        self._set_status(f"Index ready: {stats.get('indexed', 0)} images, {stats.get('labels', 0)} identities.")

    # ------------------------------------------------------------------
    # Source image + segmentation
    # ------------------------------------------------------------------

    def _browse_source(self):
        start = os.path.dirname(self._source_path) if self._source_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Select Source Image", start, _IMAGE_FILTER, options=_DIALOG_OPTS)
        if path:
            self._load_source(path)

    def _load_source(self, path: str):
        import cv2

        if not path or not os.path.isfile(path):
            return
        img = cv2.imread(path)
        if img is None:
            self._set_status("Could not read image.")
            return
        self._source_path = path
        self._source_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._cur_alpha = None
        self._cur_bbox = None
        h, w = self._source_rgb.shape[:2]
        pix = QPixmap.fromImage(QImage(self._source_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())
        self.image_label.set_source_pixmap(pix, w, h)
        self._set_status(f"Loaded {os.path.basename(path)}. Click a subject to segment.")

    def _on_image_clicked(self, x: int, y: int):
        if self._source_rgb is None:
            return
        from backend.src.web.recon import segmenter

        try:
            alpha, bbox = segmenter.segment_at_point(self._source_rgb, x, y)
        except Exception as e:  # noqa: BLE001 - segmentation is best-effort
            logger.warning("Segmentation failed: %s", e)
            self._set_status(f"Segmentation failed: {e}")
            return
        self._cur_alpha = alpha
        self._cur_bbox = bbox
        self._show_overlay(alpha)
        self._set_status("Subject selected. Press 'Resolve Identity'.")

    def _show_overlay(self, alpha):
        import numpy as np

        overlay = self._source_rgb.copy()  # pyrefly: ignore [missing-attribute]
        mask = alpha > 0
        tint = np.zeros_like(overlay)
        tint[mask] = (88, 101, 242)
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * tint[mask]).astype(np.uint8)
        h, w = overlay.shape[:2]
        pix = QPixmap.fromImage(QImage(overlay.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())
        self.image_label.set_source_pixmap(pix, w, h)

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    def _resolve(self):
        if self._source_rgb is None:
            self._set_status("Load an image first.")
            return
        if self._engine is None:
            QMessageBox.information(self, "No Index", "Build the identity index first.")
            return
        from backend.src.web.recon import segmenter

        if self._cur_alpha is not None:
            cutout = segmenter.alpha_cutout(self._source_rgb, self._cur_alpha)
        else:
            # whole-frame fallback: opaque alpha
            import numpy as np

            full = np.full(self._source_rgb.shape[:2], 255, dtype=np.uint8)
            cutout = segmenter.alpha_cutout(self._source_rgb, full)
        cutout_rgb = cutout[:, :, :3]
        png = segmenter.cutout_to_png_bytes(cutout)

        self._set_busy(True)
        # Local/both scopes embed the cutout; warm the model on the main thread
        # first (web-only skips embedding, so no need to load torch).
        if getattr(self._config, "search_scope", SCOPE_LOCAL) in (SCOPE_LOCAL, SCOPE_BOTH):
            self._set_status("Loading embedding model...")
            self._warm_embedder()
        self._set_status("Resolving identity...")
        worker = ResolveWorker(self._engine, cutout_rgb, png)
        self._run_worker(worker, self._on_resolved)

    def _on_resolved(self, res):
        self._set_busy(False)
        self._report = res.report
        self.name_label.setText(res.name or "Unknown")
        self.conf_bar.setValue(int(round(res.confidence * 100)))
        self.method_label.setText(f"Method: {res.method or '—'}")
        self.origin_label.setText(f"Origin: {res.origin or 'none'}")

        self.prov_tree.clear()
        if res.origin == "local":
            for m in res.local_matches:
                item = QTreeWidgetItem([m["label"].replace("_", " "), f"{m['score'] * 100:.0f}%"])
                item.setData(0, Qt.ItemDataRole.UserRole, ("local", m["path"]))
                child = QTreeWidgetItem([m["path"], ""])
                child.setData(0, Qt.ItemDataRole.UserRole, ("local", m["path"]))
                item.addChild(child)
                self.prov_tree.addTopLevelItem(item)
        else:
            for d in res.web_domains:
                parent = QTreeWidgetItem([f"{d['domain']} ({d['count']})", ""])
                for url in d.get("urls", []):
                    child = QTreeWidgetItem([url, ""])
                    child.setData(0, Qt.ItemDataRole.UserRole, ("web", url))
                    parent.addChild(child)
                self.prov_tree.addTopLevelItem(parent)
        self.prov_tree.expandAll()
        self._set_status(f"Identity: {res.name or 'Unknown'} ({res.confidence * 100:.0f}%) via {res.method or '—'}")

    def _on_prov_activated(self, item: QTreeWidgetItem, _col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, target = data
        if kind == "web":
            QDesktopServices.openUrl(QUrl(target))
        else:
            self._open_in_file_manager(target)

    def _open_in_file_manager(self, path: str):
        if not path:
            return
        directory = path if os.path.isdir(path) else os.path.dirname(path)
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", directory])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", directory])
            elif sys.platform.startswith("win"):
                os.startfile(directory)  # noqa: S606
        except Exception as e:  # noqa: BLE001
            logger.warning("open_in_file_manager failed: %s", e)

    # ------------------------------------------------------------------
    # Provenance export
    # ------------------------------------------------------------------

    def _export(self, fmt: str):
        if self._report is None:
            self._set_status("Nothing to export yet.")
            return
        ext = "csv" if fmt == "csv" else "json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Provenance", f"provenance.{ext}", f"{ext.upper()} (*.{ext})", options=_DIALOG_OPTS
        )
        if not path:
            return
        try:
            export_provenance(self._report, path, fmt=ext)
            self._set_status(f"Exported provenance to {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", str(e))

    # ------------------------------------------------------------------
    # Batch dataset builder
    # ------------------------------------------------------------------

    def _browse_batch(self):
        if self._engine is None:
            QMessageBox.information(self, "No Index", "Build the identity index first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", _IMAGE_FILTER, options=_DIALOG_OPTS)
        paths = [p for p in paths if os.path.isfile(p)]
        if not paths:
            return
        self._set_busy(True)
        self._set_status("Loading embedding model...")
        self._warm_embedder()
        self._set_status(f"Analyzing {len(paths)} images...")
        worker = BatchSuggestWorker(self._engine, paths)
        self._run_worker(worker, self._on_batch)

    def _on_batch(self, suggestions):
        self._set_busy(False)
        self._batch_rows = suggestions
        self.batch_table.setRowCount(len(suggestions))
        for row, s in enumerate(suggestions):
            self.batch_table.setItem(row, 0, QTableWidgetItem(os.path.basename(s.get("path", ""))))
            self.batch_table.setItem(row, 1, QTableWidgetItem((s.get("suggested_label") or "—").replace("_", " ")))
            self.batch_table.setItem(row, 2, QTableWidgetItem(f"{s.get('score', 0.0) * 100:.0f}%"))
        matched = sum(1 for s in suggestions if s.get("suggested_label"))
        self.btn_approve.setEnabled(matched > 0)
        self._set_status(f"{matched}/{len(suggestions)} images matched an identity.")

    def _approve_batch(self):
        import shutil

        # A user-specified target root overrides the per-row default (which puts
        # identity folders next to each source image).
        target_root = self.target_edit.text().strip()
        moved = 0
        for row in self._batch_rows:
            path = row.get("path")
            label = row.get("suggested_label")
            target = os.path.join(target_root, label) if target_root and label else row.get("target_dir")
            if not target or not path or not os.path.isfile(path):
                continue
            try:
                os.makedirs(target, exist_ok=True)
                dest = os.path.join(target, os.path.basename(path))
                if os.path.abspath(dest) != os.path.abspath(path):
                    shutil.move(path, dest)
                    moved += 1
            except OSError as e:
                logger.warning("Batch move failed for %s: %s", path, e)
        self._batch_rows = []
        self.batch_table.setRowCount(0)
        self.btn_approve.setEnabled(False)
        self._set_status(f"Moved {moved} images into identity folders.")

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------

    def _warm_embedder(self) -> None:
        """Force the heavy embedding model to load on the MAIN thread once.

        torch / InsightFace lazily ``dlopen`` their native libraries on first
        use. Doing that first-time load inside a worker ``QThread`` while the
        JPype JVM is live triggers a heap-corruption crash ("corrupted size vs.
        prev_size", QSocketNotifier-from-another-thread) — the documented
        JVM + lazily-loaded-native-lib conflict. Warming here loads those libs
        on the main thread; subsequent worker-thread inference is then safe."""
        mode = self._config.embed_mode
        if mode in self._warmed_modes:
            return
        try:
            import numpy as np
            from backend.src.web.recon.embedder import embed

            embed(np.zeros((64, 64, 3), dtype=np.uint8), mode)
        except Exception as e:  # noqa: BLE001 - warm-up is best-effort
            logger.warning("Embedder warm-up failed for %s: %s", mode, e)
        finally:
            # Mark warmed regardless: a failed load won't succeed off-thread
            # either, and we must not retry it inside a worker.
            self._warmed_modes.add(mode)

    def _run_worker(self, worker, on_finished):
        # Workers are QThread subclasses (override run(), no event loop). A plain
        # QThread + moveToThread spins a glib socket-notifier event dispatcher in
        # the worker thread which SIGSEGVs under the live JVM.
        worker.status.connect(self._set_status)
        worker.sig_finished.connect(on_finished)
        worker.sig_finished.connect(lambda *_: self._reap_worker(worker))
        worker.error.connect(self._on_worker_error)
        worker.error.connect(lambda *_: self._reap_worker(worker))
        self._threads.append(worker)
        worker.start()

    def _reap_worker(self, worker):
        if worker in self._threads:
            self._threads.remove(worker)
        worker.wait(5000)
        worker.deleteLater()

    def _on_worker_error(self, message: str):
        self._set_busy(False)
        self._set_status(f"Error: {message}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cancel_loading(self):
        for t in list(self._threads):
            try:
                t.requestInterruption()
                t.quit()
                t.wait(2000)
            except Exception:  # noqa: BLE001
                pass
        self._threads.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)
