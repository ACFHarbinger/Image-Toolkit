import pytest
from gui.src.components.containers.merge_canvas import MergeCanvas
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

pytestmark = pytest.mark.gui


def test_merge_canvas_ctrl_wheel_zoom(q_app):
    canvas = MergeCanvas()
    initial_scale = canvas.transform().m11()

    # 1. Scroll with CTRL -> Should zoom in
    zoom_in_event = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )
    canvas.wheelEvent(zoom_in_event)

    scale_after_zoom_in = canvas.transform().m11()
    assert scale_after_zoom_in > initial_scale
    assert scale_after_zoom_in == pytest.approx(initial_scale * 1.15)

    # 2. Scroll with CTRL -> Should zoom out
    zoom_out_event = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )
    canvas.wheelEvent(zoom_out_event)

    scale_after_zoom_out = canvas.transform().m11()
    assert scale_after_zoom_out == pytest.approx(initial_scale)


def test_merge_canvas_wheel_no_ctrl(q_app):
    canvas = MergeCanvas()
    initial_scale = canvas.transform().m11()

    # Scroll WITHOUT CTRL -> Should not zoom
    no_ctrl_event = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )
    canvas.wheelEvent(no_ctrl_event)

    scale_after = canvas.transform().m11()
    assert scale_after == initial_scale


def test_merge_canvas_zoom_limits(q_app):
    canvas = MergeCanvas()

    # Zoom in repeatedly to test we can zoom in very far (e.g. > 50.0)
    zoom_in_event = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )

    for _ in range(50):
        canvas.wheelEvent(zoom_in_event)

    scale_upper = canvas.transform().m11()
    assert scale_upper > 50.0

    # Zoom out repeatedly to test we can zoom out very far (e.g. < 0.005)
    zoom_out_event = QWheelEvent(
        QPointF(100, 100),
        QPointF(100, 100),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False
    )

    for _ in range(100):
        canvas.wheelEvent(zoom_out_event)

    scale_lower = canvas.transform().m11()
    assert scale_lower < 0.005
