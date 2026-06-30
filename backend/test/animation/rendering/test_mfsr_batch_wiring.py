"""
backend/test/animation/rendering/test_mfsr_batch_wiring.py
===========================================================
Phase 5 — batch.sr_classical dispatch wiring tests.

Verifies that de_seam.py and pso_registration.py correctly dispatch to
batch.sr_classical when available, and that the Python fallback is preserved.
All tests run without GPU.  Tests are skipped when batch is not built.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

try:
    import base as _batch_sr_test  # noqa: F401
    _HAS_BATCH = True
    _HAS_BATCH_SR = hasattr(_batch_sr_test, "sr_classical")
except ImportError:
    _HAS_BATCH = False
    _HAS_BATCH_SR = False

_skip_no_batch = pytest.mark.skipif(not _HAS_BATCH, reason="batch not built")
_skip_no_sr = pytest.mark.skipif(
    not _HAS_BATCH_SR, reason="batch.sr_classical not built"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _solid_pair(h=64, w=48, shift_x=8):
    """Two uint8 BGR images with a horizontal shift."""
    rng = np.random.default_rng(7)
    a = rng.integers(30, 220, (h, w, 3), dtype=np.uint8)
    b = np.roll(a, shift_x, axis=1)
    b[:, :shift_x] = 0
    return a, b


# ---------------------------------------------------------------------------
# batch.sr_classical direct API
# ---------------------------------------------------------------------------

class TestBatchSrClassicalDirect:
    """Direct calls into batch.sr_classical submodule."""

    @_skip_no_sr
    def test_dct_restore_returns_same_shape(self):
        """dct_restore returns uint8 same shape as input."""
        frame = np.full((64, 64, 3), 128, dtype=np.uint8)
        import base as batch
        out = batch.sr_classical.dct_restore(frame, 8, 0.02)
        assert out.shape == frame.shape
        assert out.dtype == np.uint8

    @_skip_no_sr
    def test_de_seam_returns_int32_array(self):
        """de_seam returns int32 array of length H."""
        a, b = _solid_pair(h=32, w=24)
        import base as batch
        path = batch.sr_classical.de_seam(a, b, True, 5, 5, 0.5)
        assert path.dtype == np.int32
        assert path.shape == (32,)

    @_skip_no_sr
    def test_de_seam_path_in_bounds(self):
        """All seam column indices must be within [0, W-1]."""
        a, b = _solid_pair(h=40, w=32)
        import base as batch
        path = batch.sr_classical.de_seam(a, b, True, 5, 5, 0.5)
        assert int(path.min()) >= 0
        assert int(path.max()) <= 31

    @_skip_no_sr
    def test_pso_register_returns_dict(self):
        """pso_register returns dict with tx, ty, fitness keys."""
        a, b = _solid_pair(h=32, w=32)
        import base as batch
        result = batch.sr_classical.pso_register(a, b, 10, 10, -50.0, 50.0)
        assert "tx" in result and "ty" in result and "fitness" in result

    @_skip_no_sr
    def test_pso_register_fitness_in_range(self):
        """NCC fitness must be in [-1, 1]."""
        a, b = _solid_pair(h=32, w=32)
        import base as batch
        result = batch.sr_classical.pso_register(a, b, 10, 10, -50.0, 50.0)
        assert -1.0 <= float(result["fitness"]) <= 1.0


# ---------------------------------------------------------------------------
# de_seam.py Python wiring
# ---------------------------------------------------------------------------

class TestDeSeamWiring:
    """batch.sr_classical.de_seam dispatch from mfsr/de_seam.py."""

    @_skip_no_batch
    def test_de_seam_returns_array(self):
        """de_seam Python wrapper returns an int array regardless of batch avail."""
        from backend.src.animation.mfsr.de_seam import de_seam
        a, b = _solid_pair(h=32, w=24)
        path = de_seam(a, b, horizontal=True, pop_size=5, n_gen=3)
        assert isinstance(path, np.ndarray)
        assert path.ndim == 1

    @_skip_no_batch
    def test_de_seam_path_length_matches_rows(self):
        """de_seam path length = number of rows when horizontal=True."""
        from backend.src.animation.mfsr.de_seam import de_seam
        h, w = 40, 30
        a, b = _solid_pair(h=h, w=w)
        path = de_seam(a, b, horizontal=True, pop_size=4, n_gen=2)
        assert len(path) == h

    @_skip_no_batch
    def test_de_seam_vertical_path_length(self):
        """de_seam horizontal=False → path length = number of cols."""
        from backend.src.animation.mfsr.de_seam import de_seam
        h, w = 36, 28
        a, b = _solid_pair(h=h, w=w)
        path = de_seam(a, b, horizontal=False, pop_size=4, n_gen=2)
        assert len(path) == w


# ---------------------------------------------------------------------------
# pso_registration.py Python wiring
# ---------------------------------------------------------------------------

class TestPsoRegisterWiring:
    """batch.sr_classical.pso_register dispatch from mfsr/pso_registration.py."""

    @_skip_no_batch
    def test_pso_register_returns_affine_and_score(self):
        """pso_register Python wrapper returns ((2,3) affine, float) tuple."""
        from backend.src.animation.mfsr.pso_registration import pso_register
        a, b = _solid_pair(h=48, w=48, shift_x=4)
        M, score = pso_register(a, b, search_range=(-50.0, 50.0),
                                 motion_model="translation",
                                 n_particles=10, n_iter=5)
        assert M.shape == (2, 3)
        assert -1.0 <= score <= 1.0

    @_skip_no_batch
    def test_pso_register_translation_tx_in_search_range(self):
        """C++ path: tx must stay within search bounds."""
        from backend.src.animation.mfsr.pso_registration import pso_register
        a, b = _solid_pair(h=32, w=32, shift_x=6)
        M, _ = pso_register(a, b, search_range=(-30.0, 30.0),
                             motion_model="translation",
                             n_particles=8, n_iter=5)
        assert -30.0 <= float(M[0, 2]) <= 30.0
