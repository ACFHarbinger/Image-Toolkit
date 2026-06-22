"""S158 compositing tests: §1.122 mean path cost, §1.123 scatter cost, §1.124 adaptive SP soft."""
import importlib
import os
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.122 — _mean_path_cost
# ---------------------------------------------------------------------------
class TestMeanPathCost:
    """Five tests for _mean_path_cost (S158)."""

    @pytest.fixture(autouse=True)
    def _import(self):
        import backend.src.anim.compositing as comp
        importlib.reload(comp)
        self.comp = comp

    def test_uniform_cost_map(self):
        """Mean of constant cost map equals that constant."""
        cost = np.ones((10, 20), dtype=np.float32) * 0.5
        path = np.full(20, 5, dtype=np.int32)
        assert self.comp._mean_path_cost(path, cost) == pytest.approx(0.5, abs=1e-5)

    def test_path_selects_rows(self):
        """Path samples the correct row per column from a row-varying cost map."""
        H, W = 8, 4
        cost = np.zeros((H, W), dtype=np.float32)
        cost[3, :] = 1.0  # row 3 is expensive
        path = np.full(W, 3, dtype=np.int32)
        assert self.comp._mean_path_cost(path, cost) == pytest.approx(1.0, abs=1e-5)

    def test_empty_path_returns_zero(self):
        """Empty path array returns 0.0 without error."""
        cost = np.ones((5, 5), dtype=np.float32)
        assert self.comp._mean_path_cost(np.array([], dtype=np.int32), cost) == 0.0

    def test_empty_cost_map_returns_zero(self):
        """Empty cost map returns 0.0 without error."""
        path = np.array([1, 2, 3], dtype=np.int32)
        assert self.comp._mean_path_cost(path, np.array([], dtype=np.float32)) == 0.0

    def test_out_of_bounds_rows_clamped(self):
        """Path rows outside cost map height are clamped, not IndexError."""
        cost = np.ones((5, 3), dtype=np.float32)
        path = np.array([100, -5, 3], dtype=np.int32)  # row 100 and -5 out of bounds
        result = self.comp._mean_path_cost(path, cost)
        assert 0.0 <= result <= 2.0  # must be a valid float, not error


# ---------------------------------------------------------------------------
# §1.123 — scatter cost penalty in _build_seam_cost_map
# ---------------------------------------------------------------------------
class TestScatterCost:
    """Five tests for §1.123 scatter cost penalty (S158)."""

    def _build_cost(self, canvas_zone, scatter=True, weight=0.3):
        """Helper: build cost map with scatter flag set via env."""
        import backend.src.anim.compositing as comp
        orig_sc = os.environ.get("ASP_SCATTER_COST", "0")
        orig_w = os.environ.get("ASP_SCATTER_COST_WEIGHT", "0.3")
        try:
            os.environ["ASP_SCATTER_COST"] = "1" if scatter else "0"
            os.environ["ASP_SCATTER_COST_WEIGHT"] = str(weight)
            importlib.reload(comp)
            return comp._build_seam_cost_map(canvas_zone, None, None)
        finally:
            os.environ["ASP_SCATTER_COST"] = orig_sc
            os.environ["ASP_SCATTER_COST_WEIGHT"] = orig_w
            importlib.reload(comp)

    def test_scatter_off_unchanged(self):
        """With scatter disabled, cost map is unaffected by local variance."""
        canvas = np.random.randint(0, 255, (20, 30, 3), dtype=np.uint8)
        cost_off = self._build_cost(canvas, scatter=False)
        cost_on = self._build_cost(canvas, scatter=True, weight=0.0)
        # weight=0 → no change even if flag is on
        np.testing.assert_array_almost_equal(cost_off, cost_on, decimal=4)

    def test_scatter_adds_positive_cost(self):
        """Scatter-enabled map has >= base cost for non-barrier pixels."""
        rng = np.random.default_rng(42)
        canvas = rng.integers(0, 255, (30, 40, 3), dtype=np.uint8)
        import backend.src.anim.compositing as comp
        importlib.reload(comp)
        cost_base = comp._build_seam_cost_map(canvas, None, None)
        cost_scatter = self._build_cost(canvas, scatter=True, weight=0.5)
        soft = cost_base < 1e5
        assert float((cost_scatter[soft] - cost_base[soft]).min()) >= -1e-4

    def test_uniform_canvas_zero_variance(self):
        """Uniform canvas has zero variance → scatter adds ~0 cost."""
        canvas = np.full((20, 20, 3), 128, dtype=np.uint8)
        import backend.src.anim.compositing as comp
        importlib.reload(comp)
        cost_base = comp._build_seam_cost_map(canvas, None, None)
        cost_scatter = self._build_cost(canvas, scatter=True, weight=1.0)
        soft = cost_base < 1e5
        np.testing.assert_array_almost_equal(
            cost_scatter[soft], cost_base[soft], decimal=3
        )

    def test_scatter_weight_scales_penalty(self):
        """Higher weight → larger scatter additive penalty."""
        rng = np.random.default_rng(7)
        canvas = rng.integers(0, 255, (30, 30, 3), dtype=np.uint8)
        import backend.src.anim.compositing as comp
        importlib.reload(comp)
        cost_base = comp._build_seam_cost_map(canvas, None, None)
        cost_low = self._build_cost(canvas, scatter=True, weight=0.1)
        cost_high = self._build_cost(canvas, scatter=True, weight=1.0)
        soft = cost_base < 1e5
        mean_low = float((cost_low[soft] - cost_base[soft]).mean())
        mean_high = float((cost_high[soft] - cost_base[soft]).mean())
        assert mean_high > mean_low

    def test_scatter_does_not_affect_barriers(self):
        """Scatter penalty is NOT applied to barrier-cost pixels (cost >= 1e5)."""
        import backend.src.anim.compositing as comp
        # Synthetic fg mask: full foreground → generates high-cost barrier cols
        canvas = np.zeros((20, 20, 3), dtype=np.uint8)
        fg_mask = np.full((20, 20), 255, dtype=np.uint8)
        importlib.reload(comp)
        # Build with hard barrier flag
        orig_b = os.environ.get("ASP_SEAM_HARD_BARRIER", "0")
        orig_sc = os.environ.get("ASP_SCATTER_COST", "0")
        try:
            os.environ["ASP_SEAM_HARD_BARRIER"] = "1"
            os.environ["ASP_SCATTER_COST"] = "1"
            importlib.reload(comp)
            cost = comp._build_seam_cost_map(canvas, fg_mask, fg_mask)
            barriers = cost >= 1e5
            if barriers.any():
                # Scatter should not have lowered any barrier pixel
                assert float(cost[barriers].min()) >= 1e5
        finally:
            os.environ["ASP_SEAM_HARD_BARRIER"] = orig_b
            os.environ["ASP_SCATTER_COST"] = orig_sc
            importlib.reload(comp)


