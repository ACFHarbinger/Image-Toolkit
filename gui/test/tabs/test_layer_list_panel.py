import pytest
from editor import LayerStack
from PySide6.QtCore import Qt

from cel_shaded_generator_gui.elements.layer_list_panel import LayerListPanel

pytestmark = pytest.mark.gui


def _ids(panel):
    return [
        panel._list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(panel._list.count())
    ]


def test_set_layer_stack_populates_list_top_to_bottom(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("bottom", "Bottom")
    stack.add_layer("top", "Top")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    assert _ids(panel) == ["top", "bottom"]


def test_add_layer_button_appends_and_emits(q_app):
    stack = LayerStack(2, 2)
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    seen = []
    panel.layers_changed.connect(lambda: seen.append(True))
    panel._add_layer()
    assert len(stack.layers()) == 1
    assert panel._list.count() == 1
    assert seen == [True]


def test_remove_selected_layer(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("only", "Only")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    panel._list.setCurrentRow(0)
    panel._remove_selected_layer()
    assert stack.layers() == []
    assert panel._list.count() == 0


def test_remove_without_selection_is_a_no_op(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("only", "Only")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    panel._list.setCurrentRow(-1)
    panel._remove_selected_layer()
    assert len(stack.layers()) == 1


def test_move_selected_layer_reorders_stack_and_reselects(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("bottom", "Bottom")
    stack.add_layer("top", "Top")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    # "Top" is row 0 (list is top-to-bottom); move it down one.
    panel._list.setCurrentRow(0)
    panel._move_selected_layer(1)
    assert [layer.meta.id for layer in stack.layers()] == ["top", "bottom"]
    assert panel.selected_layer_id() == "top"


def test_move_selected_layer_at_boundary_is_a_no_op(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("only", "Only")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    panel._list.setCurrentRow(0)
    panel._move_selected_layer(-1)
    assert [layer.meta.id for layer in stack.layers()] == ["only"]


def test_unchecking_item_hides_layer_and_emits(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("only", "Only")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    seen = []
    panel.layers_changed.connect(lambda: seen.append(True))
    item = panel._list.item(0)
    item.setCheckState(Qt.CheckState.Unchecked)
    assert stack.layer("only").meta.visible is False
    assert seen == [True]


def test_setting_none_layer_stack_clears_list(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("only", "Only")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    panel.set_layer_stack(None)
    assert panel._list.count() == 0
    assert panel.selected_layer_id() is None


def test_selecting_a_row_emits_layer_selected(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("bottom", "Bottom")
    stack.add_layer("top", "Top")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    seen = []
    panel.layer_selected.connect(seen.append)
    panel._list.setCurrentRow(1)
    assert seen[-1] == "bottom"


def test_select_layer_selects_by_id_and_emits(q_app):
    stack = LayerStack(2, 2)
    stack.add_layer("bottom", "Bottom")
    stack.add_layer("top", "Top")
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    seen = []
    panel.layer_selected.connect(seen.append)
    panel.select_layer("bottom")
    assert panel.selected_layer_id() == "bottom"
    assert seen[-1] == "bottom"


def test_add_layer_auto_selects_the_new_layer(q_app):
    stack = LayerStack(2, 2)
    panel = LayerListPanel()
    panel.set_layer_stack(stack)
    panel._add_layer()
    new_id = stack.layers()[0].meta.id
    assert panel.selected_layer_id() == new_id
