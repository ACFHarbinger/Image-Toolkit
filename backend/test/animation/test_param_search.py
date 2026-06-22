"""Tests for §1.10B param_search.py — Bayesian ASP threshold search."""

import pytest

from backend.src.animation.param_search import (
    ASP_SEARCH_PARAMS,
    _score_config,
    _verdict_from_config,
)


def _default_cfg():
    return {
        name: default
        for name, (_, _lo, _hi, default, _desc) in ASP_SEARCH_PARAMS.items()
    }


def _make_result_data(datasets):
    return {"datasets": datasets}


def _cv_dataset(asp_m, sim_m):
    return {
        "comparison": {"verdict_source": "cv_metrics"},
        "metrics_asp": asp_m,
        "metrics_simple": sim_m,
    }


def _gt_dataset(asp_m, sim_m):
    return {
        "comparison": {"verdict_source": "ground_truth"},
        "metrics_asp": asp_m,
        "metrics_simple": sim_m,
    }


class TestVerdictFromConfig:
    def test_asp_better_when_clearly_higher_score(self):
        asp_m = {
            "coverage": 0.99,
            "seam_coherence": 5.0,
            "seam_gradient": 1.0,
            "ghosting_score": 5.0,
        }
        sim_m = {
            "coverage": 0.50,
            "seam_coherence": 20.0,
            "seam_gradient": 10.0,
            "ghosting_score": 30.0,
        }
        verdict = _verdict_from_config(asp_m, sim_m, _default_cfg())
        assert verdict == "asp_better"

    def test_simple_better_when_severe_banding(self):
        asp_m = {
            "seam_coherence": 40.0,
            "coverage": 0.9,
            "seam_gradient": 5.0,
            "ghosting_score": 10.0,
        }
        sim_m = {
            "seam_coherence": 20.0,
            "coverage": 0.9,
            "seam_gradient": 5.0,
            "ghosting_score": 10.0,
        }
        verdict = _verdict_from_config(asp_m, sim_m, _default_cfg())
        assert verdict == "simple_better"

    def test_comparable_when_scores_within_margin(self):
        asp_m = {
            "coverage": 0.80,
            "seam_coherence": 15.0,
            "seam_gradient": 5.0,
            "ghosting_score": 20.0,
        }
        sim_m = {
            "coverage": 0.80,
            "seam_coherence": 15.0,
            "seam_gradient": 5.0,
            "ghosting_score": 20.0,
        }
        verdict = _verdict_from_config(asp_m, sim_m, _default_cfg())
        assert verdict == "comparable"

    def test_insufficient_data_when_empty_metrics(self):
        verdict = _verdict_from_config({}, {}, _default_cfg())
        assert verdict == "insufficient_data"

    def test_custom_margin_changes_verdict(self):
        asp_m = {
            "coverage": 0.85,
            "seam_coherence": 12.0,
            "seam_gradient": 3.0,
            "ghosting_score": 15.0,
        }
        sim_m = {
            "coverage": 0.80,
            "seam_coherence": 14.0,
            "seam_gradient": 4.0,
            "ghosting_score": 18.0,
        }
        cfg_tight = {**_default_cfg(), "score_margin": 1.001}
        cfg_loose = {**_default_cfg(), "score_margin": 1.5}
        verdict_tight = _verdict_from_config(asp_m, sim_m, cfg_tight)
        verdict_loose = _verdict_from_config(asp_m, sim_m, cfg_loose)
        assert verdict_tight == "asp_better"
        assert verdict_loose == "comparable"


class TestScoreConfig:
    def test_gt_datasets_excluded_from_scoring(self):
        gt_ds = _gt_dataset(
            {
                "coverage": 0.95,
                "seam_coherence": 3.0,
                "seam_gradient": 1.0,
                "ghosting_score": 5.0,
            },
            {
                "coverage": 0.50,
                "seam_coherence": 30.0,
                "seam_gradient": 15.0,
                "ghosting_score": 40.0,
            },
        )
        result_data = _make_result_data([gt_ds])
        score = _score_config(_default_cfg(), result_data)
        assert score == 0.0  # GT dataset excluded

    def test_asp_better_contributes_2(self):
        cv_ds = _cv_dataset(
            {
                "coverage": 0.99,
                "seam_coherence": 3.0,
                "seam_gradient": 1.0,
                "ghosting_score": 2.0,
            },
            {
                "coverage": 0.40,
                "seam_coherence": 35.0,
                "seam_gradient": 20.0,
                "ghosting_score": 50.0,
            },
        )
        score = _score_config(_default_cfg(), _make_result_data([cv_ds]))
        assert score == 2.0

    def test_comparable_contributes_1(self):
        same_m = {
            "coverage": 0.80,
            "seam_coherence": 15.0,
            "seam_gradient": 5.0,
            "ghosting_score": 20.0,
        }
        cv_ds = _cv_dataset(same_m, same_m)
        score = _score_config(_default_cfg(), _make_result_data([cv_ds]))
        assert score == 1.0

    def test_simple_better_contributes_0(self):
        asp_m = {
            "coverage": 0.5,
            "seam_coherence": 40.0,
            "seam_gradient": 20.0,
            "ghosting_score": 50.0,
        }
        sim_m = {
            "coverage": 0.9,
            "seam_coherence": 8.0,
            "seam_gradient": 2.0,
            "ghosting_score": 5.0,
        }
        cv_ds = _cv_dataset(asp_m, sim_m)
        score = _score_config(_default_cfg(), _make_result_data([cv_ds]))
        assert score == 0.0

    def test_score_additive_across_multiple_datasets(self):
        good_asp = {
            "coverage": 0.99,
            "seam_coherence": 3.0,
            "seam_gradient": 1.0,
            "ghosting_score": 2.0,
        }
        bad_sim = {
            "coverage": 0.40,
            "seam_coherence": 35.0,
            "seam_gradient": 20.0,
            "ghosting_score": 50.0,
        }
        same_m = {
            "coverage": 0.80,
            "seam_coherence": 15.0,
            "seam_gradient": 5.0,
            "ghosting_score": 20.0,
        }
        datasets = [
            _cv_dataset(good_asp, bad_sim),  # asp_better → +2
            _cv_dataset(same_m, same_m),  # comparable → +1
            _cv_dataset(same_m, same_m),  # comparable → +1
        ]
        score = _score_config(_default_cfg(), _make_result_data(datasets))
        assert score == pytest.approx(4.0)
