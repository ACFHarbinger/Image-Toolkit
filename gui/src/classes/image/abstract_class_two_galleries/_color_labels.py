"""Color-label persistence (§2.18B+C), card styling, and preview highlighting.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _ColorLabelsMixin:
    """Color labels, card border styling, and the preview-window highlight."""

    _LABEL_COLORS: Dict[str, str] = {
        "red":    "#e74c3c",
        "orange": "#e67e22",
        "yellow": "#f1c40f",
        "green":  "#2ecc71",
        "blue":   "#3498db",
        "purple": "#9b59b6",
    }
    _LABEL_ICONS: Dict[str, str] = {
        "red": "🔴", "orange": "🟠", "yellow": "🟡",
        "green": "🟢", "blue": "🔵", "purple": "🟣",
    }

    def _get_color_label(self: "AbstractClassTwoGalleriesHostProtocol", path: str) -> Optional[str]:
        """Return the color key for *path*, or None if unlabelled."""
        from gui.src.windows.settings.app_settings import AppSettings
        return AppSettings.label(path)

    def _set_color_label(self: "AbstractClassTwoGalleriesHostProtocol", path: str, color_key: Optional[str]) -> None:
        """Persist *color_key* (or clear it) for *path*, then refresh the card border."""
        from gui.src.windows.settings.app_settings import AppSettings
        if color_key:
            AppSettings.set_label(path, color_key)
        else:
            AppSettings.remove(f"labels/{path}")
        card = self.path_to_label_map.get(path)
        if card:
            self.update_card_style(card, path in self.selected_files)

    def update_card_style(self: "AbstractClassTwoGalleriesHostProtocol", widget: QWidget, is_selected: bool):
        if hasattr(widget, "set_selected_style"):
            widget.set_selected_style(is_selected)
        else:
            if is_selected:
                color, width = "#5865f2", "3px"
            else:
                # Show color label border when not selected (§2.18C)
                path = widget.property("gallery_path")
                label_color = self._LABEL_COLORS.get(self._get_color_label(path) or "", "") if path else ""
                color = label_color or "#4f545c"
                width = "2px" if label_color else "1px"
            widget.setStyleSheet(f"border: {width} solid {color};")

    @Slot(str, str)
    def update_preview_highlight(self: "AbstractClassTwoGalleriesHostProtocol", old_path: str, new_path: str):
        """Adds a blue highlight border to the card currently being viewed in the preview window."""
        is_closing = new_path == "WINDOW_CLOSED"

        def reset_card(path, card):
            if not card or not path:
                return
            try:
                orig = card.property("original_style")
                if orig is not None:
                    card.setStyleSheet(orig)
                    card.setProperty("original_style", None)
                else:
                    # Fallback: ensure the selection style is correct
                    self.update_card_style(card, self.is_path_selected(path))
            except RuntimeError:
                pass

        # 1. Restore style for the old card (found gallery and selected gallery)
        reset_card(old_path, self.path_to_label_map.get(old_path))
        reset_card(old_path, self.selected_card_map.get(old_path))

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                self.open_preview_windows.remove(sender_win)  # pyrefly: ignore [bad-argument-type]
            return

        def highlight_card(path, card):
            if not card or not path:
                return
            try:
                # Ensure it has the correct selection state first
                self.update_card_style(card, self.is_path_selected(path))

                # Store style if not already stored
                if card.property("original_style") is None:
                    card.setProperty("original_style", card.styleSheet())

                # Apply blue highlight border to the card wrapper
                current = card.styleSheet().strip()
                sep = "" if not current or current.endswith(";") else ";"
                card.setStyleSheet(f"{current}{sep} border: 4px solid #3498db;")
            except RuntimeError:
                pass

        # 2. Apply highlight to the new card
        highlight_card(new_path, self.path_to_label_map.get(new_path))
        highlight_card(new_path, self.selected_card_map.get(new_path))


__all__ = ["_ColorLabelsMixin"]
