import pytest
from editor import LayerStack

from cel_shaded_generator_gui.elements.layer_canvas import LayerCanvas

pytestmark = pytest.mark.gui


def test_no_layer_stack_initially(q_app):
    canvas = LayerCanvas()
    assert canvas.layer_stack() is None
    assert canvas.current_scale() == 1.0


def test_set_layer_stack_renders_composite(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(4, 4)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :, :] = [10, 20, 30, 255]
    canvas.set_layer_stack(stack)
    assert canvas.layer_stack() is stack
    assert not canvas._pixmap_item.pixmap().isNull()


def test_refresh_reflects_layer_stack_mutations(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(2, 2)
    canvas.set_layer_stack(stack)
    stack.add_layer("new", "New")
    canvas.refresh()
    assert not canvas._pixmap_item.pixmap().isNull()


def test_set_layer_stack_none_clears_pixmap(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(2, 2)
    canvas.set_layer_stack(stack)
    canvas.set_layer_stack(None)
    assert canvas._pixmap_item.pixmap().isNull()


class _FakeWheelEvent:
    def __init__(self, delta_y):
        self._delta_y = delta_y

    def angleDelta(self):
        return self

    def y(self):
        return self._delta_y


def test_wheel_event_zooms_in_and_out_within_bounds(q_app):
    canvas = LayerCanvas()
    canvas.set_layer_stack(LayerStack(4, 4))
    canvas.wheelEvent(_FakeWheelEvent(120))
    assert canvas.current_scale() == pytest.approx(1.25)
    canvas.wheelEvent(_FakeWheelEvent(-120))
    assert canvas.current_scale() == pytest.approx(1.0)


def test_wheel_event_is_a_no_op_without_a_layer_stack(q_app):
    canvas = LayerCanvas()
    canvas.wheelEvent(_FakeWheelEvent(120))
    assert canvas.current_scale() == 1.0
