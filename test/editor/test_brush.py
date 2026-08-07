import numpy as np
import pytest

from editor import (
    erase_dot,
    erase_line,
    stamp_dot,
    stamp_dot_soft,
    stamp_line,
    stamp_line_soft,
    stamp_mask_dot,
    stamp_mask_line,
)


def _blank(width=10, height=10):
    return np.zeros((height, width, 4), dtype=np.uint8)


def _blank_mask(width=10, height=10):
    return np.zeros((height, width), dtype=np.uint8)


def test_stamp_dot_paints_a_filled_circle():
    pixels = _blank()
    stamp_dot(pixels, 5, 5, 2, (255, 0, 0, 255))
    assert pixels[5, 5].tolist() == [255, 0, 0, 255]
    assert pixels[5, 3].tolist() == [255, 0, 0, 255]  # within radius
    assert pixels[5, 2].tolist() == [0, 0, 0, 0]  # outside radius


def test_stamp_dot_radius_zero_paints_a_single_pixel():
    pixels = _blank()
    stamp_dot(pixels, 5, 5, 0, (0, 255, 0, 255))
    assert pixels[5, 5].tolist() == [0, 255, 0, 255]
    assert pixels[5, 4].tolist() == [0, 0, 0, 0]
    assert pixels[4, 5].tolist() == [0, 0, 0, 0]


def test_stamp_dot_clips_to_canvas_bounds():
    pixels = _blank(4, 4)
    stamp_dot(pixels, 0, 0, 2, (10, 20, 30, 255))
    assert pixels[0, 0].tolist() == [10, 20, 30, 255]


def test_stamp_dot_entirely_off_canvas_is_a_no_op():
    pixels = _blank(4, 4)
    stamp_dot(pixels, -10, -10, 1, (10, 20, 30, 255))
    assert (pixels == 0).all()


def test_stamp_dot_blends_partial_alpha_over_existing_color():
    pixels = _blank(1, 1)
    pixels[0, 0] = [0, 0, 0, 255]
    stamp_dot(pixels, 0, 0, 0, (255, 255, 255, 128))
    # Straight-alpha "over": ~50% white over black, opaque result.
    assert pixels[0, 0, 3] == 255
    assert 120 <= pixels[0, 0, 0] <= 135


def test_stamp_dot_rejects_wrong_shaped_pixels():
    with pytest.raises(ValueError, match="HxWx4"):
        stamp_dot(np.zeros((2, 2, 3), dtype=np.uint8), 0, 0, 1, (0, 0, 0, 255))


def test_stamp_dot_rejects_negative_radius():
    with pytest.raises(ValueError, match="radius"):
        stamp_dot(_blank(), 0, 0, -1, (0, 0, 0, 255))


def test_stamp_dot_rejects_malformed_color():
    with pytest.raises(ValueError, match="color"):
        stamp_dot(_blank(), 0, 0, 1, (0, 0, 0))
    with pytest.raises(ValueError, match="color"):
        stamp_dot(_blank(), 0, 0, 1, (0, 0, 0, 256))


def test_stamp_line_single_point_behaves_like_stamp_dot():
    a = _blank()
    stamp_line(a, 5, 5, 5, 5, 1, (255, 0, 0, 255))
    b = _blank()
    stamp_dot(b, 5, 5, 1, (255, 0, 0, 255))
    assert (a == b).all()


def test_stamp_line_paints_a_continuous_stroke_without_gaps():
    pixels = _blank(20, 20)
    stamp_line(pixels, 2, 10, 17, 10, 2, (255, 0, 0, 255))
    row = pixels[10, 2:18, 3]
    assert (row > 0).all()


def test_stamp_line_diagonal_reaches_both_endpoints():
    pixels = _blank(20, 20)
    stamp_line(pixels, 1, 1, 15, 15, 1, (0, 200, 0, 255))
    assert pixels[1, 1, 3] > 0
    assert pixels[15, 15, 3] > 0


def test_stamp_mask_dot_overwrites_to_intensity():
    mask = _blank_mask()
    mask[:, :] = 255
    stamp_mask_dot(mask, 5, 5, 1, 0)
    assert mask[5, 5] == 0
    assert mask[5, 3] == 255  # outside radius, untouched


def test_stamp_mask_dot_clips_to_bounds():
    mask = _blank_mask(4, 4)
    stamp_mask_dot(mask, 0, 0, 2, 200)
    assert mask[0, 0] == 200


def test_stamp_mask_dot_entirely_off_canvas_is_a_no_op():
    mask = _blank_mask(4, 4)
    stamp_mask_dot(mask, -10, -10, 1, 200)
    assert (mask == 0).all()


def test_stamp_mask_dot_rejects_wrong_shaped_buffer():
    with pytest.raises(ValueError, match="mask buffer"):
        stamp_mask_dot(_blank(), 0, 0, 1, 255)


def test_stamp_mask_dot_rejects_out_of_range_intensity():
    with pytest.raises(ValueError, match="intensity"):
        stamp_mask_dot(_blank_mask(), 0, 0, 1, 256)
    with pytest.raises(ValueError, match="intensity"):
        stamp_mask_dot(_blank_mask(), 0, 0, 1, -1)


def test_stamp_mask_line_single_point_behaves_like_stamp_mask_dot():
    a = _blank_mask()
    stamp_mask_line(a, 5, 5, 5, 5, 1, 200)
    b = _blank_mask()
    stamp_mask_dot(b, 5, 5, 1, 200)
    assert (a == b).all()


