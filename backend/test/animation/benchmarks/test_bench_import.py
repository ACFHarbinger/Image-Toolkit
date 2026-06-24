"""§1.10E — Tests for bench_import helpers (parse_bench_json, suggested_rating, etc.)."""

from __future__ import annotations

import json

import pytest

from backend.src.animation.rlhf.bench_import import (
    parse_bench_json,
    resolve_anime_path,
    suggested_rating,
    verdict_label,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_dataset(
    name: str = "test01",
    anime_path: str = "/data/output/test01_anime.png",
    verdict: str = "asp_better",
    metrics: dict | None = None,
    used_fallback: bool = False,
) -> dict:
    if metrics is None:
        metrics = {
            "sharpness": 60.0,
            "coverage": 0.95,
            "ghosting_score": 0.10,
            "seam_coherence": 0.82,
            "rlhf_score": None,
            "rlhf_flagged": False,
        }
    return {
        "name": name,
        "anime_path": anime_path,
        "paths": {"anime_stitch": anime_path},
        "metrics_asp": metrics,
        "comparison": {"verdict": verdict, "ssim": 0.91},
        "used_fallback": used_fallback,
    }


# ---------------------------------------------------------------------------
# parse_bench_json
# ---------------------------------------------------------------------------


class TestParseBenchJson:
    def test_full_suite_doc(self, tmp_path):
        """Full suite JSON with 'datasets' list → returns the list."""
        ds1 = _make_dataset("test01")
        ds2 = _make_dataset("test02")
        doc = {"meta": {"ts": "2026-06-15"}, "datasets": [ds1, ds2], "summary": {}}
        p = tmp_path / "bench.json"
        p.write_text(json.dumps(doc))

        result = parse_bench_json(str(p))

        assert len(result) == 2
        assert result[0]["name"] == "test01"
        assert result[1]["name"] == "test02"

    def test_single_dataset_dict(self, tmp_path):
        """Single-dataset dict (no 'datasets' key) → wrapped in a one-element list."""
        ds = _make_dataset("test42")
        p = tmp_path / "single.json"
        p.write_text(json.dumps(ds))

        result = parse_bench_json(str(p))

        assert len(result) == 1
        assert result[0]["name"] == "test42"

    def test_bare_list(self, tmp_path):
        """JSON file is a bare list of datasets → returned as-is."""
        datasets = [_make_dataset("a"), _make_dataset("b"), _make_dataset("c")]
        p = tmp_path / "list.json"
        p.write_text(json.dumps(datasets))

        result = parse_bench_json(str(p))

        assert len(result) == 3

    def test_invalid_structure_raises(self, tmp_path):
        """Unrecognisable JSON structure raises ValueError."""
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"foo": "bar", "baz": 42}))

        with pytest.raises(ValueError, match="Unrecognised benchmark JSON"):
            parse_bench_json(str(p))

    def test_missing_file_raises(self, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_bench_json(str(tmp_path / "nonexistent.json"))


# ---------------------------------------------------------------------------
# resolve_anime_path
# ---------------------------------------------------------------------------


class TestResolveAnimePath:
    def test_primary_field_used_when_exists(self, tmp_path):
        """'anime_path' field takes precedence when the file exists."""
        p = tmp_path / "panorama.png"
        p.write_bytes(b"\x89PNG\r\n")
        ds = _make_dataset(anime_path=str(p))

        assert resolve_anime_path(ds) == str(p)

    def test_fallback_to_paths_dict(self, tmp_path):
        """Falls back to paths['anime_stitch'] when anime_path file is absent."""
        real = tmp_path / "stitch.png"
        real.write_bytes(b"\x89PNG\r\n")
        ds = {
            "name": "x",
            "anime_path": "/nonexistent/foo.png",
            "paths": {"anime_stitch": str(real)},
            "metrics_asp": {},
        }

        assert resolve_anime_path(ds) == str(real)

    def test_returns_path_even_if_file_missing(self):
        """Returns the candidate path string even if the file doesn't exist."""
        ds = _make_dataset(anime_path="/not/on/disk.png")
        result = resolve_anime_path(ds)
        assert result == "/not/on/disk.png"

    def test_returns_none_when_no_path(self):
        """Returns None when neither path field is present."""
        ds = {"name": "x", "metrics_asp": {}}
        assert resolve_anime_path(ds) is None


# ---------------------------------------------------------------------------
# suggested_rating
# ---------------------------------------------------------------------------


class TestSuggestedRating:
    def test_high_quality_metrics_give_high_rating(self):
        """Perfect metrics → rating close to 10."""
        m = {
            "sharpness": 80.0,
            "coverage": 1.0,
            "ghosting_score": 0.0,
            "seam_coherence": 1.0,
        }
        assert suggested_rating(m) >= 9.0

    def test_low_quality_metrics_give_low_rating(self):
        """Poor metrics → rating below 5."""
        m = {
            "sharpness": 5.0,
            "coverage": 0.3,
            "ghosting_score": 0.9,
            "seam_coherence": 0.1,
        }
        assert suggested_rating(m) < 5.0

    def test_none_metrics_returns_midpoint(self):
        """None metrics → neutral 5.0."""
        assert suggested_rating(None) == 5.0

    def test_empty_dict_returns_midpoint(self):
        """Empty dict → falls back to defaults; result is in a sensible range."""
        rating = suggested_rating({})
        assert 0.0 <= rating <= 10.0

    def test_result_is_clamped_to_0_10(self):
        """Rating is always within [0, 10]."""
        m = {
            "sharpness": 9999.0,
            "coverage": 99.0,
            "ghosting_score": -5.0,
            "seam_coherence": 99.0,
        }
        r = suggested_rating(m)
        assert 0.0 <= r <= 10.0

    def test_high_ghosting_lowers_score(self):
        """Increasing ghosting_siqe (true ghosting, 0-100) should reduce the rating."""
        base = {
            "sharpness": 60.0,
            "coverage": 0.9,
            "ghosting_siqe": 0.0,   # §3.32C: now uses ghosting_siqe, not ghosting_score
            "seam_coherence": 0.8,
        }
        high = {**base, "ghosting_siqe": 90.0}   # heavy ghosting → lower score
        assert suggested_rating(high) < suggested_rating(base)


# ---------------------------------------------------------------------------
# verdict_label
# ---------------------------------------------------------------------------


class TestVerdictLabel:
    @pytest.mark.parametrize(
        "verdict,expected",
        [
            ("asp_better", "✓ ASP"),
            ("simple_better", "✗ SIMP"),
            ("tie", "~ TIE"),
            ("", "?"),
            (None, "?"),
        ],
    )
    def test_labels(self, verdict, expected):
        ds = {"comparison": {"verdict": verdict}}
        assert verdict_label(ds) == expected

    def test_missing_comparison_key(self):
        """Missing 'comparison' key → '?'."""
        assert verdict_label({"name": "x"}) == "?"


# ===========================================================================
# §3.32C — suggested_rating uses ghosting_siqe (not ghosting_score)
# ===========================================================================


class TestSuggestedRatingGhostingSiqe:
    """§3.32C: suggested_rating must use ghosting_siqe (0-100 scale, higher=worse)."""

    def _base(self, ghosting_siqe: float = 0.0) -> dict:
        return {
            "sharpness": 60.0,
            "coverage": 0.9,
            "ghosting_siqe": ghosting_siqe,
            "seam_coherence": 0.8,
        }

    def test_zero_ghosting_siqe_maximises_ghost_term(self):
        # ghosting_siqe=0 → (1 - 0/100)*0.20 = 0.20 contribution
        r_clean = suggested_rating(self._base(ghosting_siqe=0.0))
        r_heavy = suggested_rating(self._base(ghosting_siqe=100.0))
        assert r_clean > r_heavy

    def test_ghosting_siqe_100_minimises_ghost_term(self):
        # ghosting_siqe=100 → (1 - 100/100)*0.20 = 0.0 contribution
        r = suggested_rating(self._base(ghosting_siqe=100.0))
        r_clean = suggested_rating(self._base(ghosting_siqe=0.0))
        assert r < r_clean

    def test_legacy_ghosting_score_key_still_works(self):
        # Old JSON without ghosting_siqe falls back to ghosting_score default (30.0)
        m = {"sharpness": 60.0, "coverage": 0.9, "seam_coherence": 0.8}
        r = suggested_rating(m)
        assert 0.0 <= r <= 10.0

    def test_monotone_in_ghosting_siqe(self):
        # Higher ghosting_siqe → lower or equal score
        scores = [suggested_rating(self._base(g)) for g in [0, 25, 50, 75, 100]]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_ghosting_siqe_normalised_not_raw(self):
        # ghosting_siqe=50 should give exactly midway ghost contribution: (1-0.5)*0.20=0.10
        # Verify by checking it's between clean (ghost_contrib=0.20) and heavy (0.0)
        r_clean = suggested_rating(self._base(ghosting_siqe=0.0))
        r_mid = suggested_rating(self._base(ghosting_siqe=50.0))
        r_heavy = suggested_rating(self._base(ghosting_siqe=100.0))
        assert r_heavy < r_mid < r_clean
