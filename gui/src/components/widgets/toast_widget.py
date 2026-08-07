"""Floating Toast Notification Widget (GUI/UX §2.10A)."""

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class ToastWidget(QWidget):
    """
    A floating, frameless, semi-transparent toast notification widget.
    It queues and stacks vertically when managed by ToastManager.
    """
    
    # Emitted when the toast finishes its animation and closes
    toast_closed = Signal(object)

    def __init__(
        self,
        message: str,
        toast_type: str = "info",
        duration_ms: int = 2500,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self.message = message
        self.toast_type = toast_type.lower()
        self.duration_ms = duration_ms

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.colors = {
            "success": QColor("#4caf50"),
            "warning": QColor("#ff9800"),
            "error": QColor("#f44336"),
            "info": QColor("#00bcd4"),
        }
        self.color = self.colors.get(self.toast_type, self.colors["info"])

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        self.label = QLabel(self.message, self)
        self.label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.label)

        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(QRect(rect.x(), rect.y(), rect.width(), rect.height()), 8, 8)

        # Background color
        bg_color = QColor(30, 30, 30, 220)
        painter.fillPath(path, bg_color)

        # Draw left border indicating type
        painter.setClipPath(path)
        painter.fillRect(0, 0, 6, self.height(), self.color)

    def start_animation(self):
        self.anim_group = QSequentialAnimationGroup(self)

        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

        hold_duration = max(0, self.duration_ms - 600)
        hold = QPropertyAnimation(self, b"windowOpacity")
        hold.setDuration(hold_duration)
        hold.setStartValue(1.0)
        hold.setEndValue(1.0)

        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(300)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.anim_group.addAnimation(fade_in)
        if hold.duration() > 0:
            self.anim_group.addAnimation(hold)
        self.anim_group.addAnimation(fade_out)

        self.anim_group.finished.connect(self._on_animation_finished)
        self.anim_group.start()

    def _on_animation_finished(self):
        self.toast_closed.emit(self)
        self.close()


class ToastManager:
    """Manages stacked toast notifications anchored to a parent widget."""

    def __init__(self, parent_widget: QWidget):
        self.parent_widget = parent_widget
        self.toasts = []
        self.max_toasts = 5
        self.spacing = 10

    def show_toast(self, message: str, toast_type: str = "info", duration_ms: int = 2500):
        if len(self.toasts) >= self.max_toasts:
            oldest = self.toasts.pop(0)
            oldest.close()

        toast = ToastWidget(message, toast_type, duration_ms, self.parent_widget)
        self.toasts.append(toast)

        toast.toast_closed.connect(self._remove_toast)

        self._reposition_toasts()
        toast.setWindowOpacity(0.0)
        toast.show()
        toast.raise_()
        toast.start_animation()

    def _remove_toast(self, toast: ToastWidget):
        if toast in self.toasts:
            self.toasts.remove(toast)
            self._reposition_toasts()

    def _reposition_toasts(self):
        if not self.parent_widget:
            return

        parent_rect = self.parent_widget.rect()
        current_y = parent_rect.height() - 20

        for toast in reversed(self.toasts):
            current_y -= toast.height()
            x = parent_rect.width() - toast.width() - 20

            anim = QPropertyAnimation(toast, b"pos")
            anim.setDuration(200)
            anim.setStartValue(
                toast.pos() if toast.isVisible() else QPoint(x, current_y + 20)
            )
            anim.setEndValue(QPoint(x, current_y))
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            anim.start()
            
            # Keep reference to avoid garbage collection
            toast._pos_anim = anim

            current_y -= self.spacing
