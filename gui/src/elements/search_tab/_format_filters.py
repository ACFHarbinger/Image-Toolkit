"""Input-format filter toggles for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Slot

from ...styles import apply_shadow_effect


class _FormatFiltersMixin:
    """Toggle/add-all/remove-all image-format filter buttons."""

    def toggle_format(self, fmt, checked):
        if checked:
            self.selected_formats.add(fmt)  # pyrefly: ignore [missing-attribute]
            self.format_buttons[fmt].setStyleSheet(
                """
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """
            )
            apply_shadow_effect(
                self.format_buttons[fmt],
                color_hex="#000000",
                radius=8,
                x_offset=0,
                y_offset=3,
            )
        else:
            self.selected_formats.discard(fmt)  # pyrefly: ignore [missing-attribute]
            self.format_buttons[fmt].setStyleSheet(
                "QPushButton:hover { background-color: #3498db; }"
            )
            apply_shadow_effect(
                self.format_buttons[fmt],
                color_hex="#000000",
                radius=8,
                x_offset=0,
                y_offset=3,
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

    def get_selected_formats(self) -> Optional[List[str]]:
        if self.dropdown:
            if not self.selected_formats:
                return None
            return list(self.selected_formats)
        else:
            formats_str = self.input_formats_edit.text().strip()
            if not formats_str:
                return None
            return [
                f.strip().lstrip(".").lower()
                for f in formats_str.replace(",", " ").split()
                if f.strip()
            ]


__all__ = ["_FormatFiltersMixin"]
