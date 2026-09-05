import sys
from PySide6.QtCore import QEasingCurve
from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget, QWidget

from gui.src.styles.motion_kit import MotionKit
from gui.src.windows.settings.app_settings import AppSettings

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_motion_kit_constants():
    assert MotionKit.FAST_MS == 120
    assert MotionKit.BASE_MS == 200
    assert MotionKit.SLOW_MS == 320
    assert MotionKit.EASING_DEFAULT == QEasingCurve.Type.OutCubic


def test_reduce_motion_effective_duration():
    AppSettings.set("preferences/reduce_motion", False)
    assert MotionKit.is_reduce_motion_enabled() is False
    assert MotionKit.effective_duration(200) == 200

    AppSettings.set("preferences/reduce_motion", True)
    assert MotionKit.is_reduce_motion_enabled() is True
    assert MotionKit.effective_duration(200) == 0

    # Reset
    AppSettings.set("preferences/reduce_motion", False)


def test_motion_kit_fade_and_slide():
    widget = QWidget()
    widget.resize(300, 200)

    # Fade In
    anim = MotionKit.fade_in(widget, duration_ms=50)
    assert widget.isVisible()

    # Slide Width
    slide_anim = MotionKit.slide_width(widget, start_w=100, end_w=300, duration_ms=50)
    assert widget.isVisible()


def test_motion_kit_stacked_switch():
    stack = QStackedWidget()
    page1 = QLabel("Page 1")
    page2 = QLabel("Page 2")
    stack.addWidget(page1)
    stack.addWidget(page2)
    assert stack.currentIndex() == 0

    MotionKit.animate_stacked_switch(stack, target_index=1, duration_ms=50)
    assert stack.currentIndex() == 1
