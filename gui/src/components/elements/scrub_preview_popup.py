from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ScrubPreviewPopup(QWidget):
    """Small floating thumbnail + timestamp shown above a video player's
    progress bar while the playhead is being dragged (YouTube-style).

    Crops a pre-generated storyboard sprite sheet -- no video decoding
    happens here at all, which is the whole point: this widget can be
    updated on every single drag tick, at any drag speed, with no
    dependency on the video's codec, resolution, or seek latency.

    Deliberately a plain CHILD widget (default Qt.WindowType.Widget), not a
    separate top-level floating window: Wayland compositors do not let a
    client freely reposition a top-level window (a bare `.move()` on one is
    silently ignored -- confirmed empirically, not just per Qt docs), which
    is exactly what an anchored-to-the-cursor popup needs to do on every
    single drag tick. A child widget's `.move()` is always honored (it's
    just placing it within its already-on-screen parent's client area, no
    compositor negotiation involved), and `.raise_()` makes it paint above
    its sibling widgets. The parent passed to the constructor must be the
    tab's top-level window (see ExtractorTab._ensure_scrub_popup()), not a
    small child widget, so the popup isn't clipped by an intermediate
    QScrollArea's viewport.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._thumb_label = QLabel()
        self._thumb_label.setStyleSheet(
            "border: 2px solid #4f545c; border-radius: 4px; background-color: #000;"
        )
        layout.addWidget(self._thumb_label)

        self._time_label = QLabel()
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setStyleSheet(
            "color: white; font-weight: bold; background-color: #1e1f22;"
            "border-radius: 3px; padding: 2px 6px;"
        )
        layout.addWidget(self._time_label)

        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "ScrubPreviewPopup { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 6px; }"
        )

    def show_at(
        self,
        *,
        pixmap: QPixmap,
        tile_rect: tuple[int, int, int, int],
        time_text: str,
        anchor_local: QPoint,
    ) -> None:
        """Crops tile_rect out of pixmap, shows time_text underneath, and
        positions the popup horizontally centered on anchor_local (a point
        in this widget's PARENT's local coordinate space -- e.g. the
        slider's position mapped into the top-level window, not a screen-
        global point) with its bottom edge sitting just above it."""
        x, y, w, h = tile_rect
        tile = pixmap.copy(x, y, w, h)
        self._thumb_label.setPixmap(tile)
        self._thumb_label.setFixedSize(tile.size())
        self._time_label.setText(time_text)

        self.adjustSize()
        target_x = anchor_local.x() - self.width() // 2
        target_y = anchor_local.y() - self.height() - 8

        parent = self.parentWidget()
        if parent is not None:
            # Both bounds matter for y, not just the lower one: the
            # anchor's true (unclipped) position within the parent window
            # can legitimately exceed the window's own height if the
            # slider lives inside a tall scrollable tab (mapTo() reports
            # geometric position, not "currently scrolled into view"), and
            # a widget positioned below its top-level window's own frame
            # simply cannot render at all -- there's no window pixels
            # there to draw into.
            target_x = max(0, min(target_x, parent.width() - self.width()))
            target_y = max(0, min(target_y, parent.height() - self.height()))

        self.move(target_x, target_y)
        self.show()
        self.raise_()

    def hide_popup(self) -> None:
        self.hide()
