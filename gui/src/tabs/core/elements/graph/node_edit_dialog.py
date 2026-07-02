from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QRadioButton, QButtonGroup, QDoubleSpinBox, QDialogButtonBox, QFileDialog,
)

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, SUPPORTED_IMG_FORMATS
from .data import NodeData
from .node_item import is_video


class NodeEditDialog(QDialog):
    """Edit a node's file path, display mode and duration."""

    def __init__(self, nd: NodeData, parent=None):
        super().__init__(parent)
        self.nd = nd
        self.setWindowTitle("Edit Wallpaper Node")
        lyt = QVBoxLayout(self)

        # File path
        fp_row = QHBoxLayout()
        self._path_lbl = QLabel(nd.file_path)
        self._path_lbl.setWordWrap(True)
        fp_row.addWidget(self._path_lbl, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        fp_row.addWidget(btn_browse)
        lyt.addLayout(fp_row)

        # Mode
        mode_grp = QGroupBox("Display Mode")
        mode_lyt = QVBoxLayout(mode_grp)
        self._radio_fixed = QRadioButton("Fixed duration")
        self._radio_runtime = QRadioButton("Video runtime (videos only)")
        self._bg = QButtonGroup(self)
        self._bg.addButton(self._radio_fixed)
        self._bg.addButton(self._radio_runtime)
        mode_lyt.addWidget(self._radio_fixed)
        mode_lyt.addWidget(self._radio_runtime)
        lyt.addWidget(mode_grp)

        if nd.display_mode == "video_runtime":
            self._radio_runtime.setChecked(True)
        else:
            self._radio_fixed.setChecked(True)

        # Duration
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (seconds):"))
        self._dur_spin = QDoubleSpinBox()
        self._dur_spin.setRange(0.5, 86400)
        self._dur_spin.setValue(nd.duration_sec)
        self._dur_spin.setSingleStep(1.0)
        dur_row.addWidget(self._dur_spin)
        lyt.addLayout(dur_row)

        self._radio_fixed.toggled.connect(lambda on: self._dur_spin.setEnabled(on))
        self._dur_spin.setEnabled(nd.display_mode != "video_runtime")

        # Video-runtime only available for videos
        if not is_video(nd.file_path):
            self._radio_runtime.setEnabled(False)
            self._radio_fixed.setChecked(True)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lyt.addWidget(btns)
        self.resize(420, 240)

    def _browse(self):
        all_exts = list(SUPPORTED_VIDEO_FORMATS) + [
            f".{e.lower().lstrip('.')}" for e in SUPPORTED_IMG_FORMATS
        ]
        ext_str = " ".join(f"*{e}" for e in all_exts)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper File", "",
            f"Media Files ({ext_str});;All Files (*)",
        )
        if path:
            self.nd.file_path = path
            self._path_lbl.setText(path)
            if not is_video(path):
                self._radio_runtime.setEnabled(False)
                self._radio_fixed.setChecked(True)
            else:
                self._radio_runtime.setEnabled(True)

    def _save(self):
        self.nd.display_mode = "video_runtime" if self._radio_runtime.isChecked() else "fixed"
        self.nd.duration_sec = self._dur_spin.value()
        self.accept()
