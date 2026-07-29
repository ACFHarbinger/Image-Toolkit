"""Source-codec filter toggle buttons.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Set

from PySide6.QtWidgets import QPushButton

from .....styles import apply_shadow_effect


class _CodecFiltersMixin:
    """Builds and toggles the source-codec filter buttons."""

    def _add_codec_filter_button(self, codec: str, layout, button_map: dict, selection_set: Set[str]):
        btn = QPushButton(codec)
        btn.setCheckable(True)
        btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
        apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn.clicked.connect(
            lambda checked, c=codec, m=button_map, s=selection_set: self._toggle_codec_filter(
                c, checked, m, s
            )
        )
        layout.addWidget(btn)
        button_map[codec] = btn

    def _toggle_codec_filter(self, codec: str, checked: bool, button_map: dict, selection_set: Set[str]):
        btn = button_map[codec]
        if checked:
            selection_set.add(codec)
            btn.setStyleSheet(
                """
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """
            )
        else:
            selection_set.discard(codec)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
        apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)


__all__ = ["_CodecFiltersMixin"]
