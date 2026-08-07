import pytest

from editor import EditHistory, LayerStack


def test_undo_without_any_record_is_a_no_op():
    stack = LayerStack(2, 2)
    history = EditHistory(stack)
    assert history.can_undo() is False
    assert history.undo() is False


def test_redo_without_any_undo_is_a_no_op():
    stack = LayerStack(2, 2)
    history = EditHistory(stack)
    assert history.can_redo() is False
    assert history.redo() is False


def test_record_then_mutate_then_undo_restores_prior_state():
    stack = LayerStack(2, 2)
    history = EditHistory(stack)
    history.record()
    stack.add_layer("base", "Base")
    assert history.can_undo() is True
    assert history.undo() is True
    assert stack.layers() == []


def test_undo_then_redo_reapplies_the_mutation():
    stack = LayerStack(2, 2)
    history = EditHistory(stack)
    history.record()
    stack.add_layer("base", "Base")
    history.undo()
    assert history.can_redo() is True
    assert history.redo() is True
    assert [layer.meta.id for layer in stack.layers()] == ["base"]


def test_new_record_after_undo_clears_redo():
    stack = LayerStack(2, 2)
    history = EditHistory(stack)
    history.record()
    stack.add_layer("base", "Base")
    history.undo()
    assert history.can_redo() is True
    history.record()
    stack.add_layer("other", "Other")
    assert history.can_redo() is False
    assert history.redo() is False


def test_multiple_undo_steps_restore_in_reverse_order():
    stack = LayerStack(2, 2)
    history = EditHistory(stack)
    history.record()
    stack.add_layer("a", "A")
    history.record()
    stack.add_layer("b", "B")
    assert [layer.meta.id for layer in stack.layers()] == ["a", "b"]
    history.undo()
    assert [layer.meta.id for layer in stack.layers()] == ["a"]
    history.undo()
    assert stack.layers() == []


def test_max_depth_evicts_oldest_undo_entries():
    stack = LayerStack(2, 2)
    history = EditHistory(stack, max_depth=2)
    for index in range(4):
        history.record()
        stack.add_layer(f"layer-{index}", f"Layer {index}")
    assert history.undo() is True
    assert history.undo() is True
    assert history.undo() is False  # only 2 entries retained


def test_rejects_non_positive_max_depth():
    with pytest.raises(ValueError, match="max_depth"):
        EditHistory(LayerStack(2, 2), max_depth=0)


def test_undo_restores_pixel_edits_from_a_paint_stroke():
    stack = LayerStack(2, 2)
    layer = stack.add_layer("base", "Base")
    history = EditHistory(stack)
    history.record()
    layer.pixels[0, 0] = [255, 0, 0, 255]
    history.undo()
    assert stack.layer("base").pixels[0, 0].tolist() == [0, 0, 0, 0]