def test_stamp_mask_line_paints_a_continuous_stroke_without_gaps():
    mask = _blank_mask(20, 20)
    stamp_mask_line(mask, 2, 10, 17, 10, 2, 128)
    row = mask[10, 2:18]
    assert (row == 128).all()


def test_stamp_dot_soft_at_full_hardness_matches_stamp_dot():
    hard = _blank()
    stamp_dot(hard, 5, 5, 3, (255, 0, 0, 255))
    soft = _blank()
    stamp_dot_soft(soft, 5, 5, 3, (255, 0, 0, 255), hardness=1.0)
    assert (hard == soft).all()


def test_stamp_dot_soft_center_is_fully_opaque_edge_fades():
    pixels = _blank(21, 21)
    stamp_dot_soft(pixels, 10, 10, 8, (255, 0, 0, 255), hardness=0.0)
    assert pixels[10, 10].tolist() == [255, 0, 0, 255]  # center: full coverage
    edge_alpha = pixels[10, 17, 3]  # near the radius edge
    assert 0 < edge_alpha < 255  # partially transparent, not hard-edged
    assert pixels[10, 19].tolist() == [0, 0, 0, 0]  # outside radius: untouched


def test_stamp_dot_soft_hardness_widens_the_fully_opaque_core():
    pixels = _blank(21, 21)
    stamp_dot_soft(pixels, 10, 10, 8, (255, 0, 0, 255), hardness=0.75)
    assert pixels[10, 15].tolist() == [255, 0, 0, 255]  # within the hard core (0.75 * 8 = 6)
    assert 0 < pixels[10, 17, 3] < 255  # still fading between the core and the edge


def test_stamp_dot_soft_off_canvas_is_a_no_op():
    pixels = _blank(4, 4)
    stamp_dot_soft(pixels, -10, -10, 1, (10, 20, 30, 255), hardness=0.5)
    assert (pixels == 0).all()


def test_stamp_dot_soft_rejects_out_of_range_hardness():
    with pytest.raises(ValueError, match="hardness"):
        stamp_dot_soft(_blank(), 0, 0, 1, (0, 0, 0, 255), hardness=1.5)
    with pytest.raises(ValueError, match="hardness"):
        stamp_dot_soft(_blank(), 0, 0, 1, (0, 0, 0, 255), hardness=-0.1)


def test_stamp_line_soft_single_point_behaves_like_stamp_dot_soft():
    a = _blank()
    stamp_line_soft(a, 5, 5, 5, 5, 2, (0, 255, 0, 255), hardness=0.5)
    b = _blank()
    stamp_dot_soft(b, 5, 5, 2, (0, 255, 0, 255), hardness=0.5)
    assert (a == b).all()


def test_stamp_line_soft_paints_a_continuous_stroke():
    pixels = _blank(20, 20)
    stamp_line_soft(pixels, 2, 10, 17, 10, 2, (0, 0, 255, 255), hardness=0.5)
    row_alpha = pixels[10, 2:18, 3]
    assert (row_alpha > 0).all()


def _painted(width=10, height=10, color=(255, 0, 0, 255)):
    pixels = _blank(width, height)
    pixels[:, :] = color
    return pixels


def test_erase_dot_hard_clears_alpha_within_radius():
    pixels = _painted()
    erase_dot(pixels, 5, 5, 2, hardness=1.0)
    assert pixels[5, 5, 3] == 0
    assert pixels[5, 3, 3] == 0  # within radius
    assert pixels[5, 2, 3] == 255  # outside radius, untouched


def test_erase_dot_hard_leaves_rgb_untouched():
    pixels = _painted(color=(10, 20, 30, 255))
    erase_dot(pixels, 5, 5, 1, hardness=1.0)
    assert pixels[5, 5, :3].tolist() == [10, 20, 30]
    assert pixels[5, 5, 3] == 0


def test_erase_dot_soft_fades_the_edge():
    pixels = _painted(21, 21)
    erase_dot(pixels, 10, 10, 8, hardness=0.0)
    assert pixels[10, 10, 3] == 0  # center: fully erased
    edge_alpha = pixels[10, 17, 3]
    assert 0 < edge_alpha < 255  # partial erase near the edge
    assert pixels[10, 19, 3] == 255  # outside radius: untouched


def test_erase_dot_soft_partial_coverage_scales_alpha_proportionally():
    pixels = _blank(21, 21)
    pixels[:, :] = [1, 2, 3, 200]
    erase_dot(pixels, 10, 10, 8, hardness=0.0)
    edge_alpha = float(pixels[10, 17, 3])
    # A soft edge pixel's alpha should scale down by its own coverage
    # fraction, not jump straight to zero the way a hard erase would.
    assert 0 < edge_alpha < 200


def test_erase_dot_off_canvas_is_a_no_op():
    pixels = _painted(4, 4)
    erase_dot(pixels, -10, -10, 1, hardness=1.0)
    assert (pixels[:, :, 3] == 255).all()


def test_erase_dot_rejects_out_of_range_hardness():
    with pytest.raises(ValueError, match="hardness"):
        erase_dot(_blank(), 0, 0, 1, hardness=1.5)


def test_erase_line_single_point_behaves_like_erase_dot():
    a = _painted()
    erase_line(a, 5, 5, 5, 5, 2, hardness=1.0)
    b = _painted()
    erase_dot(b, 5, 5, 2, hardness=1.0)
    assert (a == b).all()


def test_erase_line_clears_a_continuous_stroke():
    pixels = _painted(20, 20)
    erase_line(pixels, 2, 10, 17, 10, 2, hardness=1.0)
    row_alpha = pixels[10, 2:18, 3]
    assert (row_alpha == 0).all()
