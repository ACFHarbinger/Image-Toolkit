"""
gui/src/components/safetensors_inspector.py
===========================================
Read-only dialog that displays the metadata, tensor summary, and layer tree
of a .safetensors file without loading any tensor data.

Usage
-----
    from gui.src.components.dialogs.safetensors_inspector import SafetensorsInspectorDialog
    dlg = SafetensorsInspectorDialog(path="/path/to/model.safetensors", parent=self)
    dlg.exec()
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    pass


class _LoadSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class _LoadWorker(QRunnable):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.signals = _LoadSignals()

    def run(self) -> None:
        try:
            from backend.src.utils.data.safetensors_metadata import read_metadata
            data = read_metadata(self.path)
            self.signals.finished.emit(data)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class SafetensorsInspectorDialog(QDialog):
    """Modal dialog showing safetensors file metadata and tensor summary."""

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.setWindowTitle(f"Inspect Model — {os.path.basename(path)}")
        self.setMinimumSize(720, 540)
        self.resize(860, 640)
        self._build_ui()
        self._start_load()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # --- path bar ---
        path_lbl = QLabel(self.path)
        path_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_lbl.setWordWrap(True)
        monofont = QFont("Monospace")
        monofont.setStyleHint(QFont.StyleHint.TypeWriter)
        path_lbl.setFont(monofont)
        root.addWidget(path_lbl)

        # --- progress bar (shown while loading) ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        # --- main splitter: summary | tensor tree ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # left: summary + user metadata
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        summary_box = QGroupBox("Summary")
        self._summary_tree = QTreeWidget()
        self._summary_tree.setHeaderLabels(["Field", "Value"])
        self._summary_tree.setRootIsDecorated(False)
        self._summary_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._summary_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._summary_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        sb_lay = QVBoxLayout(summary_box)
        sb_lay.addWidget(self._summary_tree)
        left_layout.addWidget(summary_box)

        meta_box = QGroupBox("User Metadata")
        self._meta_tree = QTreeWidget()
        self._meta_tree.setHeaderLabels(["Key", "Value"])
        self._meta_tree.setRootIsDecorated(False)
        self._meta_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._meta_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._meta_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        mb_lay = QVBoxLayout(meta_box)
        mb_lay.addWidget(self._meta_tree)
        left_layout.addWidget(meta_box, stretch=1)

        splitter.addWidget(left_widget)

        # right: tensor layer tree
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        layers_box = QGroupBox("Tensors")
        self._tensor_tree = QTreeWidget()
        self._tensor_tree.setHeaderLabels(["Name", "Shape", "Dtype"])
        self._tensor_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tensor_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tensor_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tensor_tree.setSortingEnabled(True)
        lb_lay = QVBoxLayout(layers_box)
        lb_lay.addWidget(self._tensor_tree)
        right_layout.addWidget(layers_box)
        splitter.addWidget(right_widget)

        splitter.setSizes([320, 540])

        # --- bottom button row ---
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy Metadata")
        copy_btn.clicked.connect(self._copy_metadata)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._copy_btn = copy_btn
        self._copy_btn.setEnabled(False)
        self._raw_data: dict = {}

    # ------------------------------------------------------------------
    # Background load
    # ------------------------------------------------------------------

    def _start_load(self) -> None:
        worker = _LoadWorker(self.path)
        worker.signals.finished.connect(self._on_loaded)
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(dict)
    def _on_loaded(self, data: dict) -> None:
        self._progress.hide()
        self._raw_data = data
        self._populate(data)
        self._copy_btn.setEnabled(True)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._progress.hide()
        item = QTreeWidgetItem(["Error", msg])
        item.setForeground(0, Qt.GlobalColor.red)
        item.setForeground(1, Qt.GlobalColor.red)
        self._summary_tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # Populate trees
    # ------------------------------------------------------------------

    def _populate(self, data: dict) -> None:
        size_mb = data.get("file_size_mb", 0.0)
        n_tensors = data.get("tensor_count", 0)
        n_params = data.get("param_count", 0)
        dtype_counts: dict = data.get("dtype_counts", {})

        # format param count
        if n_params >= 1_000_000_000:
            param_str = f"{n_params / 1e9:.2f} B"
        elif n_params >= 1_000_000:
            param_str = f"{n_params / 1e6:.2f} M"
        else:
            param_str = f"{n_params:,}"

        summary_rows = [
            ("File", os.path.basename(self.path)),
            ("Size", f"{size_mb:.1f} MB"),
            ("Tensors", str(n_tensors)),
            ("Parameters", param_str),
        ]
        if dtype_counts:
            for dtype, count in sorted(dtype_counts.items()):
                summary_rows.append((f"  dtype:{dtype}", f"{count} tensors"))

        for key, val in summary_rows:
            QTreeWidgetItem(self._summary_tree, [key, val])

        # user metadata
        user_meta: dict = data.get("user_meta", {})
        for key in sorted(user_meta):
            val = user_meta[key]
            # skip base64 preview blobs
            if isinstance(val, str) and val.startswith("data:image/"):
                val = f"<base64 image, {len(val)} chars>"
            QTreeWidgetItem(self._meta_tree, [key, str(val)])
        if not user_meta:
            QTreeWidgetItem(self._meta_tree, ["(none)", ""])

        # tensor tree
        tensors: dict = data.get("tensors", {})
        for name in sorted(tensors):
            info = tensors[name]
            shape_str = "×".join(str(d) for d in info["shape"])
            QTreeWidgetItem(self._tensor_tree, [name, shape_str, info["dtype"]])

        self._summary_tree.resizeColumnToContents(0)
        self._meta_tree.resizeColumnToContents(0)
        self._tensor_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _copy_metadata(self) -> None:
        lines = []
        data = self._raw_data
        lines.append(f"File: {self.path}")
        lines.append(f"Size: {data.get('file_size_mb', 0):.1f} MB")
        lines.append(f"Tensors: {data.get('tensor_count', 0)}")
        lines.append(f"Parameters: {data.get('param_count', 0):,}")
        lines.append("")
        user_meta = data.get("user_meta", {})
        if user_meta:
            lines.append("User Metadata:")
            for k, v in sorted(user_meta.items()):
                if isinstance(v, str) and v.startswith("data:image/"):
                    v = "<base64 image>"
                lines.append(f"  {k}: {v}")
        QApplication.clipboard().setText("\n".join(lines))
