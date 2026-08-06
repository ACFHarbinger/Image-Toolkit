import cv2
import numpy as np
import pytest

from manga.temporal import build_levin_system_3d, colorize_scribble_sequence


def _uniform_gray_stack(t=5, h=40, w=40, value=200):
    return np.full((t, h, w), value, dtype=np.uint8)


class TestBuildLevinSystem3D:
    def test_shape(self):
        y = np.random.default_rng(0).random((4, 10, 12))
        A = build_levin_system_3d(y)
        assert A.shape == (480, 480)

    def test_rows_sum_to_zero(self):
        y = np.random.default_rng(1).random((3, 8, 8))
        A = build_levin_system_3d(y)
        row_sums = np.asarray(A.sum(axis=1)).ravel()
        assert np.allclose(row_sums, 0.0, atol=1e-9)

    def test_uniform_volume_finite_weights(self):
        y = np.full((3, 6, 6), 0.5)
        A = build_levin_system_3d(y)
        assert np.isfinite(A.data).all()

    def test_single_frame_matches_more_neighbors_than_zero_t_rad(self):
        y = np.random.default_rng(2).random((3, 5, 5))
        A_t1 = build_levin_system_3d(y, win_rad=1, t_rad=1)
        A_t0 = build_levin_system_3d(y, win_rad=1, t_rad=0)
        # t_rad=0 means no cross-frame edges at all -- strictly fewer nonzeros.
        assert A_t1.nnz > A_t0.nnz


