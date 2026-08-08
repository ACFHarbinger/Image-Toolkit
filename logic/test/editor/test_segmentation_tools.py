
from editor import (
    LayerStack,
    close_line_gaps_in_layer,
    region_adjacency_for_regions,
    segment_layer_into_regions,
)


def _ring_layer_stack(size=10):
    """A 10x10 canvas with a single square ring of ink enclosing one
    background region -- the simplest fixture with exactly one enclosed,
    non-border-touching region."""
    stack = LayerStack(size, size)
    layer = stack.add_layer("line-art", "Line Art")
    layer.pixels[2, 2:8, :] = [0, 0, 0, 255]
    layer.pixels[7, 2:8, :] = [0, 0, 0, 255]
    layer.pixels[2:8, 2, :] = [0, 0, 0, 255]
    layer.pixels[2:8, 7, :] = [0, 0, 0, 255]
    return stack


def test_segment_layer_into_regions_creates_one_region_layer():
    stack = _ring_layer_stack()
    new_ids = segment_layer_into_regions(stack, "line-art")
    assert len(new_ids) == 1
    region_layer = stack.layer(new_ids[0])
    assert region_layer is not None
    # Interior of the ring is opaque; a corner outside the ring is not.
    assert region_layer.pixels[4, 4, 3] == 255
    assert region_layer.pixels[0, 0, 3] == 0


def test_segment_layer_into_regions_stacks_directly_above_source():
    stack = _ring_layer_stack()
    new_ids = segment_layer_into_regions(stack, "line-art")
    ids_in_order = [layer.meta.id for layer in stack.layers()]
    assert ids_in_order.index(new_ids[0]) == ids_in_order.index("line-art") + 1


def test_segment_layer_into_regions_returns_empty_for_missing_layer():
    stack = LayerStack(4, 4)
    assert segment_layer_into_regions(stack, "missing") == []


def test_segment_layer_into_regions_never_mutates_the_source_layer():
    stack = _ring_layer_stack()
    before = stack.layer("line-art").pixels.copy()
    segment_layer_into_regions(stack, "line-art")
    assert (stack.layer("line-art").pixels == before).all()


def test_segment_layer_into_regions_respects_min_region_area():
    stack = _ring_layer_stack()
    # The enclosed region is 5x5 = 25 pixels; a higher threshold discards it.
    assert segment_layer_into_regions(stack, "line-art", min_region_area=100) == []


def test_close_line_gaps_in_layer_bridges_a_small_gap():
    stack = _ring_layer_stack()
    layer = stack.layer("line-art")
    layer.pixels[2, 4, :] = [0, 0, 0, 0]  # punch a 1px gap in the top edge
    assert segment_layer_into_regions(stack, "line-art") == []  # leaks to the border

    assert close_line_gaps_in_layer(stack, "line-art", 1) is True
    assert layer.pixels[2, 4, 3] == 255
    new_ids = segment_layer_into_regions(stack, "line-art")
    assert len(new_ids) == 1


def test_close_line_gaps_in_layer_returns_false_for_missing_layer():
    stack = LayerStack(4, 4)
    assert close_line_gaps_in_layer(stack, "missing", 1) is False


def test_region_adjacency_for_regions_finds_touching_regions():
    stack = LayerStack(6, 2)
    layer = stack.add_layer("base", "Base")
    a = stack.add_layer("a", "A")
    a.pixels[:, :3, 3] = 255
    b = stack.add_layer("b", "B")
    b.pixels[:, 3:, 3] = 255
    del layer
    assert region_adjacency_for_regions(stack, ["a", "b"]) == {("a", "b")}


def test_region_adjacency_for_regions_empty_for_non_touching_regions():
    stack = LayerStack(6, 2)
    a = stack.add_layer("a", "A")
    a.pixels[:, :1, 3] = 255
    b = stack.add_layer("b", "B")
    b.pixels[:, 5:, 3] = 255
    assert region_adjacency_for_regions(stack, ["a", "b"]) == set()


def test_region_adjacency_for_regions_requires_at_least_two_ids():
    stack = LayerStack(4, 4)
    stack.add_layer("a", "A")
    assert region_adjacency_for_regions(stack, ["a"]) == set()
    assert region_adjacency_for_regions(stack, []) == set()


def test_region_adjacency_for_regions_empty_for_missing_id():
    stack = LayerStack(4, 4)
    stack.add_layer("a", "A")
    assert region_adjacency_for_regions(stack, ["a", "missing"]) == set()
