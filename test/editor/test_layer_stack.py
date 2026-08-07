import numpy as np
import pytest

from editor import Layer, LayerMeta, LayerStack


def test_add_layer_creates_transparent_pixels_at_canvas_size():
    stack = LayerStack(4, 3)
    layer = stack.add_layer("base", "Base")
    assert layer.pixels.shape == (3, 4, 4)
    assert layer.pixels.dtype == np.uint8
    assert (layer.pixels == 0).all()
    assert [layer.meta.id for layer in stack.layers()] == ["base"]


def test_add_layer_rejects_duplicate_ids():
    stack = LayerStack(2, 2)
    stack.add_layer("base", "Base")
    with pytest.raises(ValueError, match="already exists"):
        stack.add_layer("base", "Base Again")


def test_add_layer_inserts_at_explicit_index():
    stack = LayerStack(2, 2)
    stack.add_layer("bottom", "Bottom")
    stack.add_layer("top", "Top")
    stack.add_layer("middle", "Middle", index=1)
    assert [layer.meta.id for layer in stack.layers()] == ["bottom", "middle", "top"]


def test_remove_layer_returns_whether_it_existed():
    stack = LayerStack(2, 2)
    stack.add_layer("base", "Base")
    assert stack.remove_layer("base") is True
    assert stack.remove_layer("base") is False
    assert stack.layers() == []


def test_reorder_layer_moves_by_id():
    stack = LayerStack(2, 2)
    stack.add_layer("a", "A")
    stack.add_layer("b", "B")
    stack.add_layer("c", "C")
    assert stack.reorder_layer("c", 0) is True
    assert [layer.meta.id for layer in stack.layers()] == ["c", "a", "b"]
    assert stack.reorder_layer("missing", 0) is False


def test_set_visibility_toggles_by_id():
    stack = LayerStack(2, 2)
    stack.add_layer("base", "Base")
    assert stack.set_visibility("base", False) is True
    assert stack.layer("base").meta.visible is False
    assert stack.set_visibility("missing", False) is False


def test_layer_stack_rejects_non_positive_dimensions():
    with pytest.raises(ValueError, match="positive"):
        LayerStack(0, 4)


def test_layer_meta_rejects_out_of_range_opacity():
    with pytest.raises(ValueError, match="opacity"):
        LayerMeta("base", "Base", opacity=1.5)


def test_layer_meta_rejects_unsupported_blend_mode():
    with pytest.raises(ValueError, match="blend mode"):
        LayerMeta("base", "Base", blend_mode="screen")


def test_layer_rejects_wrong_shaped_pixels():
    with pytest.raises(ValueError, match="HxWx4"):
        Layer(LayerMeta("base", "Base"), np.zeros((2, 2, 3), dtype=np.uint8))


def test_composite_of_empty_stack_is_fully_transparent():
    stack = LayerStack(2, 2)
    composite = stack.composite()
    assert composite.shape == (2, 2, 4)
    assert (composite[:, :, 3] == 0).all()


def test_composite_stacks_opaque_layers_top_wins():
    stack = LayerStack(1, 1)
    bottom = stack.add_layer("bottom", "Bottom")
    bottom.pixels[:, :, :] = [255, 0, 0, 255]
    top = stack.add_layer("top", "Top")
    top.pixels[:, :, :] = [0, 255, 0, 255]
    composite = stack.composite()
    assert composite[0, 0].tolist() == [0, 255, 0, 255]


def test_composite_skips_invisible_layers():
    stack = LayerStack(1, 1)
    hidden = stack.add_layer("hidden", "Hidden")
    hidden.pixels[:, :, :] = [0, 255, 0, 255]
    hidden.meta.visible = False
    visible = stack.add_layer("visible", "Visible")
    visible.pixels[:, :, :] = [255, 0, 0, 255]
    composite = stack.composite()
    assert composite[0, 0].tolist() == [255, 0, 0, 255]


def test_composite_blends_partial_opacity_with_transparent_base():
    stack = LayerStack(1, 1)
    layer = stack.add_layer("half", "Half")
    layer.pixels[:, :, :] = [200, 100, 50, 255]
    layer.meta.opacity = 0.5
    composite = stack.composite()
    assert composite[0, 0, 3] == pytest.approx(127, abs=1)
    # Straight-alpha "over" onto a transparent base keeps unpremultiplied RGB.
    assert composite[0, 0, :3].tolist() == [200, 100, 50]


def test_composite_multiply_darkens_beneath_and_leaves_white_unchanged():
    stack = LayerStack(1, 1)
    base = stack.add_layer("base", "Base")
    base.pixels[:, :, :] = [200, 100, 50, 255]
    line_art = stack.add_layer("line-art", "Line Art", index=1)
    line_art.meta.blend_mode = "multiply"
    line_art.pixels[:, :, :] = [255, 255, 255, 255]
    composite = stack.composite()
    assert composite[0, 0].tolist() == [200, 100, 50, 255]

    stack2 = LayerStack(1, 1)
    base2 = stack2.add_layer("base", "Base")
    base2.pixels[:, :, :] = [200, 100, 50, 255]
    ink = stack2.add_layer("ink", "Ink", index=1)
    ink.meta.blend_mode = "multiply"
    ink.pixels[:, :, :] = [0, 0, 0, 255]
    composite2 = stack2.composite()
    assert composite2[0, 0, :3].tolist() == [0, 0, 0]
