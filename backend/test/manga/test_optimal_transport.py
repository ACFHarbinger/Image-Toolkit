import cv2
import numpy as np
import pytest

from backend.src.manga.optimal_transport import colorize_reference, sinkhorn


def _split_target(h=60, w=60, left_value=200, right_value=60):
    gray = np.full((h, w), left_value, dtype=np.uint8)
    gray[:, w // 2:] = right_value
    return gray


def _split_reference(h=60, w=60):
    # Moderately saturated (not fully saturated) so the YCrCb round-trip
    # used to preserve target luminance doesn't clip -- a fully-saturated
    # reference color combined with a bright/dark target luminance can fall
    # outside the legal RGB gamut, forcing a clip that perturbs Y itself.
    ref = np.zeros((h, w, 3), dtype=np.uint8)
    ref[:, : w // 2] = [210, 140, 140]
    ref[:, w // 2:] = [140, 140, 210]
    return ref


class TestSinkhorn:
    def test_output_shape(self):
        rng = np.random.default_rng(0)
        cost = rng.random((5, 7))
        mu = np.full(5, 1 / 5)
        nu = np.full(7, 1 / 7)
        plan = sinkhorn(cost, mu, nu)
        assert plan.shape == (5, 7)

    def test_marginals_are_approximately_satisfied(self):
        rng = np.random.default_rng(1)
        cost = rng.random((6, 6))
        mu = np.full(6, 1 / 6)
        nu = np.full(6, 1 / 6)
        plan = sinkhorn(cost, mu, nu, n_iter=500)
        assert np.allclose(plan.sum(axis=1), mu, atol=1e-3)
        assert np.allclose(plan.sum(axis=0), nu, atol=1e-3)

    def test_zero_cost_gives_uniform_plan(self):
        cost = np.zeros((4, 4))
        mu = np.full(4, 1 / 4)
        nu = np.full(4, 1 / 4)
        plan = sinkhorn(cost, mu, nu)
        assert np.allclose(plan, np.full((4, 4), 1 / 16), atol=1e-6)

    def test_finite_for_degenerate_marginals(self):
        cost = np.random.default_rng(2).random((3, 3))
        mu = np.array([1.0, 0.0, 0.0])
        nu = np.array([0.0, 1.0, 0.0])
        plan = sinkhorn(cost, mu, nu)
        assert np.isfinite(plan).all()


class TestColorizeReference:
    def test_output_shape_and_dtype(self):
        gray = _split_target()
        ref = _split_reference()
        out = colorize_reference(gray, ref, n_segments_target=30, n_segments_reference=30, max_solve_dim=0)
        assert out.shape == (60, 60, 3)
        assert out.dtype == np.uint8

    def test_color_propagates_toward_matching_structural_region(self):
        h, w = 60, 60
        gray = _split_target(h, w)
        ref = _split_reference(h, w)

        out = colorize_reference(gray, ref, n_segments_target=30, n_segments_reference=30, max_solve_dim=0)
        out_ycrcb = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb).astype(np.float64)

        left_cr = out_ycrcb[:, : w // 4, 1].mean()
        right_cr = out_ycrcb[:, 3 * w // 4:, 1].mean()
        left_cb = out_ycrcb[:, : w // 4, 2].mean()
        right_cb = out_ycrcb[:, 3 * w // 4:, 2].mean()
        # Left (matches reference's red region) should be more red-biased
        # (higher Cr, lower Cb); right (matches blue) the reverse.
        assert left_cr > right_cr
        assert right_cb > left_cb

    def test_preserves_target_luminance(self):
        gray = _split_target()
        ref = _split_reference()
        out = colorize_reference(gray, ref, n_segments_target=30, n_segments_reference=30, max_solve_dim=0)

        out_y = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb)[:, :, 0]
        target_y = cv2.cvtColor(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2YCrCb)[:, :, 0]
        assert np.array_equal(out_y, target_y)

    def test_non_2d_target_gray_raises(self):
        gray = np.zeros((10, 10, 3), dtype=np.uint8)
        ref = np.zeros((10, 10, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="2-D"):
            colorize_reference(gray, ref)

    def test_wrong_reference_shape_raises(self):
        gray = np.zeros((10, 10), dtype=np.uint8)
        ref = np.zeros((10, 10), dtype=np.uint8)
        with pytest.raises(ValueError, match="HxWx3"):
            colorize_reference(gray, ref)

    def test_downscaled_solve_runs_and_matches_full_resolution_bias(self):
        h, w = 80, 80
        gray = _split_target(h, w)
        ref = _split_reference(h, w)

        out = colorize_reference(gray, ref, n_segments_target=30, n_segments_reference=30, max_solve_dim=40)
        assert out.shape == (h, w, 3)

        out_ycrcb = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb).astype(np.float64)
        left_cr = out_ycrcb[:, : w // 4, 1].mean()
        right_cr = out_ycrcb[:, 3 * w // 4:, 1].mean()
        assert left_cr > right_cr

    def test_different_resolution_reference_is_handled(self):
        gray = _split_target(60, 60)
        ref = _split_reference(30, 45)
        out = colorize_reference(gray, ref, n_segments_target=20, n_segments_reference=20, max_solve_dim=0)
        assert out.shape == (60, 60, 3)
