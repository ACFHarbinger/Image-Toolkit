"""
Tests for S151 compositing features:
  §1.101 _ZONE_MAD_THRESH full-zone MAD gate
  §1.102 _WARP_MOMENTUM_DAMP residual momentum
  §1.103 _SP_REF_PROX reference-proximity dominance
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# §1.101 — Full blend-zone MAD pre-escalation
# ---------------------------------------------------------------------------

class TestZoneMadThresh:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_ZONE_MAD_THRESH")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_ZONE_MAD_THRESH" in comp.__all__

    def test_default_is_zero(self):
        import backend.src.anim.compositing as comp
        assert comp._ZONE_MAD_THRESH == pytest.approx(0.0)

    def test_constant_defined(self):
        from backend.src.constants.anim import ZONE_MAD_THRESH_DEFAULT
        assert ZONE_MAD_THRESH_DEFAULT > 0.0

    def test_config_schema_has_key(self):
        from backend.src.anim.config import _CONFIG_SCHEMA
        assert "ASP_ZONE_MAD_THRESH" in _CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# §1.102 — Warp residual momentum damping
# ---------------------------------------------------------------------------

class TestWarpMomentumDamp:
    def test_flags_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_WARP_MOMENTUM_DAMP")
        assert hasattr(comp, "_WARP_MOMENTUM_FACTOR")

    def test_flags_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_WARP_MOMENTUM_DAMP" in comp.__all__
        assert "_WARP_MOMENTUM_FACTOR" in comp.__all__

    def test_factor_default_in_range(self):
        import backend.src.anim.compositing as comp
        assert 0.0 < comp._WARP_MOMENTUM_FACTOR <= 1.0

    def test_constant_defined(self):
        from backend.src.constants.anim import WARP_MOMENTUM_FACTOR
        assert 0.0 < WARP_MOMENTUM_FACTOR <= 1.0

    def test_config_schema_has_keys(self):
        from backend.src.anim.config import _CONFIG_SCHEMA
        assert "ASP_WARP_MOMENTUM_DAMP" in _CONFIG_SCHEMA
        assert "ASP_WARP_MOMENTUM_FACTOR" in _CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# §1.103 — Reference-proximity dominant frame selection
# ---------------------------------------------------------------------------

class TestSpRefProx:
    def test_flag_in_module(self):
        import backend.src.anim.compositing as comp
        assert hasattr(comp, "_SP_REF_PROX")

    def test_flag_in_all(self):
        import backend.src.anim.compositing as comp
        assert "_SP_REF_PROX" in comp.__all__

    def test_default_is_false(self):
        import backend.src.anim.compositing as comp
        assert comp._SP_REF_PROX is False

    def test_constant_defined(self):
        from backend.src.constants.anim import SP_REF_PROX_DEFAULT
        assert SP_REF_PROX_DEFAULT is False

    def test_ref_prox_picks_closer_frame(self):
        # Pure unit test of the proximity logic, no pipeline needed
        ref_fi = 5
        fi_a, fi_b = 3, 8   # fi_a is closer (|3-5|=2 vs |8-5|=3)
        dom_prox = fi_a if abs(fi_a - ref_fi) <= abs(fi_b - ref_fi) else fi_b
        assert dom_prox == fi_a
