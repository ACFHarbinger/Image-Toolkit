import logging
import os
from typing import Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from .....helpers.video.video_thumbnailer import VideoThumbnailer, get_video_thumbnail_cache_path
from .....theming.theme_api import color
from .....theming.wallpaper_graph_palette import (
    NODE_BASIS_BADGE_TEXT,
    NODE_BASIS_BG,
    NODE_BASIS_BG_SEL,
    NODE_BASIS_BORDER,
    NODE_BASIS_BORDER_SEL,
    NODE_HOVER_ORANGE_BG,
    NODE_HOVER_ORANGE_BORDER,
    NODE_SINK_BADGE_TEXT,
    NODE_SINK_BG,
    NODE_SINK_BG_SEL,
    NODE_SINK_BORDER,
    NODE_SINK_BORDER_SEL,
    NODE_STEP_BADGE_TEXT,
    NODE_STEP_BG,
    NODE_STEP_BG_SEL,
    NODE_STEP_BORDER,
    NODE_STEP_BORDER_SEL,
    NODE_THUMB_PLACEHOLDER_BG,
    NODE_THUMB_PLACEHOLDER_ICON,
    NODE_UNREACHABLE_BADGE_TEXT,
    NODE_UNREACHABLE_BG,
    NODE_UNREACHABLE_BG_SEL,
    NODE_UNREACHABLE_BORDER,
    NODE_UNREACHABLE_BORDER_SEL,
)
from .data_schema import NodeData

logger = logging.getLogger(__name__)

NODE_W = 140
NODE_H = 115


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_VIDEO_FORMATS


