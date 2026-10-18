"""Drag-to-resize gallery borders (height_resize_grip)."""

import pytest
from gui.src.components.containers import MarqueeScrollArea
from gui.src.components.containers.height_resize_grip import (
    GRIP_THICKNESS,
    MIN_GALLERY_HEIGHT,
    enable_height_resize,
    install_gallery_height_grips,
    watch_gallery_host,
)
from gui.src.components.virtual_gallery import VirtualDualGallery, VirtualGallery
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget


def _mouse(widget, kind, y, buttons=Qt.MouseButton.LeftButton):
    local = QPointF(5, 2)
    glob = QPointF(widget.mapToGlobal(local.toPoint())) + QPointF(0, y)
    button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
    QApplication.sendEvent(
        widget, QMouseEvent(kind, local, glob, button, buttons, Qt.KeyboardModifier.NoModifier)
    )


def _drag(grip, dy):
    _mouse(grip, QEvent.Type.MouseButtonPress, 0)
    _mouse(grip, QEvent.Type.MouseMove, dy)
    _mouse(grip, QEvent.Type.MouseButtonRelease, dy, Qt.MouseButton.NoButton)


def _page(target):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.addWidget(target)
    layout.addStretch(1)
    page.resize(400, 1200)
    page.show()
    return page


@pytest.mark.gui
def test_bottom_and_top_borders_resize_in_opposite_directions(q_app):
    target = QWidget()
    target.setFixedHeight(300)
    page = _page(target)
    resizer = enable_height_resize(target)

    _drag(resizer.bottom_grip, 80)
    assert target.height() == 380
    _drag(resizer.bottom_grip, -30)
    assert target.height() == 350
    # The top border grows the widget when dragged up, shrinks it when dragged down.
    _drag(resizer.top_grip, -50)
    assert target.height() == 400
    _drag(resizer.top_grip, 100)
    assert target.height() == 300
    page.close()


@pytest.mark.gui
def test_grips_follow_edges_clamp_and_reset(q_app):
    target = QWidget()
    target.setMinimumHeight(250)
    target.setMaximumHeight(250)
    page = _page(target)
    resizer = enable_height_resize(target)
    assert enable_height_resize(target) is resizer  # idempotent

    _drag(resizer.bottom_grip, 150)
    assert target.height() == 400
    assert resizer.bottom_grip.geometry().bottom() == target.height() - 1
    assert resizer.top_grip.geometry().top() == 0
    assert resizer.bottom_grip.height() == GRIP_THICKNESS
    assert resizer.bottom_grip.cursor().shape() == Qt.CursorShape.SizeVerCursor

    _drag(resizer.bottom_grip, -5000)
    assert target.height() == MIN_GALLERY_HEIGHT

    QApplication.sendEvent(
        resizer.top_grip,
        QMouseEvent(
            QEvent.Type.MouseButtonDblClick, QPointF(5, 2), QPointF(5, 2),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
        ),
    )
    assert (target.minimumHeight(), target.maximumHeight()) == (250, 250)
    assert resizer.custom_height is None
    page.close()


@pytest.mark.gui
def test_height_is_remembered_per_scope(q_app):
    first = QWidget()
    page = _page(first)
    resizer = enable_height_resize(first, settings_scope="GripTest", settings_key="gallery")
    resizer.set_height(200)
    _drag(resizer.bottom_grip, 60)
    page.close()

    second = QWidget()
    page = _page(second)
    enable_height_resize(second, settings_scope="GripTest", settings_key="gallery")
    assert second.height() == 260
    second._height_resizer.reset()
    page.close()

    third = QWidget()
    page = _page(third)
    assert enable_height_resize(third, settings_scope="GripTest", settings_key="gallery").custom_height is None
    page.close()


@pytest.mark.gui
def test_host_watcher_finds_galleries_but_not_dual_internals(q_app):
    host = QWidget()
    layout = QVBoxLayout(host)
    dual = VirtualDualGallery(host)
    single = VirtualGallery(host)
    scroll = MarqueeScrollArea(host)
    for w in (dual, single, scroll):
        layout.addWidget(w)
    watch_gallery_host(host)
    host.show()

    for w in (dual, single, scroll):
        assert getattr(w, "_height_resizer", None) is not None, type(w).__name__
    assert getattr(dual.found_gallery, "_height_resizer", None) is None
    assert getattr(dual.selected_gallery, "_height_resizer", None) is None
    # A second pass (another show) adds nothing new.
    assert len(install_gallery_height_grips(host)) == 3
    assert len(host.findChildren(QWidget, "gallery_height_grip_bottom")) == 3
    host.close()
