import cv2
import numpy as np
import pytest

from backend.src.manga.screentone import build_texture_affinity_system, colorize_scribble_screentone


def _screentone_gray(h=60, w=60, dot_value=20, bg_value=240, pitch=4):
    gray = np.full((h, w), bg_value, dtype=np.uint8)
    gray[::pitch, ::pitch] = dot_value
    return gray


class TestBuildTextureAffinitySystem:
    def test_shape(self):
        features = np.random.default_rng(0).random((10, 12, 4))
        A = build_texture_affinity_system(features)
        assert A.shape == (120, 120)

    def test_rows_sum_to_zero(self):
        features = np.random.default_rng(1).random((8, 8, 4))
        A = build_texture_affinity_system(features)
        row_sums = np.asarray(A.sum(axis=1)).ravel()
        assert np.allclose(row_sums, 0.0, atol=1e-9)

    def test_identical_features_everywhere_gives_uniform_weights(self):
        """A constant feature map has zero pairwise distance everywhere, so
        every valid neighbor gets equal weight -- no NaN/inf, no bias."""
        features = np.zeros((6, 6, 3))
        A = build_texture_affinity_system(features)
        assert np.isfinite(A.data).all()


class TestColorizeScribbleScreentone:
    def test_output_shape_and_dtype(self):
        gray = _screentone_gray()
        scribble_rgb = np.zeros((60, 60, 3), dtype=np.uint8)
        mask = np.zeros((60, 60), dtype=bool)
        scribble_rgb[5:9, 5:9] = [255, 0, 0]
        mask[5:9, 5:9] = True

        out = colorize_scribble_screentone(gray, scribble_rgb, mask, max_solve_dim=0)
        assert out.shape == (60, 60, 3)
        assert out.dtype == np.uint8

    def test_color_propagates_toward_each_scribble_region(self):
        h, w = 60, 100
        gray = _screentone_gray(h, w)
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[10:15, 5:10] = [255, 0, 0]
        mask[10:15, 5:10] = True
        scribble_rgb[10:15, 85:90] = [0, 0, 255]
        mask[10:15, 85:90] = True

        out = colorize_scribble_screentone(gray, scribble_rgb, mask, max_solve_dim=0)
        out_ycrcb = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb)

        left_cr, left_cb = out_ycrcb[12, 20, 1], out_ycrcb[12, 20, 2]
        right_cr, right_cb = out_ycrcb[12, 70, 1], out_ycrcb[12, 70, 2]
        # Red-scribbled side: higher Cr, lower Cb. Blue-scribbled side: the reverse.
        assert int(left_cr) > int(right_cr)
        assert int(right_cb) > int(left_cb)

    def test_no_scribbles_raises(self):
        gray = _screentone_gray()
        scribble_rgb = np.zeros((60, 60, 3), dtype=np.uint8)
        mask = np.zeros((60, 60), dtype=bool)
        with pytest.raises(ValueError, match="no scribbled pixels"):
            colorize_scribble_screentone(gray, scribble_rgb, mask)

    def test_shape_mismatch_raises(self):
        gray = _screentone_gray(60, 60)
        scribble_rgb = np.zeros((20, 20, 3), dtype=np.uint8)
        mask = np.zeros((20, 20), dtype=bool)
        mask[5, 5] = True
        with pytest.raises(ValueError, match="must match"):
            colorize_scribble_screentone(gray, scribble_rgb, mask)

    def test_non_2d_gray_raises(self):
        gray = np.zeros((10, 10, 3), dtype=np.uint8)
        scribble_rgb = np.zeros((10, 10, 3), dtype=np.uint8)
        mask = np.zeros((10, 10), dtype=bool)
        with pytest.raises(ValueError, match="2-D"):
            colorize_scribble_screentone(gray, scribble_rgb, mask)

    def test_downscaled_solve_runs_and_matches_full_resolution_bias(self):
        h, w = 60, 60
        gray = _screentone_gray(h, w)
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[5:9, 5:9] = [255, 0, 0]
        mask[5:9, 5:9] = True
        scribble_rgb[45:49, 45:49] = [0, 0, 255]
        mask[45:49, 45:49] = True

        out = colorize_scribble_screentone(gray, scribble_rgb, mask, max_solve_dim=30)
        assert out.shape == (h, w, 3)

    def test_tiny_scribble_degenerate_downscale_falls_back(self):
        h, w = 100, 100
        gray = _screentone_gray(h, w)
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[50, 50] = [255, 0, 0]
        mask[50, 50] = True

        out = colorize_scribble_screentone(gray, scribble_rgb, mask, max_solve_dim=5)
        assert out.shape == (h, w, 3)
