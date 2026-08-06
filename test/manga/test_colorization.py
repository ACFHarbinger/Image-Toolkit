import numpy as np
import pytest

from backend.src.manga.colorization import build_levin_system, colorize_scribble


def _uniform_gray(h=40, w=40, value=200):
    return np.full((h, w), value, dtype=np.uint8)


class TestBuildLevinSystem:
    def test_shape(self):
        y = np.random.default_rng(0).random((10, 12))
        A = build_levin_system(y)
        assert A.shape == (120, 120)

    def test_rows_sum_to_zero(self):
        """Every row is 1 (diagonal) minus normalized weights summing to 1
        across valid neighbors -- so an unconstrained row sums to exactly 0."""
        y = np.random.default_rng(1).random((8, 8))
        A = build_levin_system(y)
        row_sums = np.asarray(A.sum(axis=1)).ravel()
        assert np.allclose(row_sums, 0.0, atol=1e-9)

    def test_uniform_image_uniform_weights(self):
        """A perfectly uniform image has zero local variance everywhere, so
        weights fall back to a plain (1/win_len) average -- no NaN/inf."""
        y = np.full((6, 6), 0.5)
        A = build_levin_system(y)
        assert np.isfinite(A.data).all()


class TestColorizeScribble:
    def test_output_shape_and_dtype(self):
        gray = _uniform_gray()
        scribble_rgb = np.zeros((40, 40, 3), dtype=np.uint8)
        mask = np.zeros((40, 40), dtype=bool)
        scribble_rgb[5:10, 5:10] = [255, 0, 0]
        mask[5:10, 5:10] = True

        out = colorize_scribble(gray, scribble_rgb, mask)
        assert out.shape == (40, 40, 3)
        assert out.dtype == np.uint8

    def test_color_propagates_toward_scribble_regions(self):
        """Two differently-colored scribbles on a uniform-gray canvas should
        each bias their local neighborhood toward their own hue."""
        gray = _uniform_gray()
        scribble_rgb = np.zeros((40, 40, 3), dtype=np.uint8)
        mask = np.zeros((40, 40), dtype=bool)
        scribble_rgb[10:15, 5:10] = [255, 0, 0]
        mask[10:15, 5:10] = True
        scribble_rgb[25:30, 30:35] = [0, 0, 255]
        mask[25:30, 30:35] = True

        out = colorize_scribble(gray, scribble_rgb, mask)

        red_region = out[10:15, 5:10].astype(np.int32)
        blue_region = out[25:30, 30:35].astype(np.int32)
        # Red-scribbled area should be redder than blue-scribbled area, and
        # vice versa for blue -- direction check, not exact-value check
        # (Y is pinned to the gray line art, not the scribble, by design).
        assert red_region[:, :, 0].mean() > blue_region[:, :, 0].mean()
        assert blue_region[:, :, 2].mean() > red_region[:, :, 2].mean()

    def test_luminance_channel_approximately_preserved_from_grayscale(self):
        """Colorization only ever solves for chrominance -- luminance should
        stay very close to the input line art. Not pixel-exact: an 8-bit
        YCrCb<->RGB round trip clips in intermediate BGR space when solved
        chrominance pushes a pixel out of RGB gamut, which is a property of
        8-bit color-space conversion in general (verified separately below),
        not a solver bug -- so this allows a small per-pixel tolerance."""
        import cv2

        h, w = 30, 30
        # A modest, in-gamut scribble color minimizes gamut-clipping drift
        # so the tolerance below stays tight.
        gray = np.random.default_rng(2).integers(60, 200, size=(h, w), dtype=np.uint8)
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[10:15, 10:15] = [140, 160, 120]
        mask[10:15, 10:15] = True

        out = colorize_scribble(gray, scribble_rgb, mask, max_solve_dim=0)

        out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        out_y = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.int16)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        expected_y = cv2.cvtColor(gray_bgr, cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.int16)
        assert np.max(np.abs(out_y - expected_y)) <= 5

    def test_ycrcb_round_trip_gamut_clipping_is_an_opencv_property(self):
        """Documents the underlying cause of the tolerance above: OpenCV's
        8-bit YCrCb<->BGR conversion is not perfectly invertible when
        chrominance is far from neutral, independent of this module."""
        import cv2

        ycrcb = np.array([[[188, 10, 200]]], dtype=np.uint8)
        roundtrip = cv2.cvtColor(cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR), cv2.COLOR_BGR2YCrCb)
        assert roundtrip[0, 0, 0] != ycrcb[0, 0, 0]

    def test_no_scribbles_raises(self):
        gray = _uniform_gray()
        scribble_rgb = np.zeros((40, 40, 3), dtype=np.uint8)
        mask = np.zeros((40, 40), dtype=bool)
        with pytest.raises(ValueError, match="no scribbled pixels"):
            colorize_scribble(gray, scribble_rgb, mask)

    def test_shape_mismatch_raises(self):
        gray = _uniform_gray(40, 40)
        scribble_rgb = np.zeros((20, 20, 3), dtype=np.uint8)
        mask = np.zeros((20, 20), dtype=bool)
        mask[5, 5] = True
        with pytest.raises(ValueError, match="must match"):
            colorize_scribble(gray, scribble_rgb, mask)

    def test_non_2d_gray_raises(self):
        gray = np.zeros((10, 10, 3), dtype=np.uint8)
        scribble_rgb = np.zeros((10, 10, 3), dtype=np.uint8)
        mask = np.zeros((10, 10), dtype=bool)
        with pytest.raises(ValueError, match="2-D"):
            colorize_scribble(gray, scribble_rgb, mask)

    def test_downscaled_solve_matches_full_resolution_roughly(self):
        """max_solve_dim should produce a visually-consistent (if not
        pixel-identical) result to a full-resolution solve for a small image
        that's still above the cap."""
        h, w = 30, 30
        gray = _uniform_gray(h, w)
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[10:15, 5:10] = [255, 0, 0]
        mask[10:15, 5:10] = True
        scribble_rgb[20:25, 20:25] = [0, 0, 255]
        mask[20:25, 20:25] = True

        out_full = colorize_scribble(gray, scribble_rgb, mask, max_solve_dim=0)
        out_downscaled = colorize_scribble(gray, scribble_rgb, mask, max_solve_dim=15)

        # Same overall color bias in each scribble's neighborhood.
        assert out_full[12, 7][0] > out_full[12, 7][2]
        assert out_downscaled[12, 7][0] > out_downscaled[12, 7][2]

    def test_tiny_scribble_degenerate_downscale_falls_back(self):
        """A single-pixel scribble that would vanish under nearest-neighbor
        downsampling must fall back to a full-resolution solve instead of
        raising 'no scribbled pixels'."""
        h, w = 100, 100
        gray = _uniform_gray(h, w)
        scribble_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        mask = np.zeros((h, w), dtype=bool)
        scribble_rgb[50, 50] = [255, 0, 0]
        mask[50, 50] = True

        out = colorize_scribble(gray, scribble_rgb, mask, max_solve_dim=5)
        assert out.shape == (h, w, 3)
