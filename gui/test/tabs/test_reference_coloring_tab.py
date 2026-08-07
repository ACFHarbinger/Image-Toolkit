import pytest
from editor import LayerStack

from cel_shaded_generator_gui.tabs.reference_coloring_tab import ReferenceColoringTab

pytestmark = pytest.mark.gui


def test_initial_state_has_no_canvas(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().layer_stack() is None
    assert "No canvas" in tab._status.text()


def test_binding_a_layer_stack_wires_canvas_and_panel(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(8, 6)
    stack.add_layer("layer-1", "Layer 1")
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._update_status()
    assert tab.canvas().layer_stack() is stack
    assert tab.layer_panel().layer_stack() is stack
    assert "8x6" in tab._status.text()
    assert "1 layer" in tab._status.text()


def test_layer_panel_mutation_refreshes_canvas_and_status(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(4, 4)
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._layer_panel._add_layer()
    assert len(stack.layers()) == 1
    assert "1 layer" in tab._status.text()


def test_default_tool_is_pan(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().tool() == "pan"


def test_selecting_brush_radio_switches_canvas_tool(q_app):
    tab = ReferenceColoringTab()
    tab._brush_tool.setChecked(True)
    assert tab.canvas().tool() == "brush"
    tab._pan_tool.setChecked(True)
    assert tab.canvas().tool() == "pan"


def test_brush_radius_spin_updates_canvas(q_app):
    tab = ReferenceColoringTab()
    tab._brush_radius_spin.setValue(12)
    assert tab.canvas().brush_radius() == 12


def test_layer_selection_wires_canvas_active_layer(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(4, 4)
    stack.add_layer("only", "Only")
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._layer_panel.select_layer("only")
    assert tab.canvas().active_layer_id() == "only"


def test_new_canvas_default_layer_is_selected_and_paintable(q_app, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (10, True)))
    tab = ReferenceColoringTab()
    tab._new_canvas()
    assert tab.canvas().active_layer_id() == "layer-1"
    tab._canvas.set_brush_color((255, 0, 0, 255))
    tab._canvas.set_brush_radius(0)
    tab._canvas._paint_dot_at_pixel(5, 5)
    assert tab.canvas().layer_stack().layer("layer-1").pixels[5, 5].tolist() == [255, 0, 0, 255]
