import numpy as np
import pytest

from editor import stamp_dot, stamp_line


def _blank(width=10, height=10):
    return np.zeros((height, width, 4), dtype=np.uint8)


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
