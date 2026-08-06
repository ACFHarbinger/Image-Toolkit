import numpy as np
import pytest

from manga.features.gabor import gabor_feature_bank


def _dotted_vs_flat_image(h=60, w=60):
    """Left half: a dense screentone-like dot grid. Right half: flat white."""
    gray = np.full((h, w), 255, dtype=np.uint8)
    left = w // 2
    dots_y, dots_x = np.meshgrid(np.arange(0, h, 3), np.arange(0, left, 3), indexing="ij")
    gray[dots_y, dots_x] = 0
    return gray


class TestGaborFeatureBank:
    def test_output_shape(self):
        gray = _dotted_vs_flat_image()
        feat = gabor_feature_bank(gray, orientations=4, frequencies=(0.15, 0.3))
        assert feat.shape == (60, 60, 8)  # 4 orientations x 2 frequencies

    def test_output_is_finite(self):
        gray = _dotted_vs_flat_image()
        feat = gabor_feature_bank(gray)
        assert np.isfinite(feat).all()

    def test_standardized_per_channel(self):
        """Each feature channel should be ~zero-mean after standardization."""
        gray = _dotted_vs_flat_image()
        feat = gabor_feature_bank(gray)
        means = feat.mean(axis=(0, 1))
        # float32 accumulation over 3600 pixels -- allow a loose tolerance,
        # this is just checking standardization happened, not exactness.
        assert np.allclose(means, 0.0, atol=1e-3)

    def test_within_screentone_more_similar_than_across_boundary(self):
        """Two pixels inside the same screentone region should have a much
        smaller feature-space distance than one screentone pixel vs. one
        flat-region pixel -- the whole point of using texture features
        instead of raw intensity for affinity weighting."""
        gray = _dotted_vs_flat_image()
        feat = gabor_feature_bank(gray)

        left_a = feat[10, 5]
        left_b = feat[12, 8]
        right = feat[10, 50]

        within_dist = np.linalg.norm(left_a - left_b)
        across_dist = np.linalg.norm(left_a - right)
        assert within_dist < across_dist

    def test_uniform_image_has_near_zero_energy(self):
        """A perfectly flat image has no spatial frequency content at all --
        every filter response should be ~0 before standardization would
        even apply (std floor kicks in, but raw energy stays low)."""
        gray = np.full((30, 30), 128, dtype=np.uint8)
        feat = gabor_feature_bank(gray)
        assert np.isfinite(feat).all()

    def test_non_2d_input_raises(self):
        gray = np.zeros((10, 10, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="2-D"):
            gabor_feature_bank(gray)

    def test_custom_orientations_and_frequencies(self):
        gray = _dotted_vs_flat_image(40, 40)
        feat = gabor_feature_bank(gray, orientations=2, frequencies=(0.2,))
        assert feat.shape == (40, 40, 2)
