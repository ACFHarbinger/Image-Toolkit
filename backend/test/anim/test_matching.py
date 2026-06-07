"""
Tests for pairwise matching helpers — specifically the §1.3E similarity-mode
extraction function ``_extract_similarity``.

All tests use synthetic numpy matrices; no GPU or image files required.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.matching import _extract_similarity  # noqa: E402


# ---------------------------------------------------------------------------
# §1.3E — _extract_similarity
# ---------------------------------------------------------------------------


class TestExtractSimilarity:
    """
    _extract_similarity(M) projects a full 2×3 affine to the best-fit 4-DOF
    similarity [[a, b, tx], [-b, a, ty]].

    Closed-form:  a_sym = (M[0,0] + M[1,1]) / 2
                  b_sym = (M[0,1] - M[1,0]) / 2
    Translation terms are copied unchanged.
    """

    def _pure_translation(self, tx: float = 0.0, ty: float = 0.0) -> np.ndarray:
        M = np.eye(2, 3, dtype=np.float32)
        M[0, 2] = tx
        M[1, 2] = ty
        return M

    def _rotation_affine(self, theta_deg: float, tx: float = 0.0, ty: float = 0.0) -> np.ndarray:
        theta = math.radians(theta_deg)
        M = np.array([
            [math.cos(theta), -math.sin(theta), tx],
            [math.sin(theta),  math.cos(theta), ty],
        ], dtype=np.float32)
        return M

    def _scale_translation(self, scale: float, tx: float = 0.0, ty: float = 0.0) -> np.ndarray:
        M = np.array([
            [scale, 0.0, tx],
            [0.0, scale, ty],
        ], dtype=np.float32)
        return M

    def test_pure_translation_unchanged(self):
        """Identity rotation/scale → output matches input exactly."""
        M = self._pure_translation(tx=30.0, ty=120.0)
        out = _extract_similarity(M)
        assert out.shape == (2, 3)
        assert out[0, 0] == pytest.approx(1.0, abs=1e-5)
        assert out[0, 1] == pytest.approx(0.0, abs=1e-5)
        assert out[1, 0] == pytest.approx(0.0, abs=1e-5)
        assert out[1, 1] == pytest.approx(1.0, abs=1e-5)
        assert out[0, 2] == pytest.approx(30.0, abs=1e-4)
        assert out[1, 2] == pytest.approx(120.0, abs=1e-4)

    def test_rotation_preserved(self):
        """A pure rotation matrix → similarity projection recovers rotation terms exactly."""
        theta = 6.35
        M = self._rotation_affine(theta, tx=0.0, ty=200.0)
        out = _extract_similarity(M)
        # For a proper rotation: a=cos θ, b=-sin θ, c=sin θ, d=cos θ
        # a_sym = (a+d)/2 = cos θ; b_sym = (b-c)/2 = (-sin θ - sin θ)/2 = -sin θ
        expected_a = math.cos(math.radians(theta))
        expected_b = -math.sin(math.radians(theta))
        assert out[0, 0] == pytest.approx(expected_a, abs=1e-5)
        assert out[0, 1] == pytest.approx(expected_b, abs=1e-5)
        assert out[1, 0] == pytest.approx(-expected_b, abs=1e-5)
        assert out[1, 1] == pytest.approx(expected_a, abs=1e-5)
        assert out[0, 2] == pytest.approx(0.0, abs=1e-4)
        assert out[1, 2] == pytest.approx(200.0, abs=1e-4)

    def test_uniform_scale_preserved(self):
        """Uniform scale (s×I) → similarity output has a_sym=s, b_sym=0."""
        s = 1.121
        M = self._scale_translation(scale=s, tx=50.0, ty=300.0)
        out = _extract_similarity(M)
        assert out[0, 0] == pytest.approx(s, abs=1e-5)
        assert out[0, 1] == pytest.approx(0.0, abs=1e-5)
        assert out[1, 0] == pytest.approx(0.0, abs=1e-5)
        assert out[1, 1] == pytest.approx(s, abs=1e-5)
        assert out[0, 2] == pytest.approx(50.0, abs=1e-4)
        assert out[1, 2] == pytest.approx(300.0, abs=1e-4)

    def test_shear_component_eliminated(self):
        """A matrix with asymmetric off-diagonals (shear) → shear discarded, similarity kept.

        M = [[1, 0.3, 0], [0.1, 1, 0]] has shear (c=0.1 ≠ -b=-0.3).
        Symmetric: a_sym=(1+1)/2=1, b_sym=(0.3-0.1)/2=0.1.
        """
        M = np.array([[1.0, 0.3, 0.0], [0.1, 1.0, 0.0]], dtype=np.float32)
        out = _extract_similarity(M)
        assert out[0, 0] == pytest.approx(1.0, abs=1e-5)
        assert out[0, 1] == pytest.approx(0.1, abs=1e-5)   # b_sym = (0.3-0.1)/2
        assert out[1, 0] == pytest.approx(-0.1, abs=1e-5)  # -b_sym
        assert out[1, 1] == pytest.approx(1.0, abs=1e-5)

    def test_output_satisfies_similarity_constraint(self):
        """For any input M, the output must satisfy the similarity constraint:
        out[1, 0] == -out[0, 1] and out[1, 1] == out[0, 0].
        """
        rng = np.random.default_rng(42)
        for _ in range(20):
            M = rng.standard_normal((2, 3)).astype(np.float32)
            out = _extract_similarity(M)
            assert out[1, 0] == pytest.approx(-out[0, 1], abs=1e-5), (
                "Similarity constraint -b == c violated"
            )
            assert out[1, 1] == pytest.approx(out[0, 0], abs=1e-5), (
                "Similarity constraint a == d violated"
            )
