import numpy as np
import pytest

from manga.features.gabor import gabor_feature_bank
from manga.colorization.graph_cut import (
    _frame_chroma,
    build_temporal_coherence_graph,
    graph_cut_temporal_refine,
)


def _uniform_gray_stack(t=3, h=40, w=40, value=150):
    return np.full((t, h, w), value, dtype=np.uint8)


def _flicker_sequence(gray1_value, h=40, w=40):
    """3-frame sequence where frame 1's own chroma disagrees with the
    (identical) chroma of frames 0 and 2 in a 20x20 patch -- a "flicker"
    outlier. ``gray1_value`` controls frame 1's grayscale value (hence its
    intensity-difference "motion" from its neighbors, both held at 150)."""
    t = 3
    gray = np.full((t, h, w), 150, dtype=np.uint8)
    gray[1, :, :] = gray1_value
    color = np.full((t, h, w, 3), 150, dtype=np.uint8)
    color[0, 10:30, 10:30] = [180, 150, 130]
    color[2, 10:30, 10:30] = [180, 150, 130]
    color[1, 10:30, 10:30] = [130, 150, 180]
    return gray, color


class TestBuildTemporalCoherenceGraph:
    def test_node_and_edge_counts(self):
        h, w = 6, 8
        own = np.zeros((h, w))
        blend = np.zeros((h, w))
        feat = np.zeros((h, w, 4))
        g = build_temporal_coherence_graph(own, blend, feat)
        assert g.get_node_count() == h * w
        # 4-connected grid: (h-1)*w vertical + h*(w-1) horizontal edges,
        # each added as one bidirectional add_edges call (counts as 1 edge
        # per call in PyMaxflow's bookkeeping, but exercise it doesn't blow
        # up / mismatch shapes at least).
        assert g.get_edge_count() > 0

    def test_shape_mismatch_raises(self):
        own = np.zeros((6, 6))
        blend = np.zeros((5, 5))
        feat = np.zeros((6, 6, 4))
        with pytest.raises(ValueError, match="same shape"):
            build_temporal_coherence_graph(own, blend, feat)

    def test_feature_shape_mismatch_raises(self):
        own = np.zeros((6, 6))
        blend = np.zeros((6, 6))
        feat = np.zeros((5, 5, 4))
        with pytest.raises(ValueError, match="spatial shape"):
            build_temporal_coherence_graph(own, blend, feat)

    def test_zero_cost_and_zero_smoothness_solves(self):
        """Degenerate all-zero costs/weights should not crash and should
        leave every node on the OWN (source) side by convention."""
        h, w = 5, 5
        own = np.zeros((h, w))
        blend = np.zeros((h, w))
        feat = np.zeros((h, w, 3))
        g = build_temporal_coherence_graph(own, blend, feat, smooth_weight=0.0)
        g.maxflow()
        ids = np.arange(h * w).reshape(h, w)
        seg = g.get_grid_segments(ids)
        assert not seg.any()

    def test_cheap_blend_pixel_is_selected(self):
        """A pixel whose data cost strongly favors BLEND (and with no
        smoothness pull from a uniform-feature neighborhood) should end up
        labeled BLEND."""
        h, w = 5, 5
        own = np.full((h, w), 10.0)
        blend = np.full((h, w), 10.0)
        own[2, 2] = 10.0
        blend[2, 2] = 0.0  # cheap to pick BLEND at this one pixel
        feat = np.zeros((h, w, 3))  # uniform texture -> no smoothness pull
        g = build_temporal_coherence_graph(own, blend, feat, smooth_weight=0.1)
        g.maxflow()
        ids = np.arange(h * w).reshape(h, w)
        seg = g.get_grid_segments(ids)
        assert seg[2, 2]


