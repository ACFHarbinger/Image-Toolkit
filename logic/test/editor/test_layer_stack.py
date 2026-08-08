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


def test_save_state_and_load_state_round_trip():
    stack = LayerStack(2, 2)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :, :] = [10, 20, 30, 255]
    layer.meta.opacity = 0.7
    layer.meta.blend_mode = "multiply"
    layer.meta.visible = False
    state = stack.save_state()

    stack.layer("base").pixels[:, :, :] = [255, 255, 255, 255]
    stack.add_layer("other", "Other")
    stack.load_state(state)

    restored = stack.layers()
    assert [layer.meta.id for layer in restored] == ["base"]
    assert restored[0].pixels.tolist() == [[[10, 20, 30, 255], [10, 20, 30, 255]]] * 2
    assert restored[0].meta.opacity == 0.7
    assert restored[0].meta.blend_mode == "multiply"
    assert restored[0].meta.visible is False


def test_save_state_is_a_deep_copy_not_a_live_view():
    stack = LayerStack(1, 1)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :, :] = [1, 2, 3, 255]
    state = stack.save_state()
    layer.pixels[:, :, :] = [9, 9, 9, 255]
    stack.load_state(state)
    assert stack.layer("base").pixels[0, 0].tolist() == [1, 2, 3, 255]


def test_add_mask_creates_a_fully_opaque_mask():
    stack = LayerStack(3, 2)
    stack.add_layer("base", "Base")
    assert stack.add_mask("base") is True
    mask = stack.layer("base").mask
    assert mask.shape == (2, 3)
    assert mask.dtype == np.uint8
    assert (mask == 255).all()


def test_add_mask_is_false_for_missing_layer_or_existing_mask():
    stack = LayerStack(2, 2)
    stack.add_layer("base", "Base")
    assert stack.add_mask("missing") is False
    assert stack.add_mask("base") is True
    assert stack.add_mask("base") is False


def test_remove_mask_clears_it():
    stack = LayerStack(2, 2)
    stack.add_layer("base", "Base")
    stack.add_mask("base")
    assert stack.remove_mask("base") is True
    assert stack.layer("base").mask is None
    assert stack.remove_mask("base") is False
    assert stack.remove_mask("missing") is False


def test_layer_rejects_mismatched_mask_shape():
    with pytest.raises(ValueError, match="mask"):
        Layer(
            LayerMeta("base", "Base"),
            np.zeros((2, 2, 4), dtype=np.uint8),
            np.zeros((3, 3), dtype=np.uint8),
        )


def test_composite_attenuates_alpha_by_mask():
    stack = LayerStack(1, 1)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :, :] = [255, 0, 0, 255]
    stack.add_mask("base")
    layer.mask[:, :] = 128
    composite = stack.composite()
    assert composite[0, 0, 3] == pytest.approx(128, abs=1)


def test_composite_fully_hides_layer_where_mask_is_zero():
    stack = LayerStack(1, 1)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :, :] = [255, 0, 0, 255]
    stack.add_mask("base")
    layer.mask[:, :] = 0
    composite = stack.composite()
    assert composite[0, 0, 3] == 0


def test_composite_without_a_mask_is_unaffected():
    stack = LayerStack(1, 1)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :, :] = [255, 0, 0, 255]
    composite = stack.composite()
    assert composite[0, 0].tolist() == [255, 0, 0, 255]


def test_save_state_and_load_state_round_trip_a_mask():
    stack = LayerStack(2, 2)
    layer = stack.add_layer("base", "Base")
    stack.add_mask("base")
    layer.mask[:, :] = 64
    state = stack.save_state()
    layer.mask[:, :] = 200
    stack.load_state(state)
    assert (stack.layer("base").mask == 64).all()


def test_save_state_round_trips_a_missing_mask_as_none():
    stack = LayerStack(2, 2)
    stack.add_layer("base", "Base")
    state = stack.save_state()
    stack.load_state(state)
    assert stack.layer("base").mask is None


def test_duplicate_layer_copies_pixels_metadata_and_mask_above_source():
    stack = LayerStack(2, 2)
    source = stack.add_layer("base", "Base")
    source.pixels[0, 1] = [1, 2, 3, 4]
    source.meta.visible = False
    source.meta.opacity = 0.4
    source.meta.blend_mode = "multiply"
    stack.add_mask("base")
    source.mask[0, 1] = 77

    duplicate = stack.duplicate_layer("base", "copy", "Base copy")

    assert duplicate is not None
    assert [layer.meta.id for layer in stack.layers()] == ["base", "copy"]
    assert duplicate.meta.visible is False
    assert duplicate.meta.opacity == 0.4
    assert duplicate.meta.blend_mode == "multiply"
    assert duplicate.pixels is not source.pixels
    assert duplicate.mask is not source.mask
    assert duplicate.pixels[0, 1].tolist() == [1, 2, 3, 4]
    assert duplicate.mask[0, 1] == 77


def test_rename_layer_updates_name_and_rejects_blank_names():
    stack = LayerStack(1, 1)
    stack.add_layer("base", "Base")
    assert stack.rename_layer("base", "Renamed")
    assert stack.layer("base").meta.name == "Renamed"
    with pytest.raises(ValueError, match="layer name"):
        stack.rename_layer("base", "   ")
    assert stack.rename_layer("missing", "Ignored") is False


def test_clear_layer_zeroes_pixels_and_mask_but_keeps_metadata():
    stack = LayerStack(2, 2)
    layer = stack.add_layer("base", "Base")
    layer.pixels[:, :] = [1, 2, 3, 4]
    stack.add_mask("base")
    layer.mask[:, :] = 77
    layer.meta.opacity = 0.4
    assert stack.clear_layer("base")
    assert (layer.pixels == 0).all()
    assert (layer.mask == 0).all()
    assert layer.meta.name == "Base"
    assert layer.meta.opacity == 0.4
    assert stack.clear_layer("missing") is False


def test_merge_down_flattens_selected_layer_and_removes_it():
    stack = LayerStack(1, 1)
    lower = stack.add_layer("lower", "Lower")
    lower.pixels[0, 0] = [255, 0, 0, 255]
    upper = stack.add_layer("upper", "Upper")
    upper.pixels[0, 0] = [0, 0, 255, 128]

    assert stack.merge_down("upper")
    assert [layer.meta.id for layer in stack.layers()] == ["lower"]
    assert stack.layer("lower").pixels[0, 0].tolist() == [127, 0, 128, 255]
    assert stack.layer("lower").mask is None
    assert stack.merge_down("lower") is False
