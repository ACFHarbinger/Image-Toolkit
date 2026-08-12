"""Unit tests for HieTab / HieEditorTab PySide6 components."""

from hie_editor_tab import HieEditorTab
from hie_tab import HieTab
from PIL import Image


def test_hie_tab_initialization(q_app):
    tab = HieTab()
    assert tab.open_image_button.text() == "Open Image…"
    assert tab.tool_select.count() > 0
    assert tab.restoration_select.count() > 0
    assert tab.session is not None


def test_hie_editor_tab_is_embeddable_alias(q_app):
    tab = HieEditorTab()
    assert isinstance(tab, HieTab)
    assert tab.open_image_button.text() == "Open Image…"


def test_hie_tab_load_image_path(q_app, tmp_path):
    img_path = tmp_path / "test_canvas.png"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(img_path)

    tab = HieTab()
    success = tab.load_image_path(str(img_path))

    assert success is True
    assert tab._history is not None
    assert tab._history.current.sequence.frames[0].source == str(img_path)
    assert tab.session.document.metadata["source"] == str(img_path)
