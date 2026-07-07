"""Entity Recon & Provenance tab backend.

Orchestrates the localized OSINT pipeline for the three-pane QML UI:
    Left    source image + SAM hover masking / manual bounding box
    Center  resolved identity card (name, confidence ring, method/origin)
    Right   provenance trail (local file paths or grouped web domains)

Heavy work runs in QThread workers; the C++ ``base.recon`` HNSW index and the
Python SAM 2 / embedding / NER models sit behind graceful fallbacks so the tab
is usable even fully offline (Strict Privacy Mode).
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
from backend.src.web.recon.provenance import ProvenanceReport
from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QObject,
    Qt,
    QThread,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from ...helpers.web.recon_worker import (
    BatchSuggestWorker,
    IndexBuildWorker,
    ResolveWorker,
)

logger = logging.getLogger(__name__)


class ProvenanceModel(QAbstractListModel):
    """Flat list of provenance rows (local paths or grouped web domains)."""

    KindRole = Qt.ItemDataRole.UserRole + 1
    LabelRole = Qt.ItemDataRole.UserRole + 2
    SourceRole = Qt.ItemDataRole.UserRole + 3
    DomainRole = Qt.ItemDataRole.UserRole + 4
    ScoreRole = Qt.ItemDataRole.UserRole + 5
    CountRole = Qt.ItemDataRole.UserRole + 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[dict] = []

    def roleNames(self):
        return {
            self.KindRole: QByteArray(b"kind"),
            self.LabelRole: QByteArray(b"label"),
            self.SourceRole: QByteArray(b"source"),
            self.DomainRole: QByteArray(b"domain"),
            self.ScoreRole: QByteArray(b"score"),
            self.CountRole: QByteArray(b"matchCount"),
        }

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        return {
            self.KindRole: row.get("kind", ""),
            self.LabelRole: row.get("label", ""),
            self.SourceRole: row.get("source", ""),
            self.DomainRole: row.get("domain", ""),
            self.ScoreRole: row.get("score", 0.0),
            self.CountRole: row.get("count", 1),
        }.get(role)

    def set_rows(self, rows: List[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class BatchModel(QAbstractListModel):
    """Suggested bulk renames/moves for the Dataset Builder dropzone."""

    PathRole = Qt.ItemDataRole.UserRole + 1
    LabelRole = Qt.ItemDataRole.UserRole + 2
    ScoreRole = Qt.ItemDataRole.UserRole + 3
    TargetRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[dict] = []

    def roleNames(self):
        return {
            self.PathRole: QByteArray(b"path"),
            self.LabelRole: QByteArray(b"suggestedLabel"),
            self.ScoreRole: QByteArray(b"score"),
            self.TargetRole: QByteArray(b"targetDir"),
        }

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        return {
            self.PathRole: row.get("path", ""),
            self.LabelRole: row.get("suggested_label", ""),
            self.ScoreRole: row.get("score", 0.0),
            self.TargetRole: row.get("target_dir", ""),
        }.get(role)

    def set_rows(self, rows: List[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self) -> List[dict]:
        return self._rows


class EntityReconTab(QObject):
    # identity card
    identity_changed = Signal()
    # source pane
    source_changed = Signal(str)
    mask_ready = Signal(str)          # translucent overlay PNG for hover render
    # lifecycle / status
    status_changed = Signal(str)
    index_ready = Signal(int, int)    # images, labels
    busy_changed = Signal(bool)
    privacy_changed = Signal(bool)
    batch_changed = Signal()

    def __init__(self):
        super().__init__()
        self._config = ReconConfig()
        self._engine: Optional[ReconEngine] = None
        self._indexer = None
        self._provenance_model = ProvenanceModel(self)
        self._batch_model = BatchModel(self)
        self._report: Optional[ProvenanceReport] = None

        self._source_path = ""
        self._source_rgb = None       # np.ndarray (RGB)
        self._cur_alpha = None
        self._cur_bbox = None

        self._name = ""
        self._confidence = 0.0
        self._method = ""
        self._origin = "none"
        self._busy = False

        self._tmp_dir = os.path.join(tempfile.gettempdir(), "image-toolkit-recon")
        os.makedirs(self._tmp_dir, exist_ok=True)

        self._threads: list = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @Property(QAbstractListModel, constant=True)
    def provenanceModel(self):
        return self._provenance_model

    @Property(QAbstractListModel, constant=True)
    def batchModel(self):
        return self._batch_model

    def _get_name(self):
        return self._name

    identityName = Property(str, _get_name, notify=identity_changed)

    def _get_conf(self):
        return self._confidence

    identityConfidence = Property(float, _get_conf, notify=identity_changed)

    def _get_method(self):
        return self._method

    identityMethod = Property(str, _get_method, notify=identity_changed)

    def _get_origin(self):
        return self._origin

    identityOrigin = Property(str, _get_origin, notify=identity_changed)

    def _get_privacy(self):
        return self._config.privacy_mode

    def _set_privacy(self, value: bool):
        self.set_privacy_mode(value)

    privacyMode = Property(bool, _get_privacy, _set_privacy, notify=privacy_changed)

    def _get_busy(self):
        return self._busy

    busy = Property(bool, _get_busy, notify=busy_changed)

    def _set_busy(self, value: bool):
        if self._busy != value:
            self._busy = value
            self.busy_changed.emit(value)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @Slot("QVariantMap")
    def set_recon_settings(self, values: dict):
        data = self._config.to_dict()
        for k, v in dict(values).items():
            if k in data:
                data[k] = v
        self._config = ReconConfig.from_dict(data)
        if self._engine is not None:
            self._engine.config = self._config

    @Slot(result="QVariantMap")
    def get_recon_settings(self):
        return self._config.to_dict()

    @Slot(bool)
    def set_privacy_mode(self, value: bool):
        value = bool(value)
        if self._config.privacy_mode != value:
            self._config.privacy_mode = value
            if self._engine is not None:
                self._engine.config = self._config
            self.privacy_changed.emit(value)
            self.status_changed.emit(
                "Privacy mode ON — offline only." if value
                else "Privacy mode OFF — web discovery enabled.")

    # ------------------------------------------------------------------
    # Dataset indexing
    # ------------------------------------------------------------------

    @Slot(str, result=str)
    def browse_dataset_qml(self, current=""):
        start = current if os.path.isdir(current) else ""
        d = QFileDialog.getExistingDirectory(None, "Select Dataset Root", start)
        if d:
            self._config.dataset_root = d
            return d
        return ""

    @Slot(str)
    def build_index(self, dataset_root=""):
        if dataset_root:
            self._config.dataset_root = dataset_root
        if not self._config.dataset_root or not os.path.isdir(self._config.dataset_root):
            self.status_changed.emit("Invalid dataset root.")
            return
        self._set_busy(True)
        self.status_changed.emit("Building identity index...")
        thread = QThread()
        worker = IndexBuildWorker(self._config)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.status_changed)
        worker.finished.connect(self._on_index_built)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._threads.remove(t) if t in self._threads else None)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    @Slot(object, dict)
    def _on_index_built(self, indexer, stats):
        self._indexer = indexer
        self._engine = ReconEngine(self._config, indexer=indexer)
        self._set_busy(False)
        self.index_ready.emit(stats.get("indexed", 0), stats.get("labels", 0))
        self.status_changed.emit(
            f"Index ready: {stats.get('indexed', 0)} images, "
            f"{stats.get('labels', 0)} identities.")

    # ------------------------------------------------------------------
    # Source image + segmentation
    # ------------------------------------------------------------------

    @Slot(str, result=str)
    def browse_source_qml(self, current=""):
        start = current if os.path.isdir(os.path.dirname(current)) else ""
        path, _ = QFileDialog.getOpenFileName(
            None, "Select Source Image", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.load_source(path)
            return path
        return ""

    @Slot(str)
    def load_source(self, path: str):
        import cv2

        if not path or not os.path.isfile(path):
            return
        img = cv2.imread(path)
        if img is None:
            self.status_changed.emit("Could not read image.")
            return
        self._source_path = path
        self._source_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._cur_alpha = None
        self._cur_bbox = None
        self.source_changed.emit(path)
        self.status_changed.emit(f"Loaded {os.path.basename(path)}.")

    @Slot(int, int, result=str)
    def segment_at(self, x: int, y: int) -> str:
        """Segment the subject under (x, y) and render a translucent overlay
        for hover feedback. Returns the overlay PNG path."""
        if self._source_rgb is None:
            return ""
        from backend.src.web.recon import segmenter

        h, w = self._source_rgb.shape[:2]
        x = max(0, min(w - 1, int(x)))
        y = max(0, min(h - 1, int(y)))
        alpha, bbox = segmenter.segment_at_point(self._source_rgb, x, y)
        self._cur_alpha = alpha
        self._cur_bbox = bbox
        return self._render_overlay(alpha)

    @Slot(int, int, int, int, result=str)
    def segment_bbox(self, x0: int, y0: int, x1: int, y1: int) -> str:
        """Manual fallback: use a bounding box as the subject."""
        if self._source_rgb is None:
            return ""
        from backend.src.web.recon import segmenter

        alpha, bbox = segmenter.segment_bbox(self._source_rgb, (x0, y0, x1, y1))
        self._cur_alpha = alpha
        self._cur_bbox = bbox
        return self._render_overlay(alpha)

    def _render_overlay(self, alpha) -> str:
        import cv2
        import numpy as np

        overlay = cv2.cvtColor(self._source_rgb, cv2.COLOR_RGB2RGBA)
        tint = np.zeros_like(overlay)
        tint[alpha > 0] = (88, 101, 242, 130)   # translucent accent (RGBA)
        mask = alpha > 0
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * tint[mask]).astype(np.uint8)
        overlay[~mask, 3] = 255
        out = os.path.join(self._tmp_dir, "mask_overlay.png")
        cv2.imwrite(out, cv2.cvtColor(overlay, cv2.COLOR_RGBA2BGRA))
        self.mask_ready.emit(out)
        return out

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    @Slot()
    def confirm_extract(self):
        """Confirm the current mask/bbox as the subject and resolve identity."""
        if self._source_rgb is None or self._cur_alpha is None:
            self.status_changed.emit("Hover and click a subject first.")
            return
        if self._engine is None:
            self.status_changed.emit("Build the identity index first.")
            return
        from backend.src.web.recon import segmenter

        cutout = segmenter.alpha_cutout(self._source_rgb, self._cur_alpha)
        cutout_rgb = cutout[:, :, :3]
        png = segmenter.cutout_to_png_bytes(cutout)

        self._set_busy(True)
        thread = QThread()
        worker = ResolveWorker(self._engine, cutout_rgb, png)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.status_changed)
        worker.finished.connect(self._on_resolved)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._threads.remove(t) if t in self._threads else None)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    @Slot(object)
    def _on_resolved(self, res):
        self._set_busy(False)
        self._name = res.name or "Unknown"
        self._confidence = res.confidence
        self._method = res.method
        self._origin = res.origin
        self._report = res.report
        self.identity_changed.emit()

        rows: List[dict] = []
        if res.origin == "local":
            for m in res.local_matches:
                rows.append({"kind": "local", "label": m["label"].replace("_", " "),
                             "source": m["path"], "score": m["score"]})
        else:
            for d in res.web_domains:
                rows.append({"kind": "web", "label": self._name, "domain": d["domain"],
                             "source": d["urls"][0] if d["urls"] else "",
                             "count": d["count"], "score": self._confidence})
        self._provenance_model.set_rows(rows)
        self.status_changed.emit(
            f"Identity: {self._name} ({self._confidence * 100:.0f}%) via {self._method}")

    # ------------------------------------------------------------------
    # Provenance export
    # ------------------------------------------------------------------

    @Slot(str, result=str)
    def export_report_qml(self, fmt="json"):
        if self._report is None:
            self.status_changed.emit("Nothing to export yet.")
            return ""
        ext = "csv" if fmt == "csv" else "json"
        path, _ = QFileDialog.getSaveFileName(
            None, "Export Provenance", f"provenance.{ext}",
            f"{ext.upper()} (*.{ext})")
        if not path:
            return ""
        try:
            export_provenance(self._report, path, fmt=ext)
            self.status_changed.emit(f"Exported provenance to {path}")
            return path
        except Exception as e:
            self.status_changed.emit(f"Export failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # Batch dataset builder
    # ------------------------------------------------------------------

    @Slot("QStringList")
    def drop_batch(self, urls: List[str]):
        if self._engine is None:
            self.status_changed.emit("Build the identity index first.")
            return
        paths = []
        for u in urls:
            p = QUrl(u).toLocalFile() if u.startswith("file:") else u
            if os.path.isfile(p):
                paths.append(p)
        if not paths:
            self.status_changed.emit("No valid image files dropped.")
            return
        self._set_busy(True)
        thread = QThread()
        worker = BatchSuggestWorker(self._engine, paths)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self.status_changed)
        worker.finished.connect(self._on_batch)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._threads.remove(t) if t in self._threads else None)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    @Slot(list)
    def _on_batch(self, suggestions):
        self._set_busy(False)
        self._batch_model.set_rows(suggestions)
        self.batch_changed.emit()
        n = sum(1 for s in suggestions if s.get("suggested_label"))
        self.status_changed.emit(f"{n}/{len(suggestions)} images matched an identity.")

    @Slot(result=int)
    def approve_all_batch(self) -> int:
        """Move each matched image into its suggested FirstName_LastName folder."""
        import shutil

        moved = 0
        for row in self._batch_model.rows():
            target = row.get("target_dir")
            path = row.get("path")
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
        self.status_changed.emit(f"Moved {moved} images into identity folders.")
        self._batch_model.set_rows([])
        self.batch_changed.emit()
        return moved

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    @Slot(str)
    def open_in_file_manager(self, path: str):
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
        except Exception as e:
            logger.warning("open_in_file_manager failed: %s", e)

    @Slot(str)
    def open_url(self, url: str):
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cancel_loading(self):
        for t in list(self._threads):
            try:
                t.requestInterruption()
                t.quit()
                t.wait(2000)
            except Exception:
                pass
        self._threads.clear()

    @Slot(str)
    def _on_worker_error(self, message: str):
        self._set_busy(False)
        self.status_changed.emit(f"Error: {message}")
