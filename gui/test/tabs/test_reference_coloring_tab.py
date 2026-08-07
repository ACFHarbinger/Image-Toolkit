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
