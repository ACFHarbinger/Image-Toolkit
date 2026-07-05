import os
from typing import Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from .....helpers.video.video_thumbnailer import VideoThumbnailer, get_video_thumbnail_cache_path
from .data import NodeData

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
            pass

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
            bg_col = QColor("#e67e22")
            border_col = QColor("#d35400")
            border_w = 2
        elif role == "basis":
            bg_col = QColor("#2d3b1e") if is_sel else QColor("#2a3520")
            border_col = QColor("#ffeaa7") if is_sel else QColor("#f1c40f")
            border_w = 4 if is_sel else 3
        elif role == "sink":
            bg_col = QColor("#3b1a2d") if is_sel else QColor("#2e1a2b")
            border_col = QColor("#ff7eb3") if is_sel else QColor("#e056b8")
            border_w = 4 if is_sel else 3
        elif role == "unreachable":
            bg_col = QColor("#3a2020") if is_sel else QColor("#2e2020")
            border_col = QColor("#ff7675") if is_sel else QColor("#7f4040")
            border_w = 4 if is_sel else 2
        else:
            bg_col = QColor("#1a2b3c") if is_sel else QColor("#131c26")
            border_col = QColor("#00ffff") if is_sel else QColor("#3498db")
            border_w = 4 if is_sel else 2

        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, border_w))
        painter.drawRoundedRect(QRectF(1, 1, NODE_W - 2, NODE_H - 2), 6, 6)

        # Role badge strip
        if role == "basis":
            badge = QRectF(1, 1, 42, 13)
            painter.fillRect(badge, QColor("#f1c40f"))
            painter.setPen(QPen(QColor("#1a1a00")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "START")
        elif role == "sink":
            badge = QRectF(1, 1, 36, 13)
            painter.fillRect(badge, QColor("#e056b8"))
            painter.setPen(QPen(QColor("#1a001a")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "END")
        elif role == "unreachable":
            badge = QRectF(1, 1, 52, 13)
            painter.fillRect(badge, QColor("#7f4040"))
            painter.setPen(QPen(QColor("#ffcccc")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "SKIPPED")
        else:
            badge = QRectF(1, 1, 38, 13)
            painter.fillRect(badge, QColor("#3498db"))
            painter.setPen(QPen(QColor("#001a33")))
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
            painter.fillRect(thumb_rect, QColor("#23272a"))
            painter.setPen(QPen(QColor("#7289da")))
            painter.setFont(QFont("Arial", 14))
            icon = "\U0001f3ac" if is_video(self.node_data.file_path) else "\U0001f5bc\ufe0f"
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, icon)

        # Filename
        fname = os.path.basename(self.node_data.file_path)
        if len(fname) > 19:
            fname = fname[:16] + "..."
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(2, 80, NODE_W - 4, 16),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, fname)

        # Duration line
        if self.node_data.display_mode == "video_runtime":
            dur_text = "Full Runtime"
        else:
            s = self.node_data.duration_sec
            dur_text = f"{int(s//60)}m {int(s%60)}s" if s >= 60 else f"{s:.0f}s"
        painter.setPen(QPen(QColor("#b9bbbe")))
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
