"""Input-format toggle buttons (add/toggle/remove).

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QPushButton

from .....styles import apply_shadow_effect


class _FormatButtonsMixin:
    """Manages the per-format toggle buttons and their checked/unchecked style."""

    def _add_format_button(self, fmt, layout):
        btn = QPushButton(fmt)
        btn.setCheckable(True)
        btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
        apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn.clicked.connect(lambda checked, f=fmt: self.toggle_format(f, checked))
        layout.addWidget(btn)
        self.format_buttons[fmt] = btn

    @Slot(str)
    def on_output_format_changed(self, text: str):
        text = text.lower()
        vid_formats = [f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS]
        is_video = text in vid_formats or "videos" in text

        # 1. Toggle Engine Visibility
        self.engine_combo.setVisible(is_video)
        self.engine_label.setVisible(is_video)

        # 2. Update Input Formats Buttons (only if dropdown mode)
        if self.dropdown and hasattr(self, "format_btn_layout"):
            # Clear existing
            for btn in self.format_buttons.values():
                self.format_btn_layout.removeWidget(btn)
                btn.deleteLater()

            self.format_buttons.clear()
            self.selected_formats.clear()  # pyrefly: ignore [missing-attribute]

            # Populate new
            target_formats = (
                SUPPORTED_VIDEO_FORMATS if is_video else SUPPORTED_IMG_FORMATS
            )
            # Helper to strip dots if needed, though IMG_FORMATS usually has no dots in definitions?
            # definitions.py: SUPPORTED_IMG_FORMATS = ["webp", ...] (no dots)
            # definitions.py: SUPPORTED_VIDEO_FORMATS = {".mp4", ...} (has dots)

            clean_formats = []
            clean_formats = sorted([f.lstrip(".") for f in target_formats]) if is_video else target_formats

            for fmt in clean_formats:
                self._add_format_button(fmt, self.format_btn_layout)

    @Slot(str, bool)
    def toggle_format(self, fmt, checked):
        btn = self.format_buttons[fmt]
        if checked:
            self.selected_formats.add(fmt) # pyrefly: ignore [missing-attribute]
            btn.setStyleSheet(
                """
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """
            )
            apply_shadow_effect(
                btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )
        else:
            self.selected_formats.discard(fmt) # pyrefly: ignore [missing-attribute]
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(
                btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )

    @Slot()
    def add_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(True)
            self.toggle_format(fmt, True)

    @Slot()
    def remove_all_formats(self):
        for fmt, btn in self.format_buttons.items():
            btn.setChecked(False)
            self.toggle_format(fmt, False)


__all__ = ["_FormatButtonsMixin"]
