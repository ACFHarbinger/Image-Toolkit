"""Correctness checks for committed deterministic benchmark goldens."""

import numpy as np

from benchmark.run_baseline import CASES, GOLDENS, TOLERANCES


def test_every_engine_area_matches_committed_golden():
    for name, function in CASES.items():
        result = function()
        golden = np.load(GOLDENS / f"{name}.npy")
        difference = np.abs(result.astype(np.float64) - golden.astype(np.float64))
        assert result.shape == golden.shape
        assert difference.mean() <= TOLERANCES[name]["mean"]
        assert difference.max() <= TOLERANCES[name]["maximum"]
