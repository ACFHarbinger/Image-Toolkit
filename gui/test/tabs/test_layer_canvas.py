import pytest
from editor import EditHistory, LayerStack
from PySide6.QtCore import QPoint, Qt

from cel_shaded_generator_gui.elements.layer_canvas import LayerCanvas

pytestmark = pytest.mark.gui


class _FakeMousePressEvent:
    def __init__(self, x, y, button=Qt.MouseButton.LeftButton):
        self._point = QPoint(x, y)
        self._button = button

    def pos(self):
        return self._point

    def button(self):
        return self._button


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


def test_default_tool_is_pan(q_app):
    canvas = LayerCanvas()
    assert canvas.tool() == "pan"


def test_set_tool_switches_drag_mode(q_app):
    from PySide6.QtWidgets import QGraphicsView

    canvas = LayerCanvas()
    canvas.set_tool("brush")
    assert canvas.tool() == "brush"
    assert canvas.dragMode() == QGraphicsView.DragMode.NoDrag
    canvas.set_tool("pan")
    assert canvas.dragMode() == QGraphicsView.DragMode.ScrollHandDrag


def test_set_tool_rejects_unknown_tool(q_app):
    canvas = LayerCanvas()
    with pytest.raises(ValueError, match="unsupported tool"):
        canvas.set_tool("eraser")


def test_brush_color_and_radius_setters(q_app):
    canvas = LayerCanvas()
    canvas.set_brush_color((10, 20, 30, 255))
    assert canvas.brush_color() == (10, 20, 30, 255)
    canvas.set_brush_radius(9)
    assert canvas.brush_radius() == 9
    canvas.set_brush_radius(-5)
    assert canvas.brush_radius() == 0


def test_brush_hardness_setter_clamps_to_unit_range(q_app):
    canvas = LayerCanvas()
    assert canvas.brush_hardness() == 1.0  # default: fully hard, unchanged prior behavior
    canvas.set_brush_hardness(0.4)
    assert canvas.brush_hardness() == 0.4
    canvas.set_brush_hardness(-1.0)
    assert canvas.brush_hardness() == 0.0
    canvas.set_brush_hardness(5.0)
    assert canvas.brush_hardness() == 1.0


