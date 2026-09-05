"""Shared motion and micro-interaction easing kit (GUI/UX §2.42, #519)."""

from __future__ import annotations

from typing import Callable, List, Optional
from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from gui.src.windows.settings.app_settings import AppSettings


class MotionKit:
    """Standardized animation and easing utilities for creative suite transitions."""

    # Durations (ms)
    FAST_MS = 120
    BASE_MS = 200
    SLOW_MS = 320

    # Standard Easing Curves
    EASING_DEFAULT = QEasingCurve.Type.OutCubic
    EASING_IN_OUT = QEasingCurve.Type.InOutCubic
    EASING_SMOOTH = QEasingCurve.Type.OutQuad
    EASING_SNAPPY = QEasingCurve.Type.OutBack

    @classmethod
    def is_reduce_motion_enabled(cls) -> bool:
        """Check if user or system requested reduced motion."""
        val = AppSettings.get("preferences/reduce_motion")
        if val is not None:
            if isinstance(val, str):
                return val.lower() in ("true", "1", "yes")
            return bool(val)
        return False

    @classmethod
    def effective_duration(cls, duration_ms: int) -> int:
        """Return 0ms when reduced motion is enabled, otherwise specified duration."""
        if cls.is_reduce_motion_enabled():
            return 0
        return max(0, duration_ms)

    @classmethod
    def fade_in(
        cls,
        widget: QWidget,
        duration_ms: int = BASE_MS,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[QPropertyAnimation]:
        """Animate widget opacity from 0.0 to 1.0."""
        dur = cls.effective_duration(duration_ms)
        widget.show()
        if dur == 0:
            if on_finished:
                on_finished()
            return None

        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(dur)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(cls.EASING_DEFAULT)

        def _cleanup():
            if on_finished:
                on_finished()

        anim.finished.connect(_cleanup)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        return anim

    @classmethod
    def fade_out(
        cls,
        widget: QWidget,
        duration_ms: int = BASE_MS,
        hide_on_finish: bool = True,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[QPropertyAnimation]:
        """Animate widget opacity from current/1.0 to 0.0."""
        dur = cls.effective_duration(duration_ms)
        if dur == 0:
            if hide_on_finish:
                widget.hide()
            if on_finished:
                on_finished()
            return None

        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(dur)
        anim.setStartValue(effect.opacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(cls.EASING_DEFAULT)

        def _cleanup():
            if hide_on_finish:
                widget.hide()
            if on_finished:
                on_finished()

        anim.finished.connect(_cleanup)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        return anim

    @classmethod
    def slide_width(
        cls,
        widget: QWidget,
        start_w: int,
        end_w: int,
        duration_ms: int = BASE_MS,
        easing: QEasingCurve.Type = EASING_DEFAULT,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[QPropertyAnimation]:
        """Animate widget width expansion or collapse using maximumWidth property."""
        dur = cls.effective_duration(duration_ms)
        if dur == 0:
            widget.setMaximumWidth(end_w)
            if end_w == 0:
                widget.hide()
            else:
                widget.show()
            if on_finished:
                on_finished()
            return None

        if end_w > 0 and not widget.isVisible():
            widget.show()

        anim = QPropertyAnimation(widget, b"maximumWidth", widget)
        anim.setDuration(dur)
        anim.setStartValue(start_w)
        anim.setEndValue(end_w)
        anim.setEasingCurve(easing)

        def _cleanup():
            if end_w == 0:
                widget.hide()
            widget.updateGeometry()
            if on_finished:
                on_finished()

        anim.finished.connect(_cleanup)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        return anim

    @classmethod
    def animate_stacked_switch(
        cls,
        stack: QStackedWidget,
        target_index: int,
        duration_ms: int = BASE_MS,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        """Cross-fade transition between pages in a QStackedWidget."""
        if target_index < 0 or target_index >= stack.count() or target_index == stack.currentIndex():
            if on_finished:
                on_finished()
            return

        dur = cls.effective_duration(duration_ms)
        if dur == 0:
            stack.setCurrentIndex(target_index)
            if on_finished:
                on_finished()
            return

        target_widget = stack.widget(target_index)
        stack.setCurrentIndex(target_index)
        cls.fade_in(target_widget, duration_ms=dur, on_finished=on_finished)


__all__ = ["MotionKit"]
