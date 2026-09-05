"""Reusable Thumbnail Zoom Control component (§2.2)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from gui.src.windows.settings.thumbnail_size import load_thumbnail_size, save_thumbnail_size


class ThumbnailZoomControl(QWidget):
    """Toolbar/Header widget combining a size slider, S/M/L/XL preset buttons, and live px readout."""

    size_changed = Signal(int)

    PRESETS = {
        "S": 96,
        "M": 160,
        "L": 240,
        "XL": 384,
    }

    def __init__(
        self,
        class_name: Optional[str] = None,
        parent: Optional[QWidget] = None,
        initial_size: Optional[int] = None,
        min_size: int = 48,
        max_size: int = 512,
        step: int = 16,
    ) -> None:
        super().__init__(parent)
        self.class_name = class_name
        self.min_size = min_size
        self.max_size = max_size
        self.step = step

        if initial_size is not None:
            self._current_size = max(min_size, min(max_size, initial_size))
        elif class_name:
            self._current_size = load_thumbnail_size(class_name, default=180)
        else:
            self._current_size = 180

        self._preset_buttons: dict[str, QPushButton] = {}
        self._build_ui()
        self.set_size(self._current_size, save=False)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        icon_lbl = QLabel("⊞")
        icon_lbl.setStyleSheet("color: #888; font-weight: bold;")
        layout.addWidget(icon_lbl)

        # Preset buttons (§2.2 Option C)
        for label, px in self.PRESETS.items():
            btn = QPushButton(label)
            btn.setFixedWidth(24 if len(label) == 1 else 28)
            btn.setFixedHeight(22)
            btn.setToolTip(f"{label} ({px} px)")
            btn.setStyleSheet(
                "QPushButton { padding: 1px 3px; font-size: 8pt; font-weight: bold; border-radius: 3px; }"
                "QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }"
            )
            btn.clicked.connect(lambda _=False, target_px=px: self._on_preset_clicked(target_px))
            self._preset_buttons[label] = btn
            layout.addWidget(btn)

        # Slider (§2.2 Option A)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(self.min_size, self.max_size)
        self.slider.setSingleStep(self.step)
        self.slider.setPageStep(self.step * 2)
        self.slider.setValue(self._current_size)
        self.slider.setFixedWidth(100)
        self.slider.setToolTip(f"Thumbnail size ({self.min_size}–{self.max_size} px)")
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        self.slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self.slider)

        # Size label
        self.lbl_size = QLabel(f"{self._current_size} px", self)
        self.lbl_size.setMinimumWidth(44)
        self.lbl_size.setStyleSheet("font-size: 8pt; color: #aaa;")
        layout.addWidget(self.lbl_size)

    @property
    def current_size(self) -> int:
        return self._current_size

    def _on_preset_clicked(self, px: int) -> None:
        self.set_size(px, save=True)
        self.size_changed.emit(self._current_size)

    def _on_slider_value_changed(self, value: int) -> None:
        snapped = max(self.min_size, min(self.max_size, (value // self.step) * self.step))
        if snapped == self._current_size:
            return
        self._current_size = snapped
        self.lbl_size.setText(f"{snapped} px")
        self._highlight_active_preset()
        self.size_changed.emit(snapped)

    def _on_slider_released(self) -> None:
        if self.class_name:
            save_thumbnail_size(self.class_name, self._current_size)

    def set_size(self, size: int, save: bool = True) -> None:
        snapped = max(self.min_size, min(self.max_size, (size // self.step) * self.step))
        self._current_size = snapped
        self.slider.blockSignals(True)
        self.slider.setValue(snapped)
        self.slider.blockSignals(False)
        self.lbl_size.setText(f"{snapped} px")
        self._highlight_active_preset()
        if save and self.class_name:
            save_thumbnail_size(self.class_name, snapped)

    def step_zoom(self, delta_steps: int) -> int:
        """Step zoom size by delta_steps (+1 = +step, -1 = -step) (§2.2 Option B)."""
        new_size = max(self.min_size, min(self.max_size, self._current_size + (delta_steps * self.step)))
        if new_size != self._current_size:
            self.set_size(new_size, save=True)
            self.size_changed.emit(new_size)
        return self._current_size

    def _highlight_active_preset(self) -> None:
        for label, px in self.PRESETS.items():
            btn = self._preset_buttons.get(label)
            if btn is not None:
                if self._current_size == px:
                    btn.setStyleSheet(
                        "QPushButton { padding: 1px 3px; font-size: 8pt; font-weight: bold; border-radius: 3px; "
                        "background-color: #5865F2; color: white; }"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { padding: 1px 3px; font-size: 8pt; font-weight: bold; border-radius: 3px; }"
                        "QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }"
                    )


__all__ = ["ThumbnailZoomControl"]