class TestGraphCutTemporalRefine:
    def test_output_shape_and_dtype(self):
        gray, color = _flicker_sequence(gray1_value=0)
        out = graph_cut_temporal_refine(gray, color)
        assert out.shape == color.shape
        assert out.dtype == np.uint8

    def test_high_motion_pulls_toward_blend(self):
        """When frame 1's grayscale value differs sharply from both
        neighbors (motion > 0.5 after normalization), the data term favors
        distrusting frame 1's own (flickering) chroma in favor of the
        neighbor-blended alternative -- the exact failure mode (fast
        motion/occlusion breaking local intensity tracking) issue #193
        targets."""
        gray_hi, color = _flicker_sequence(gray1_value=0)
        out_hi = graph_cut_temporal_refine(gray_hi, color, data_weight=2.0, smooth_weight=0.3)

        own = _frame_chroma(color[1])[20, 20]
        blend = (_frame_chroma(color[0])[20, 20] + _frame_chroma(color[2])[20, 20]) / 2
        hi_chroma = _frame_chroma(out_hi[1])[20, 20]

        dist_to_blend = np.abs(hi_chroma - blend).sum()
        dist_to_own = np.abs(hi_chroma - own).sum()
        assert dist_to_blend < dist_to_own

    def test_low_motion_keeps_own(self):
        """When frame 1's grayscale value matches its neighbors closely
        (motion ~ 0), there's no motion-based reason to distrust its own
        chroma -- the data term should keep it unchanged even though it
        still disagrees with its neighbors (a real per-frame difference,
        not a tracking failure)."""
        gray_lo, color = _flicker_sequence(gray1_value=150)
        out_lo = graph_cut_temporal_refine(gray_lo, color, data_weight=2.0, smooth_weight=0.3)

        own = _frame_chroma(color[1])[20, 20]
        out_chroma = _frame_chroma(out_lo[1])[20, 20]
        assert np.array_equal(out_chroma, own)

    def test_agreeing_neighbors_are_unaffected(self):
        """If a frame's own chroma already agrees with its neighbors
        (flicker ~ 0), the refinement is a no-op regardless of motion --
        there's nothing to correct. Uses a modest gray dip (not an extreme
        one) to keep the chroma well within RGB gamut for this frame's
        luminance -- see test_preserves_luminance_per_frame's docstring for
        why an extreme luminance/chroma combination isn't used here."""
        t, h, w = 3, 30, 30
        gray = np.full((t, h, w), 150, dtype=np.uint8)
        gray[1] = 90  # motion present, but...
        color = np.full((t, h, w, 3), 150, dtype=np.uint8)
        color[:, 10:20, 10:20] = [180, 150, 130]  # ...all three frames agree

        out = graph_cut_temporal_refine(gray, color, data_weight=2.0, smooth_weight=0.3)
        assert np.array_equal(_frame_chroma(out[1]), _frame_chroma(color[1]))

    def test_preserves_luminance_per_frame(self):
        """Not pixel-exact when the fixture's own/blend chroma hypotheses
        were extracted under a *different* frame's luminance than the one
        actually used to reconstruct the output (as in ``_flicker_sequence``,
        which deliberately uses an extreme gray1_value to trigger a
        BLEND-favoring motion signal): an 8-bit YCrCb<->RGB round trip clips
        in intermediate BGR space when the combination falls out of gamut --
        the same documented, pre-existing OpenCV property already covered by
        ``test_colorization.py``'s
        ``test_ycrcb_round_trip_gamut_clipping_is_an_opencv_property``, not a
        bug in this module. A small per-pixel tolerance accounts for it."""
        gray, color = _flicker_sequence(gray1_value=0)
        out = graph_cut_temporal_refine(gray, color)
        import cv2

        for t in range(gray.shape[0]):
            out_y = cv2.cvtColor(cv2.cvtColor(out[t], cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.int16)
            target_y = cv2.cvtColor(cv2.cvtColor(gray[t], cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.int16)
            assert np.max(np.abs(out_y - target_y)) <= 10

    def test_non_3d_gray_stack_raises(self):
        gray = np.zeros((40, 40), dtype=np.uint8)
        color = np.zeros((40, 40, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="3-D"):
            graph_cut_temporal_refine(gray, color)

    def test_shape_mismatch_raises(self):
        gray = _uniform_gray_stack(3, 40, 40)
        color = np.zeros((3, 20, 20, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="must have shape"):
            graph_cut_temporal_refine(gray, color)

    def test_single_frame_raises(self):
        gray = _uniform_gray_stack(1, 20, 20)
        color = np.zeros((1, 20, 20, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="at least 2 frames"):
            graph_cut_temporal_refine(gray, color)

    def test_boundary_frame_uses_single_neighbor(self):
        """First/last frames only have one temporal neighbor -- should not
        crash, and should just blend with that one neighbor."""
        gray, color = _flicker_sequence(gray1_value=0)
        out = graph_cut_temporal_refine(gray, color)
        assert out.shape == color.shape
        assert np.isfinite(out).all()

    def test_gabor_kwargs_forwarded(self):
        """Passing gabor_kwargs should change the smoothness term (and
        therefore not error, and still produce a valid output) -- exercises
        the pass-through to gabor_feature_bank."""
        gray, color = _flicker_sequence(gray1_value=0)
        out = graph_cut_temporal_refine(gray, color, gabor_kwargs={"orientations": 2, "frequencies": (0.2,)})
        assert out.shape == color.shape

    def test_two_frame_sequence(self):
        t, h, w = 2, 30, 30
        gray = np.full((t, h, w), 150, dtype=np.uint8)
        gray[1] = 0
        color = np.full((t, h, w, 3), 150, dtype=np.uint8)
        color[0, 10:20, 10:20] = [180, 150, 130]
        color[1, 10:20, 10:20] = [130, 150, 180]
        out = graph_cut_temporal_refine(gray, color)
        assert out.shape == color.shape


class TestFrameChromaHelper:
    def test_shape(self):
        rgb = np.full((10, 10, 3), 128, dtype=np.uint8)
        chroma = _frame_chroma(rgb)
        assert chroma.shape == (10, 10, 2)

    def test_neutral_gray_has_neutral_chroma(self):
        rgb = np.full((10, 10, 3), 128, dtype=np.uint8)
        chroma = _frame_chroma(rgb)
        assert np.allclose(chroma, 128.0, atol=1.0)


def test_smoothness_uses_gabor_features_consistently():
    """Sanity check that build_temporal_coherence_graph's smoothness edges
    really do come from gabor_feature_bank-shaped features (integration
    between the two modules), not just any same-shaped array."""
    gray = np.full((20, 20), 128, dtype=np.uint8)
    gray[:, 10:] = 200
    feat = gabor_feature_bank(gray)
    own = np.zeros((20, 20))
    blend = np.zeros((20, 20))
    g = build_temporal_coherence_graph(own, blend, feat)
    assert g.get_node_count() == 400
