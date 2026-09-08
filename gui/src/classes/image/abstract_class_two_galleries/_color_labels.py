"""Color-label persistence (§2.18B+C), card styling, and preview highlighting.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Dict, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget

from gui.src.components.gallery.card_factory import (
    DEFAULT_BORDER_COLOR,
    SELECTION_COLOR,
    apply_preview_highlight,
    reset_preview_highlight,
)
from gui.src.qt_object_guard import deleted_qobject_guard

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
                color, width = SELECTION_COLOR, "3px"
            else:
                # Show color label border when not selected (§2.18C)
                path = widget.property("gallery_path")
                label_color = self._LABEL_COLORS.get(self._get_color_label(path) or "", "") if path else ""
                color = label_color or DEFAULT_BORDER_COLOR
                width = "2px" if label_color else "1px"
            widget.setStyleSheet(f"border: {width} solid {color};")

    @Slot(str, str)
    def update_preview_highlight(self: "AbstractClassTwoGalleriesHostProtocol", old_path: str, new_path: str):
        """Adds an amber highlight border to the card currently being viewed in
        the preview window (distinct from the indigo selection border)."""
        is_closing = new_path == "WINDOW_CLOSED"
        dual = getattr(self, "dual", None)

        def reset_card(path, card):
            try:
                reset_preview_highlight(
                    card,
                    path,
                    is_selected=self.is_path_selected(path) if path else False,
                    update_style=self.update_card_style,
                )
            except RuntimeError as exc:
                deleted_qobject_guard(exc, "_ColorLabelsMixin.update_preview_highlight.reset_card")

        # 1. Restore style for the old card (found gallery and selected gallery)
        reset_card(old_path, self.path_to_label_map.get(old_path))
        reset_card(old_path, self.selected_card_map.get(old_path))
        if dual is not None:
            dual.mark_preview(old_path, False)

        if is_closing:
            sender_win = self.sender()
            if sender_win in self.open_preview_windows:
                with contextlib.suppress(ValueError):
                    self.open_preview_windows.remove(sender_win)  # pyrefly: ignore [bad-argument-type]
            return

        def highlight_card(path, card):
            try:
                apply_preview_highlight(
                    card,
                    path,
                    is_selected=self.is_path_selected(path) if path else False,
                    update_style=self.update_card_style,
                )
            except RuntimeError as exc:
                deleted_qobject_guard(exc, "_ColorLabelsMixin.update_preview_highlight.highlight_card")

        # 2. Apply highlight to the new card
        highlight_card(new_path, self.path_to_label_map.get(new_path))
        highlight_card(new_path, self.selected_card_map.get(new_path))
        if dual is not None:
            dual.mark_preview(new_path, True)


__all__ = ["_ColorLabelsMixin"]
