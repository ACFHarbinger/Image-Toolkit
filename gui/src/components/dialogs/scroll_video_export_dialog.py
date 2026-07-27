from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class ScrollVideoExportDialog(QDialog):
    """
    Collects parameters for `ImageMerger.export_scrolling_video` (roadmap
    §4.2 — Export Stitched Panorama to Scrolling Video, Option B). Kept
    deliberately small: scroll speed, fps, codec, and an optional explicit
    output resolution (unchecked = auto-derive from the panorama, per the
    backend function's own default logic).
    """

    def __init__(self, image_size: Tuple[int, int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export as Scrolling Video")
        img_w, img_h = image_size

        layout = QVBoxLayout(self)
        info = QLabel(
            f"Source panorama: {img_w}x{img_h}px\n"
            "Scroll axis is auto-detected from the aspect ratio "
            "(tall -> vertical, wide -> horizontal)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 2000)
        self.speed_spin.setValue(10)
        self.speed_spin.setSuffix(" px/frame")
        form.addRow("Scroll speed:", self.speed_spin)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        self.fps_spin.setSuffix(" fps")
        form.addRow("Frame rate:", self.fps_spin)

        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["libx264", "libx265", "libvpx-vp9"])
        form.addRow("Video codec:", self.codec_combo)

        self.custom_res_check = QCheckBox("Use custom output resolution")
        form.addRow(self.custom_res_check)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(2, 20000)
        self.width_spin.setValue(min(img_w, 1920))
        self.width_spin.setEnabled(False)
        form.addRow("Width:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(2, 20000)
        self.height_spin.setValue(min(img_h, 1080))
        self.height_spin.setEnabled(False)
        form.addRow("Height:", self.height_spin)

        self.custom_res_check.toggled.connect(self.width_spin.setEnabled)
        self.custom_res_check.toggled.connect(self.height_spin.setEnabled)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict:
        resolution: Optional[Tuple[int, int]] = None
        if self.custom_res_check.isChecked():
            resolution = (self.width_spin.value(), self.height_spin.value())
        return {
            "scroll_speed_px_per_frame": self.speed_spin.value(),
            "fps": self.fps_spin.value(),
            "codec": self.codec_combo.currentText(),
            "resolution": resolution,
        }