def test_paint_dot_soft_hardness_fades_the_edge(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(21, 21)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_brush_color((255, 0, 0, 255))
    canvas.set_brush_radius(8)
    canvas.set_brush_hardness(0.0)
    canvas._paint_dot_at_pixel(10, 10)
    layer = stack.layer("base")
    assert layer.pixels[10, 10].tolist() == [255, 0, 0, 255]  # center: fully opaque
    assert 0 < layer.pixels[10, 17, 3] < 255  # near the edge: fading
    assert layer.pixels[10, 19].tolist() == [0, 0, 0, 0]  # outside radius: untouched


def test_paint_line_soft_hardness_paints_a_faded_stroke(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(20, 20)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_brush_color((0, 0, 255, 255))
    canvas.set_brush_radius(2)
    canvas.set_brush_hardness(0.5)
    canvas._paint_line_at_pixel(1, 10, 15, 10)
    row_alpha = stack.layer("base").pixels[10, 1:16, 3]
    assert (row_alpha > 0).all()


def test_mask_mode_ignores_brush_hardness(q_app):
    """Mask painting stays hard-edged (direct overwrite) regardless of
    brush hardness -- soft masks aren't a supported concept yet."""
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    layer = stack.add_layer("base", "Base")
    stack.add_mask("base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_mask_mode(True)
    canvas.set_brush_radius(2)
    canvas.set_brush_hardness(0.0)
    canvas.set_mask_intensity(200)
    canvas._paint_dot_at_pixel(5, 5)
    assert layer.mask[5, 5] == 200
    assert layer.mask[5, 6] == 200  # within radius: still a hard, uniform overwrite


def test_paint_dot_at_pixel_requires_an_active_layer(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    # No active layer bound yet -- painting must be a no-op, not a crash.
    canvas._paint_dot_at_pixel(5, 5)
    assert (stack.layer("base").pixels == 0).all()


def test_paint_dot_at_pixel_paints_the_active_layer(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_brush_color((255, 0, 0, 255))
    canvas.set_brush_radius(1)
    canvas._paint_dot_at_pixel(5, 5)
    assert stack.layer("base").pixels[5, 5].tolist() == [255, 0, 0, 255]


def test_paint_line_at_pixel_paints_the_active_layer(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_brush_color((0, 255, 0, 255))
    canvas.set_brush_radius(1)
    canvas._paint_line_at_pixel(1, 5, 8, 5)
    assert stack.layer("base").pixels[5, 1, 3] > 0
    assert stack.layer("base").pixels[5, 8, 3] > 0


def test_mouse_paint_flow_via_private_pixel_hooks(q_app):
    """Exercises the same press/move/release bookkeeping mousePressEvent/
    mouseMoveEvent/mouseReleaseEvent use, without fighting
    QGraphicsView.mapToScene's viewport/scene coordinate mapping in a
    headless test -- mirrors MangaCanvasEditor's existing test pattern of
    calling the pixel-space paint methods directly."""
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_tool("brush")
    canvas.set_brush_radius(1)

    canvas._painting = True
    canvas._last_point = (2, 2)
    canvas._paint_dot_at_pixel(2, 2)
    point = (6, 2)
    canvas._paint_line_at_pixel(*canvas._last_point, *point)
    canvas._last_point = point
    canvas._painting = False

    assert stack.layer("base").pixels[2, 2, 3] > 0
    assert stack.layer("base").pixels[2, 6, 3] > 0


def test_mouse_press_records_one_history_checkpoint_per_stroke(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_tool("brush")
    history = EditHistory(stack)
    canvas.set_history(history)
    # Bypass QGraphicsView's viewport/scene coordinate mapping (untestable
    # without a shown, sized widget) the same way MangaCanvasEditor's tests
    # avoid it -- stub the one call mousePressEvent makes through it.
    canvas._scene_point_to_pixel = lambda event: (3, 3)

    canvas.mousePressEvent(_FakeMousePressEvent(3, 3))
    canvas.mouseReleaseEvent(_FakeMousePressEvent(3, 3))

    assert stack.layer("base").pixels[3, 3, 3] > 0
    assert history.can_undo() is True
    assert history.undo() is True
    assert stack.layer("base").pixels[3, 3, 3] == 0


def test_mouse_press_does_not_record_without_an_active_layer(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_tool("brush")
    history = EditHistory(stack)
    canvas.set_history(history)

    canvas.mousePressEvent(_FakeMousePressEvent(3, 3))

    assert history.can_undo() is False


def test_mask_mode_setters(q_app):
    canvas = LayerCanvas()
    assert canvas.mask_mode() is False
    canvas.set_mask_mode(True)
    assert canvas.mask_mode() is True
    assert canvas.mask_intensity() == 255
    canvas.set_mask_intensity(500)
    assert canvas.mask_intensity() == 255
    canvas.set_mask_intensity(-5)
    assert canvas.mask_intensity() == 0


def test_mask_mode_paints_the_mask_not_the_pixels(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    stack.add_mask("base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_mask_mode(True)
    canvas.set_mask_intensity(0)
    canvas.set_brush_radius(1)
    canvas._paint_dot_at_pixel(5, 5)
    assert stack.layer("base").mask[5, 5] == 0
    assert stack.layer("base").pixels[5, 5].tolist() == [0, 0, 0, 0]


def test_mask_mode_is_a_no_op_without_a_mask_on_the_active_layer(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_mask_mode(True)
    canvas._paint_dot_at_pixel(5, 5)
    assert stack.layer("base").mask is None
    assert stack.layer("base").pixels[5, 5].tolist() == [0, 0, 0, 0]


def test_mask_mode_line_painting(q_app):
    canvas = LayerCanvas()
    stack = LayerStack(10, 10)
    stack.add_layer("base", "Base")
    stack.add_mask("base")
    canvas.set_layer_stack(stack)
    canvas.set_active_layer_id("base")
    canvas.set_mask_mode(True)
    canvas.set_mask_intensity(128)
    canvas.set_brush_radius(1)
    canvas._paint_line_at_pixel(2, 5, 7, 5)
    assert stack.layer("base").mask[5, 2] == 128
    assert stack.layer("base").mask[5, 7] == 128
