"""QStyledItemDelegate that paints state borders and thumbnail overlay badges — GUI/UX §2.1, §2.40.

Reads ``VirtualGalleryModel``'s ``InDbRole`` / ``SelectedRole`` / ``PreviewRole``
off the model instance (no module-level import of the model, avoiding any
cycle) and draws a color-coded border:

* amber border for rows whose preview window is currently open,
* indigo border for selected rows (two-gallery Selected panel, wallpaper
  click-selection),
* green border for rows the tab marks as already present in the library DB
  (scan-metadata) or queued for a monitor (wallpaper display queue).

Also renders configurable thumbnail overlay badges (rating, resolution, format,
star rating, tag counts) per ``GalleryOverlayConfig``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from .presentation_mode import (
    RATING_COLORS,
    GalleryOverlayConfig,
)


class VirtualGalleryDelegate(QStyledItemDelegate):
    """Draws state borders and custom thumbnail overlay badges on gallery cells."""

    _IN_DB_COLOR = QColor("#2ecc71")
    _SELECTED_COLOR = QColor("#5865f2")
    _PREVIEW_COLOR = QColor("#f39c12")

    def __init__(
        self,
        parent=None,
        overlay_config: Optional[GalleryOverlayConfig] = None,
    ) -> None:
        super().__init__(parent)
        self.overlay_config: GalleryOverlayConfig = overlay_config or GalleryOverlayConfig()

    def set_overlay_config(self, config: GalleryOverlayConfig) -> None:
        self.overlay_config = config

    def paint(self, painter: QPainter, option, index) -> None:
        self._paint_background_and_icon(painter, option, index)
        model = index.model()
        if model is None:
            return

        # 1. State Borders
        try:
            preview = bool(model.data(index, getattr(model, "PreviewRole", -1)))
            selected = bool(model.data(index, getattr(model, "SelectedRole", -1)))
            in_db = bool(model.data(index, getattr(model, "InDbRole", -1)))
        except (AttributeError, TypeError):
            preview = selected = in_db = False

        if preview:
            color, width = self._PREVIEW_COLOR, 4
        elif selected:
            color, width = self._SELECTED_COLOR, 3
        elif in_db:
            color, width = self._IN_DB_COLOR, 3
        else:
            color, width = None, 0

        if color and width > 0:
            d = width // 2
            painter.save()
            painter.setPen(QPen(color, width))
            painter.drawRect(option.rect.adjusted(d, d, -d, -d))
            painter.restore()

        # Hover Highlight (§2.24)
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.save()
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 25)))
            painter.drawRoundedRect(option.rect.adjusted(1, 1, -1, -1), 4, 4)
            painter.restore()

        # 2. Thumbnail Overlays (§2.40)
        self._paint_overlays(painter, option.rect, model, index)

    def _paint_background_and_icon(self, painter: QPainter, option, index) -> None:
        """Paint the item's background/selection chrome via the native style,
        then paint the thumbnail icon ourselves.

        KDE's Breeze (and Kvantum) widget style crops non-square decoration
        pixmaps to their icon box instead of letterboxing them -- a portrait
        thumbnail comes out cut in half vertically. That crop happens inside
        the style's own ``CE_ItemViewItem`` control painting, which is why it
        never reproduces with Qt's built-in styles (Fusion) or in headless/
        offscreen tests. Asking the style to draw the item with no icon at
        all, then painting the icon ourselves via ``QIcon.paint`` (a generic,
        style-independent, aspect-preserving routine), keeps native
        background/selection/hover chrome while sidestepping the buggy icon
        path entirely.
        """
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        icon = opt.icon
        decoration_size = opt.decorationSize

        opt.icon = QIcon()
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDecoration

        widget = option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        if not icon.isNull() and decoration_size.isValid() and not decoration_size.isEmpty():
            icon_rect = QRect(0, 0, decoration_size.width(), decoration_size.height())
            icon_rect.moveCenter(option.rect.center())
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

    def _paint_overlays(self, painter: QPainter, rect: QRectF, model, index) -> None:
        cfg = self.overlay_config
        if not cfg:
            return

        try:
            rating = model.data(index, getattr(model, "RatingRole", -1)) if cfg.show_rating else None
            res = model.data(index, getattr(model, "ResolutionRole", -1)) if cfg.show_resolution else None
            fmt = model.data(index, getattr(model, "FormatRole", -1)) if cfg.show_format else None
            star = model.data(index, getattr(model, "StarRatingRole", -1)) if cfg.show_star_rating else None
            tags = model.data(index, getattr(model, "TagCountRole", -1)) if cfg.show_tag_count else None
        except (AttributeError, TypeError):
            return

        if not any((rating, res, fmt, star, tags)):
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        badge_font = QFont(painter.font())
        badge_font.setPointSize(7)
        badge_font.setBold(True)
        painter.setFont(badge_font)

        # Top-Left: Rating Badge (G, S, Q, E)
        if rating:
            r_str = str(rating).upper()[:1]
            bg_hex = RATING_COLORS.get(r_str.lower(), "#38bdf8")
            badge_rect = QRectF(rect.left() + 6, rect.top() + 6, 16, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(bg_hex)))
            painter.drawRoundedRect(badge_rect, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, r_str)

        # Top-Right: Tag Count or Star Rating
        if tags is not None and tags > 0:
            tag_str = f"🏷️ {tags}"
            tag_rect = QRectF(rect.right() - 48, rect.top() + 6, 42, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
            painter.drawRoundedRect(tag_rect, 3, 3)
            painter.setPen(QColor("#00f0ff"))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag_str)
        elif star is not None and star > 0:
            star_str = f"★ {star:.1f}"
            star_rect = QRectF(rect.right() - 44, rect.top() + 6, 38, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
            painter.drawRoundedRect(star_rect, 3, 3)
            painter.setPen(QColor("#ffb703"))
            painter.drawText(star_rect, Qt.AlignmentFlag.AlignCenter, star_str)

        # Bottom-Left: Resolution Pill (e.g. 1920×1080)
        if res and isinstance(res, (tuple, list)) and len(res) == 2:
            res_str = f"{res[0]}×{res[1]}"
            res_rect = QRectF(rect.left() + 6, rect.bottom() - 22, 64, 15)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
            painter.drawRoundedRect(res_rect, 3, 3)
            painter.setPen(QColor("#e2e8f0"))
            painter.drawText(res_rect, Qt.AlignmentFlag.AlignCenter, res_str)

        # Bottom-Right: File Format Pill (e.g. PNG)
        if fmt:
            fmt_str = str(fmt).upper()
            fmt_rect = QRectF(rect.right() - 36, rect.bottom() - 22, 30, 15)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
            painter.drawRoundedRect(fmt_rect, 3, 3)
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(fmt_rect, Qt.AlignmentFlag.AlignCenter, fmt_str)

        painter.restore()


__all__ = ["VirtualGalleryDelegate"]
