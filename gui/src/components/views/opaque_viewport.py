from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class OpaqueViewport(QWidget):
    """Opaque, cached gallery backing that preserves the background artwork.

    Qt can scroll-blit this viewport because every pixel is painted. The
    cached backing still contains the window-aligned background plus a theme
    tint, so glassmorphism does not require transparent widget ancestry
    (see #453/#457 -- a transparent viewport disables Qt's fast scroll-blit
    path and forces a full-ancestor-chain repaint on every card update).

    IMPORTANT, read before "fixing" this back to transparent (this file has
    been reverted to transparent and re-fixed to opaque four times already
    -- see the 2026-08-19/20 bus log): ``WA_OpaquePaintEvent = True`` does
    NOT mean this widget stops showing the background image. ``_rebuild_backing``
    draws the actual configured background artwork (via
    ``BackgroundCanvasController.render_background``) into the cached
    pixmap, window-aligned, then a translucent tint on top -- the on-screen
    result is visually indistinguishable from a truly transparent widget
    layered over the same background. The two things that would make this
    genuinely look like an "opaque dark box" -- (a) never drawing the real
    image at all, (b) sourcing the base fill from an unreliable color -- are
    exactly what the tests below assert against. If galleries look wrong,
    the bug is almost certainly in ``render_background``/config wiring, not
    in this widget being opaque. Verify with a real screenshot before
    reverting again.

    The base fill (used when no background image is configured, or as the
    layer under the drawn image) comes from the DARK_BG/LIGHT_BG theme
    constants, not ``self.palette()``. QSS ``background-color`` rules never
    write back into QPalette, so a plain QWidget's palette does not reflect
    the app's actual dark/light theme -- reading it here previously produced
    a pitch-black backing on some setups (#453 follow-up).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gallery_viewport")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._backing = QPixmap()

        # Import lazily to avoid making the low-level components package and
        # the styles package depend on each other during module import.
        from ...styles.background_canvas import BackgroundCanvasController

        BackgroundCanvasController.instance().background_changed.connect(
            self._invalidate_backing
        )

    def _is_dark_theme(self) -> bool:
        # Introspect the top-level window rather than importing MainWindow
        # (would create a components -> windows dependency cycle). Default
        # to dark, matching the hardcoded-dark convention already used by
        # other low-level glassmorphism tints in this codebase (e.g.
        # ClickableLabel's rgba(20, 24, 32, ...) card background).
        root = self.window()
        return getattr(root, "current_theme", "dark") != "light"

    def _base_fill_color(self) -> QColor:
        from ...styles import DARK_BG, LIGHT_BG

        hex_color = DARK_BG if self._is_dark_theme() else LIGHT_BG
        color = QColor(hex_color)
        color.setAlpha(255)
        return color

    def _invalidate_backing(self):
        self._backing = QPixmap()
        self.update()

    def _rebuild_backing(self):
        if self.width() <= 0 or self.height() <= 0:
            return

        backing = QPixmap(self.size())
        base = self._base_fill_color()
        backing.fill(base)

        painter = QPainter(backing)
        root = self.window()
        offset = self.mapTo(root, QPoint(0, 0))

        from ...styles.background_canvas import BackgroundCanvasController

        controller = BackgroundCanvasController.instance()
        controller.render_background(
            painter,
            QRect(-offset.x(), -offset.y(), root.width(), root.height()),
        )

        # The opaque base below this translucent tint guarantees alpha=255.
        tint = (
            QColor(20, 24, 32, 72)
            if base.lightness() < 128
            else QColor(255, 255, 255, 72)
        )
        painter.fillRect(backing.rect(), tint)
        painter.end()
        self._backing = backing

    def paintEvent(self, event):
        if self._backing.size() != self.size() or self._backing.isNull():
            self._rebuild_backing()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._backing)
        painter.end()

    def resizeEvent(self, event):
        self._invalidate_backing()
        super().resizeEvent(event)

    def moveEvent(self, event):
        self._invalidate_backing()
        super().moveEvent(event)

    def changeEvent(self, event):
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._invalidate_backing()
        super().changeEvent(event)