class TestColorizeScribbleSequence:
    def test_output_shape_and_dtype(self):
        t, h, w = 4, 40, 40
        gray = _uniform_gray_stack(t, h, w)
        scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
        mask = np.zeros((t, h, w), dtype=bool)
        scribble_rgb[0, 5:10, 5:10] = [255, 0, 0]
        mask[0, 5:10, 5:10] = True

        out = colorize_scribble_sequence(gray, scribble_rgb, mask, max_solve_dim=0)
        assert out.shape == (t, h, w, 3)
        assert out.dtype == np.uint8

    def test_color_interpolates_monotonically_across_frames(self):
        t, h, w = 5, 40, 40
        gray = _uniform_gray_stack(t, h, w)
        scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
        mask = np.zeros((t, h, w), dtype=bool)
        scribble_rgb[0, 15:20, 15:20] = [220, 40, 40]
        mask[0, 15:20, 15:20] = True
        scribble_rgb[t - 1, 15:20, 15:20] = [40, 40, 220]
        mask[t - 1, 15:20, 15:20] = True

        out = colorize_scribble_sequence(gray, scribble_rgb, mask, max_solve_dim=0)

        cr_by_frame = []
        for frame in range(t):
            ycrcb = cv2.cvtColor(cv2.cvtColor(out[frame], cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb)
            cr_by_frame.append(float(ycrcb[15:20, 15:20, 1].mean()))

        # Red-scribbled frame 0 has the highest Cr; blue-scribbled last frame
        # has the lowest; every frame in between should sit monotonically
        # between them -- confirms the color is actually propagating through
        # the temporal axis rather than each frame solving in isolation.
        assert all(cr_by_frame[i] >= cr_by_frame[i + 1] for i in range(t - 1))
        assert cr_by_frame[0] > cr_by_frame[-1]

    def test_unscribbled_frame_between_keyframes_is_not_left_uncolored(self):
        t, h, w = 3, 30, 30
        gray = _uniform_gray_stack(t, h, w)
        scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
        mask = np.zeros((t, h, w), dtype=bool)
        scribble_rgb[0, 10:15, 10:15] = [220, 40, 40]
        mask[0, 10:15, 10:15] = True
        scribble_rgb[2, 10:15, 10:15] = [220, 40, 40]
        mask[2, 10:15, 10:15] = True

        out = colorize_scribble_sequence(gray, scribble_rgb, mask, max_solve_dim=0)
        middle_ycrcb = cv2.cvtColor(cv2.cvtColor(out[1], cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb)
        # Middle frame has no scribble of its own but sits between two
        # identically-red-scribbled neighbors -- it should pick up red bias.
        assert middle_ycrcb[10:15, 10:15, 1].mean() > 128

    def test_no_scribbles_raises(self):
        gray = _uniform_gray_stack()
        scribble_rgb = np.zeros((5, 40, 40, 3), dtype=np.uint8)
        mask = np.zeros((5, 40, 40), dtype=bool)
        with pytest.raises(ValueError, match="no scribbled pixels"):
            colorize_scribble_sequence(gray, scribble_rgb, mask)

    def test_shape_mismatch_raises(self):
        gray = _uniform_gray_stack(5, 40, 40)
        scribble_rgb = np.zeros((5, 20, 20, 3), dtype=np.uint8)
        mask = np.zeros((5, 20, 20), dtype=bool)
        mask[0, 5, 5] = True
        with pytest.raises(ValueError, match="must match"):
            colorize_scribble_sequence(gray, scribble_rgb, mask)

    def test_non_3d_gray_stack_raises(self):
        gray = np.zeros((40, 40), dtype=np.uint8)
        scribble_rgb = np.zeros((40, 40, 3), dtype=np.uint8)
        mask = np.zeros((40, 40), dtype=bool)
        with pytest.raises(ValueError, match="3-D"):
            colorize_scribble_sequence(gray, scribble_rgb, mask)

    def test_single_frame_raises(self):
        gray = _uniform_gray_stack(1, 20, 20)
        scribble_rgb = np.zeros((1, 20, 20, 3), dtype=np.uint8)
        mask = np.zeros((1, 20, 20), dtype=bool)
        mask[0, 5, 5] = True
        with pytest.raises(ValueError, match="at least 2 frames"):
            colorize_scribble_sequence(gray, scribble_rgb, mask)

    def test_downscaled_solve_runs(self):
        t, h, w = 4, 60, 60
        gray = _uniform_gray_stack(t, h, w)
        scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
        mask = np.zeros((t, h, w), dtype=bool)
        scribble_rgb[0, 5:9, 5:9] = [255, 0, 0]
        mask[0, 5:9, 5:9] = True
        scribble_rgb[t - 1, 45:49, 45:49] = [0, 0, 255]
        mask[t - 1, 45:49, 45:49] = True

        out = colorize_scribble_sequence(gray, scribble_rgb, mask, max_solve_dim=30)
        assert out.shape == (t, h, w, 3)

    def test_tiny_scribble_degenerate_downscale_falls_back(self):
        t, h, w = 3, 100, 100
        gray = _uniform_gray_stack(t, h, w)
        scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
        mask = np.zeros((t, h, w), dtype=bool)
        scribble_rgb[0, 50, 50] = [255, 0, 0]
        mask[0, 50, 50] = True
        scribble_rgb[2, 50, 50] = [0, 0, 255]
        mask[2, 50, 50] = True

        out = colorize_scribble_sequence(gray, scribble_rgb, mask, max_solve_dim=5)
        assert out.shape == (t, h, w, 3)

    def test_preserves_luminance_per_frame(self):
        t, h, w = 3, 30, 30
        gray = _uniform_gray_stack(t, h, w, value=180)
        scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
        mask = np.zeros((t, h, w), dtype=bool)
        scribble_rgb[0, 10:15, 10:15] = [210, 140, 140]
        mask[0, 10:15, 10:15] = True
        scribble_rgb[2, 10:15, 10:15] = [140, 140, 210]
        mask[2, 10:15, 10:15] = True

        out = colorize_scribble_sequence(gray, scribble_rgb, mask, max_solve_dim=0)
        for frame in range(t):
            out_y = cv2.cvtColor(cv2.cvtColor(out[frame], cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb)[:, :, 0]
            target_y = cv2.cvtColor(cv2.cvtColor(gray[frame], cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2YCrCb)[:, :, 0]
            assert np.array_equal(out_y, target_y)