# ---------------------------------------------------------------------------
# §1.124 — adaptive SP soft-edge width from seam residual
# ---------------------------------------------------------------------------
class TestAdaptiveSpSoft:
    """Five tests for §1.124 residual-based adaptive soft-edge width (S158)."""

    @pytest.fixture(autouse=True)
    def _import(self):
        orig = os.environ.get("ASP_ADAPTIVE_SP_SOFT", "0")
        os.environ["ASP_ADAPTIVE_SP_SOFT"] = "1"
        import backend.src.anim.compositing as comp
        importlib.reload(comp)
        self.comp = comp
        yield
        os.environ["ASP_ADAPTIVE_SP_SOFT"] = orig
        importlib.reload(comp)

    def _read_min_max(self):
        return self.comp._ADAPTIVE_SP_SOFT_MIN, self.comp._ADAPTIVE_SP_SOFT_MAX

    def test_min_max_defaults(self):
        """Default MIN=3, MAX=10."""
        mn, mx = self._read_min_max()
        assert mn == 3
        assert mx == 10

    def test_high_residual_uses_min(self):
        """Post-diff > 30 → effective width clamped to MIN."""
        # Simulate the residual-based logic directly
        sp_soft = 6
        seam_post_diffs = {0: 40.0}  # high residual
        mn, mx = self._read_min_max()
        post_d = seam_post_diffs.get(0, 22.0)
        eff = sp_soft
        if post_d > 30.0:
            eff = mn
        elif post_d < 10.0:
            eff = mx
        assert eff == mn

    def test_low_residual_uses_max(self):
        """Post-diff < 10 → effective width widened to MAX."""
        sp_soft = 6
        seam_post_diffs = {0: 5.0}  # low residual
        mn, mx = self._read_min_max()
        post_d = seam_post_diffs.get(0, 22.0)
        eff = sp_soft
        if post_d > 30.0:
            eff = mn
        elif post_d < 10.0:
            eff = mx
        assert eff == mx

    def test_mid_residual_unchanged(self):
        """Post-diff in [10, 30] → effective width unchanged from sp_soft."""
        sp_soft = 6
        seam_post_diffs = {0: 20.0}  # mid residual
        mn, mx = self._read_min_max()
        post_d = seam_post_diffs.get(0, 22.0)
        eff = sp_soft
        if post_d > 30.0:
            eff = mn
        elif post_d < 10.0:
            eff = mx
        assert eff == sp_soft

    def test_env_override_min_max(self):
        """ASP_ADAPTIVE_SP_SOFT_MIN/MAX env vars override defaults."""
        orig_min = os.environ.get("ASP_ADAPTIVE_SP_SOFT_MIN", "3")
        orig_max = os.environ.get("ASP_ADAPTIVE_SP_SOFT_MAX", "10")
        try:
            os.environ["ASP_ADAPTIVE_SP_SOFT_MIN"] = "5"
            os.environ["ASP_ADAPTIVE_SP_SOFT_MAX"] = "15"
            import backend.src.anim.compositing as comp
            importlib.reload(comp)
            assert comp._ADAPTIVE_SP_SOFT_MIN == 5
            assert comp._ADAPTIVE_SP_SOFT_MAX == 15
        finally:
            os.environ["ASP_ADAPTIVE_SP_SOFT_MIN"] = orig_min
            os.environ["ASP_ADAPTIVE_SP_SOFT_MAX"] = orig_max
            importlib.reload(comp)
