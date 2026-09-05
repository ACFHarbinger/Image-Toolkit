import sys

from gui.src.components.virtual_gallery.dual_widget import VirtualDualGallery
from gui.src.components.widgets.thumbnail_zoom_control import ThumbnailZoomControl
from gui.src.windows.settings.app_settings import AppSettings
from gui.src.windows.settings.thumbnail_size import load_thumbnail_size
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists
if not QApplication.instance():
    app = QApplication(sys.argv)


def test_thumbnail_zoom_control_initialization():
    control = ThumbnailZoomControl(initial_size=200, min_size=48, max_size=512, step=16)
    assert control.current_size == 192  # 200 snapped to 16
    assert control.slider.value() == 192
    assert "192 px" in control.lbl_size.text()


def test_thumbnail_zoom_control_presets():
    control = ThumbnailZoomControl(initial_size=180)
    received_sizes: list[int] = []
    control.size_changed.connect(lambda s: received_sizes.append(s))

    # Click preset 'S' (96px)
    control._preset_buttons["S"].click()
    assert control.current_size == 96
    assert control.slider.value() == 96
    assert "96 px" in control.lbl_size.text()
    assert received_sizes[-1] == 96

    # Click preset 'XL' (384px)
    control._preset_buttons["XL"].click()
    assert control.current_size == 384
    assert control.slider.value() == 384
    assert received_sizes[-1] == 384


def test_thumbnail_zoom_control_slider():
    control = ThumbnailZoomControl(initial_size=180)
    received_sizes: list[int] = []
    control.size_changed.connect(lambda s: received_sizes.append(s))

    control.slider.setValue(250)
    assert control.current_size == 240  # snapped to 16
    assert received_sizes[-1] == 240


def test_thumbnail_zoom_control_step_zoom():
    control = ThumbnailZoomControl(initial_size=160, step=16)
    received_sizes: list[int] = []
    control.size_changed.connect(lambda s: received_sizes.append(s))

    # Step up (+1 step)
    new_size = control.step_zoom(1)
    assert new_size == 176
    assert control.current_size == 176
    assert received_sizes[-1] == 176

    # Step down (-2 steps)
    new_size = control.step_zoom(-2)
    assert new_size == 144
    assert control.current_size == 144
    assert received_sizes[-1] == 144


def test_thumbnail_zoom_control_persistence():
    class_name = "TestZoomPersistenceTab"
    AppSettings.set_session(class_name, "thumbnail_size", 160)

    control = ThumbnailZoomControl(class_name=class_name)
    assert control.current_size == 160

    control.set_size(240, save=True)
    assert load_thumbnail_size(class_name) == 240


def test_virtual_dual_gallery_zoom_integration():
    dual = VirtualDualGallery()
    assert hasattr(dual, "zoom_control")
    assert dual.zoom_control is not None

    initial_size = dual.found_gallery.thumbnail_size
    dual._on_ctrl_wheel(120)  # Scroll up -> zoom in (+1 step)
    assert dual.found_gallery.thumbnail_size == initial_size + 16
    assert dual.selected_gallery.thumbnail_size == initial_size + 16
    assert dual.zoom_control.current_size == initial_size + 16

    # set_thumbnail_size propagates
    dual.set_thumbnail_size(320)
    assert dual.found_gallery.thumbnail_size == 320
    assert dual.selected_gallery.thumbnail_size == 320
    assert dual.zoom_control.current_size == 320