class NodeItem(QGraphicsObject):
    """Visual node in the wallpaper sequence graph."""

    def __init__(self, node_data: NodeData):
        super().__init__()
        self.node_data = node_data
        self._pixmap: Optional[QPixmap] = None
        self._load_thumbnail()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(node_data.pos_x, node_data.pos_y)
        self.setToolTip(node_data.file_path)

    def _load_thumbnail(self):
        path = self.node_data.file_path
        if not os.path.exists(path):
            return
        try:
            if is_video(path):
                cache_path = get_video_thumbnail_cache_path(path)
                if os.path.exists(cache_path):
                    pm = QPixmap(cache_path)
                else:
                    thumbnailer = VideoThumbnailer()
                    qimg = thumbnailer.generate(path, 120)
                    if qimg and not qimg.isNull():
                        pm = QPixmap.fromImage(qimg)
                        qimg.save(cache_path, "JPG")   # pyrefly: ignore [no-matching-overload]
                    else:
                        pm = QPixmap()
            else:
                pm = QPixmap(path)

            if not pm.isNull():
                self._pixmap = pm.scaled(120, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        except Exception:
            logger.debug("Suppressed Exception in NodeItem._load_thumbnail", exc_info=True)

    def refresh_thumbnail(self):
        self._pixmap = None
        self._load_thumbnail()
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, NODE_W, NODE_H)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Role assigned by WallpaperGraphScene._refresh_node_styles
        role = getattr(self, "_node_role", "reachable")
        is_sel = self.isSelected()

        if getattr(self, "_hovered_orange", False):
            bg_col = QColor(NODE_HOVER_ORANGE_BG)
            border_col = QColor(NODE_HOVER_ORANGE_BORDER)
            border_w = 2
        elif role == "basis":
            bg_col = QColor(NODE_BASIS_BG_SEL) if is_sel else QColor(NODE_BASIS_BG)
            border_col = QColor(NODE_BASIS_BORDER_SEL) if is_sel else QColor(NODE_BASIS_BORDER)
            border_w = 4 if is_sel else 3
        elif role == "sink":
            bg_col = QColor(NODE_SINK_BG_SEL) if is_sel else QColor(NODE_SINK_BG)
            border_col = QColor(NODE_SINK_BORDER_SEL) if is_sel else QColor(NODE_SINK_BORDER)
            border_w = 4 if is_sel else 3
        elif role == "unreachable":
            bg_col = QColor(NODE_UNREACHABLE_BG_SEL) if is_sel else QColor(NODE_UNREACHABLE_BG)
            border_col = QColor(NODE_UNREACHABLE_BORDER_SEL) if is_sel else QColor(NODE_UNREACHABLE_BORDER)
            border_w = 4 if is_sel else 2
        else:
            bg_col = QColor(NODE_STEP_BG_SEL) if is_sel else QColor(NODE_STEP_BG)
            border_col = QColor(NODE_STEP_BORDER_SEL) if is_sel else QColor(NODE_STEP_BORDER)
            border_w = 4 if is_sel else 2

        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, border_w))
        painter.drawRoundedRect(QRectF(1, 1, NODE_W - 2, NODE_H - 2), 6, 6)

        # Role badge strip
        if role == "basis":
            badge = QRectF(1, 1, 42, 13)
            painter.fillRect(badge, QColor(NODE_BASIS_BORDER))
            painter.setPen(QPen(QColor(NODE_BASIS_BADGE_TEXT)))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "START")
        elif role == "sink":
            badge = QRectF(1, 1, 36, 13)
            painter.fillRect(badge, QColor(NODE_SINK_BORDER))
            painter.setPen(QPen(QColor(NODE_SINK_BADGE_TEXT)))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "END")
        elif role == "unreachable":
            badge = QRectF(1, 1, 52, 13)
            painter.fillRect(badge, QColor(NODE_UNREACHABLE_BORDER))
            painter.setPen(QPen(QColor(NODE_UNREACHABLE_BADGE_TEXT)))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "SKIPPED")
        else:
            badge = QRectF(1, 1, 38, 13)
            painter.fillRect(badge, QColor(NODE_STEP_BORDER))
            painter.setPen(QPen(QColor(NODE_STEP_BADGE_TEXT)))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "STEP")

        # Thumbnail area
        has_badge = True
        thumb_top = 15 if has_badge else 5
        thumb_rect = QRectF(5, thumb_top, NODE_W - 10, 72 - (thumb_top - 5))
        if self._pixmap:
            pw, ph = self._pixmap.width(), self._pixmap.height()
            rx = thumb_rect.x() + (thumb_rect.width() - pw) / 2
            ry = thumb_rect.y() + (thumb_rect.height() - ph) / 2
            painter.drawPixmap(int(rx), int(ry), self._pixmap)
        else:
            painter.fillRect(thumb_rect, QColor(NODE_THUMB_PLACEHOLDER_BG))
            painter.setPen(QPen(QColor(NODE_THUMB_PLACEHOLDER_ICON)))
            painter.setFont(QFont("Arial", 14))
            icon = "\U0001f3ac" if is_video(self.node_data.file_path) else "\U0001f5bc\ufe0f"
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, icon)

        # Filename
        fname = os.path.basename(self.node_data.file_path)
        if len(fname) > 19:
            fname = fname[:16] + "..."
        painter.setPen(QPen(QColor(color("text"))))
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(2, 80, NODE_W - 4, 16),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, fname)

        # Duration line
        if self.node_data.display_mode == "video_runtime":
            dur_text = "Full Runtime"
        else:
            s = self.node_data.duration_sec
            dur_text = f"{int(s//60)}m {int(s%60)}s" if s >= 60 else f"{s:.0f}s"
        painter.setPen(QPen(QColor(color("muted_text"))))
        painter.setFont(QFont("Arial", 7))
        painter.drawText(QRectF(2, 97, NODE_W - 4, 14),
                         Qt.AlignmentFlag.AlignCenter, dur_text)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node_data.pos_x = self.pos().x()
            self.node_data.pos_y = self.pos().y()
            sc = self.scene()
            if sc and hasattr(sc, "_on_node_moved"):
                sc._on_node_moved(self.node_data.node_id)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        sc = self.scene()
        if sc and hasattr(sc, "node_edit_requested"):
            sc.node_edit_requested.emit(self.node_data.node_id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        sc = self.scene()
        if sc and hasattr(sc, "_node_context_menu"):
            sc._node_context_menu(self.node_data.node_id, event.screenPos())
        event.accept()
