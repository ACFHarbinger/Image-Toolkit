import sys

from gui.src.components.widgets.toast_widget import ToastManager, ToastWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

# Ensure QApplication exists
if not QApplication.instance():
    app = QApplication(sys.argv)

def test_toast_widget_initialization():
    toast = ToastWidget("Test Message", "success", 3000)
    assert toast.message == "Test Message"
    assert toast.toast_type == "success"
    assert toast.duration_ms == 3000
    assert toast.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert toast.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert toast.label.text() == "Test Message"

def test_toast_manager_show_toast():
    parent = QWidget()
    manager = ToastManager(parent)
    manager.show_toast("Hello", "info", 1000)
    assert len(manager.toasts) == 1

    toast = manager.toasts[0]
    assert toast.message == "Hello"
    assert toast.toast_type == "info"
    assert toast.duration_ms == 1000

def test_toast_manager_max_toasts():
    parent = QWidget()
    manager = ToastManager(parent)
    manager.max_toasts = 3

    for i in range(5):
        manager.show_toast(f"Message {i}")

    assert len(manager.toasts) == 3
    assert manager.toasts[0].message == "Message 2"
    assert manager.toasts[2].message == "Message 4"

def test_toast_repositioning():
    parent = QWidget()
    parent.resize(800, 600)
    manager = ToastManager(parent)

    manager.show_toast("Toast 1")
    manager.show_toast("Toast 2")

    t1 = manager.toasts[0]
    t2 = manager.toasts[1]

    # Check that t2 has higher Y target than t1 (since t2 is newer, it should be at bottom)
    # The animation might be running, but we can check the end value of the animation
    assert t2._pos_anim.endValue().y() > t1._pos_anim.endValue().y()

def test_toast_animation_and_closure():
    parent = QWidget()
    manager = ToastManager(parent)
    manager.show_toast("Close Me", duration_ms=100)

    assert len(manager.toasts) == 1
    toast = manager.toasts[0]

    # Directly invoke closure to test removal logic without waiting
    toast._on_animation_finished()
    assert len(manager.toasts) == 0

