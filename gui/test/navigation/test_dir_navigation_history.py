import sys

from gui.src.classes.base.gallery_base import AbstractGalleryBase
from PySide6.QtWidgets import QApplication


# Dummy concrete implementation of AbstractGalleryBase
class DummyGallery(AbstractGalleryBase):
    def __init__(self):
        super().__init__()
        self.last_browsed_dir = "/dir/initial"
        self.current_loaded_dir = "/dir/initial"

    def get_default_config(self) -> dict:
        return {}

    def set_config(self, config: dict) -> None:
        pass

    def _on_layout_change(self) -> None:
        pass

    def _navigate_to_dir(self, path: str) -> None:
        self.current_loaded_dir = path
        self.last_browsed_dir = path


if not QApplication.instance():
    app = QApplication(sys.argv)


def test_dir_navigation_history_stacks():
    gallery = DummyGallery()
    assert len(gallery._dir_back_stack) == 0
    assert len(gallery._dir_forward_stack) == 0

    # Push first navigation
    gallery._push_dir_history("/dir/first")
    assert list(gallery._dir_back_stack) == ["/dir/initial"]
    assert len(gallery._dir_forward_stack) == 0

    gallery.last_browsed_dir = "/dir/first"
    gallery._push_dir_history("/dir/second")
    assert list(gallery._dir_back_stack) == ["/dir/initial", "/dir/first"]

    gallery.last_browsed_dir = "/dir/second"
    # Go back
    prev = gallery._dir_go_back()
    assert prev == "/dir/first"
    gallery.last_browsed_dir = prev
    assert list(gallery._dir_back_stack) == ["/dir/initial"]
    assert list(gallery._dir_forward_stack) == ["/dir/second"]

    # Go forward
    nxt = gallery._dir_go_forward()
    assert nxt == "/dir/second"
    gallery.last_browsed_dir = nxt
    assert list(gallery._dir_back_stack) == ["/dir/initial", "/dir/first"]
    assert len(gallery._dir_forward_stack) == 0


def test_nav_history_buttons_state():
    gallery = DummyGallery()
    btn_back, btn_forward = gallery.create_nav_history_buttons()

    assert not btn_back.isEnabled()
    assert not btn_forward.isEnabled()

    # Push a directory
    gallery._push_dir_history("/dir/a")
    assert btn_back.isEnabled()
    assert not btn_forward.isEnabled()

    # Simulate clicking back
    gallery.last_browsed_dir = "/dir/a"
    btn_back.click()
    assert gallery.current_loaded_dir == "/dir/initial"
    assert not btn_back.isEnabled()
    assert btn_forward.isEnabled()

    # Simulate clicking forward
    btn_forward.click()
    assert gallery.current_loaded_dir == "/dir/a"
    assert btn_back.isEnabled()
    assert not btn_forward.isEnabled()
