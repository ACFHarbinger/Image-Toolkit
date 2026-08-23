import pytest

from gui.src.theming.resolve import base_defaults
from gui.src.theming.validate import contrast_ratio, contrast_warnings


class TestContrastRatio:
    def test_identical_colors_ratio_is_one(self):
        assert contrast_ratio("#808080", "#808080") == 1.0

    def test_black_on_white_is_max_ratio(self):
        ratio = contrast_ratio("#000000", "#ffffff")
        assert 20.9 < ratio < 21.1  # WCAG-defined max is 21:1

    def test_symmetric(self):
        assert contrast_ratio("#123456", "#abcdef") == contrast_ratio("#abcdef", "#123456")


class TestContrastWarnings:
    def test_shipped_dark_theme_defaults_real_gaps(self):
        # Real finding, not a test bug: the shipped dark theme has two
        # pairs under WCAG AA -- muted_text/surface (~3.87:1, mild) and
        # border/surface (~1.28:1, this design's border is intentionally
        # subtle rather than a hard line, but still worth surfacing).
        # Pinned exactly so a future change to the shipped defaults
        # notices if it moves, without asserting a false "already
        # perfect" baseline.
        warnings = contrast_warnings(base_defaults("dark"))
        by_pair = {(w.token_a, w.token_b): w.ratio for w in warnings}
        assert set(by_pair) == {("muted_text", "surface"), ("border", "surface")}
        assert by_pair[("muted_text", "surface")] == pytest.approx(3.873, abs=0.01)
        assert by_pair[("border", "surface")] == pytest.approx(1.284, abs=0.01)

    def test_shipped_light_theme_defaults_real_gaps(self):
        warnings = contrast_warnings(base_defaults("light"))
        by_pair = {(w.token_a, w.token_b): w.ratio for w in warnings}
        assert set(by_pair) == {("accent", "window_bg"), ("border", "surface")}
        assert by_pair[("accent", "window_bg")] == pytest.approx(3.685, abs=0.01)
        assert by_pair[("border", "surface")] == pytest.approx(1.606, abs=0.01)

    def test_low_contrast_pair_flagged(self):
        from gui.src.theming.schema import ColorTokens

        low_contrast = ColorTokens(
            accent="#808080", surface="#7f7f7f", window_bg="#808080",
            text="#828282", muted_text="#7d7d7d", border="#818181",
        )
        warnings = contrast_warnings(low_contrast)
        assert len(warnings) > 0
        assert all(w.ratio < w.minimum for w in warnings)
        # message names the affected token pair (Harbinger's round-2 answer)
        assert "text" in warnings[0].message or "window_bg" in warnings[0].message

    def test_advisory_never_raises(self):
        # This function must never raise/block -- "warnings only" per
        # Harbinger's answer. Calling it on a deliberately bad palette
        # must just return warnings, not throw.
        from gui.src.theming.schema import ColorTokens

        bad = ColorTokens(
            accent="#000000", surface="#000000", window_bg="#000000",
            text="#010101", muted_text="#020202", border="#030303",
        )
        warnings = contrast_warnings(bad)  # must not raise
        assert len(warnings) == 6  # every pair checked fails
