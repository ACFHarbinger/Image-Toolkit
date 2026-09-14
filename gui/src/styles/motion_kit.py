"""Shared motion/easing kit for consistent app-wide animations (§2.42, #519).

Provides duration constants, easing curves, and a ``reduce_motion`` check
that reads the OS-level accessibility setting once. All animation call sites
should use this module instead of rolling their own ``QPropertyAnimation``.
"""

from __future__ import annotations

import os
import platform
from functools import lru_cache
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

FAST_MS: int = 120
BASE_MS: int = 200
SLOW_MS: int = 320


def _out_cubic() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.OutCubic)


def _in_out_cubic() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.InOutCubic)


def _out_quad() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.OutQuad)


def _in_out_quad() -> QEasingCurve:
    return QEasingCurve(QEasingCurve.Type.InOutQuad)


@lru_cache(maxsize=1)
def reduce_motion() -> bool:
    """Check OS-level 'reduce motion' accessibility setting.

    Checks (in order):
    1. ``IMAGE_TOOLKIT_REDUCE_MOTION`` env var (``1``/``true``/``yes``)
    2. ``REDUCE_MOTION`` env var (same values)
    3. Platform-specific APIs:
       - Linux: ``gsettings org.gnome.desktop.interface reduce-motion``
       - macOS: ``defaults read NSAccessibilityReduceMotion``
       - Windows: registry ``HKCU\\...\\AnimationsEnabled``

    Result is cached -- call once at startup, not per-animation.
    """
    for var in ("IMAGE_TOOLKIT_REDUCE_MOTION", "REDUCE_MOTION"):
        val = os.environ.get(var, "").lower()
        if val in ("1", "true", "yes"):
            return True
        if val in ("0", "false", "no"):
            return False

    system = platform.system()
    try:
        if system == "Linux":
            import subprocess

            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "reduce-motion"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip().lower() == "true"
        elif system == "Darwin":
            import subprocess

            result = subprocess.run(
                ["defaults", "read", "NSAccessibilityReduceMotion"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip() == "1"
        elif system == "Windows":
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop",
            )
            try:
                val, _ = winreg.QueryValueEx(key, "UserPreferencesMask")
                return bool(val[0] & 0x1) if isinstance(val, (bytes, bytearray)) and len(val) > 0 else False
            except (FileNotFoundError, OSError):
                pass
            finally:
                winreg.CloseKey(key)
    except Exception:
        pass

    return False


def animate_fade(
    widget: QWidget,
    *,
    from_opacity: float = 0.0,
    to_opacity: float = 1.0,
    duration_ms: int = BASE_MS,
    easing: Optional[QEasingCurve] = None,
    on_finished: Optional[object] = None,
) -> Optional[QPropertyAnimation]:
    """Fade a widget's opacity. Returns the animation (caller must hold a reference).

    If ``reduce_motion()`` is True, sets the final opacity immediately and returns None.
    """
    if reduce_motion():
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(to_opacity)
        widget.setGraphicsEffect(effect)
        return None

    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration_ms)
    anim.setStartValue(from_opacity)
    anim.setEndValue(to_opacity)
    anim.setEasingCurve(easing or _out_cubic())
    if on_finished is not None:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def animate_slide(
    widget: QWidget,
    *,
    prop: bytes = b"pos",
    start_value: object = None,
    end_value: object = None,
    duration_ms: int = BASE_MS,
    easing: Optional[QEasingCurve] = None,
    on_finished: Optional[object] = None,
) -> Optional[QPropertyAnimation]:
    """Slide a widget property (pos, geometry, etc). Returns the animation.

    If ``reduce_motion()`` is True, sets the end value immediately and returns None.
    """
    if reduce_motion():
        if end_value is not None:
            widget.setProperty(prop.decode(), end_value)
        return None

    anim = QPropertyAnimation(widget, prop)
    anim.setDuration(duration_ms)
    if start_value is not None:
        anim.setStartValue(start_value)
    if end_value is not None:
        anim.setEndValue(end_value)
    anim.setEasingCurve(easing or _out_cubic())
    if on_finished is not None:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def animate_width(
    widget: QWidget,
    *,
    from_width: int,
    to_width: int,
    duration_ms: int = BASE_MS,
    easing: Optional[QEasingCurve] = None,
    on_finished: Optional[object] = None,
) -> Optional[QPropertyAnimation]:
    """Animate a widget's width. Returns the animation.

    If ``reduce_motion()`` is True, sets the final width immediately and returns None.
    """
    if reduce_motion():
        widget.setFixedWidth(to_width)
        return None

    anim = QPropertyAnimation(widget, b"minimumWidth")
    anim.setDuration(duration_ms)
    anim.setStartValue(from_width)
    anim.setEndValue(to_width)
    anim.setEasingCurve(easing or _out_cubic())
    if on_finished is not None:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


__all__ = [
    "FAST_MS",
    "BASE_MS",
    "SLOW_MS",
    "reduce_motion",
    "animate_fade",
    "animate_slide",
    "animate_width",
]
