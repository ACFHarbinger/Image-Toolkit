"""refs #654: ASP_DETERMINISTIC reseeds the RNGs the matcher samples from.

No GPU. The flag stays opt-in because it also pins Torch threads to 1 and
disables cuDNN autotune; these tests only check the seed contract.
"""

from __future__ import annotations

import random

import numpy as np
from middleware.src.stitching.alignment.matching._sampling import _sample_bg_points
from middleware.src.stitching.core.pipeline.manifest import (
    configure_reproducibility,
    reproducibility_snapshot,
)


def _restore_torch(saved: dict) -> None:
    torch = saved.get("torch")
    if torch is None:
        return
    torch.set_num_threads(saved["threads"])
    torch.backends.cudnn.deterministic = saved["deterministic"]
    torch.backends.cudnn.benchmark = saved["benchmark"]
    torch.use_deterministic_algorithms(saved["algorithms"], warn_only=True)


def _capture_torch() -> dict:
    try:
        import torch
    except Exception:
        return {"torch": None}
    return {
        "torch": torch,
        "threads": torch.get_num_threads(),
        "deterministic": bool(torch.backends.cudnn.deterministic),
        "benchmark": bool(torch.backends.cudnn.benchmark),
        "algorithms": bool(torch.are_deterministic_algorithms_enabled()),
    }


def test_deterministic_flag_repeats_background_samples(monkeypatch):
    monkeypatch.setenv("ASP_DETERMINISTIC", "1")
    monkeypatch.setenv("ASP_REPRO_SEED", "42")
    saved = _capture_torch()
    try:
        first = configure_reproducibility()
        samples_a = _sample_bg_points(None, 32, 32, n=24)
        py_a = [random.random() for _ in range(4)]
        second = configure_reproducibility()
        samples_b = _sample_bg_points(None, 32, 32, n=24)
        py_b = [random.random() for _ in range(4)]
    finally:
        _restore_torch(saved)
    assert first["requested"] is True and first["applied"] is True
    assert first["seed"] == 42 and second["seed"] == 42
    assert np.array_equal(samples_a, samples_b)
    assert py_a == py_b


def test_different_seeds_change_background_samples(monkeypatch):
    monkeypatch.setenv("ASP_DETERMINISTIC", "1")
    saved = _capture_torch()
    try:
        monkeypatch.setenv("ASP_REPRO_SEED", "42")
        configure_reproducibility()
        samples_a = _sample_bg_points(None, 32, 32, n=24)
        monkeypatch.setenv("ASP_REPRO_SEED", "99")
        configure_reproducibility()
        samples_b = _sample_bg_points(None, 32, 32, n=24)
    finally:
        _restore_torch(saved)
    assert not np.array_equal(samples_a, samples_b)


def test_flag_off_does_not_reseed(monkeypatch):
    monkeypatch.setenv("ASP_DETERMINISTIC", "0")
    configure_reproducibility()
    np.random.seed(0)
    first = _sample_bg_points(None, 32, 32, n=24)
    applied = configure_reproducibility()
    second = _sample_bg_points(None, 32, 32, n=24)
    assert applied["requested"] is False
    assert applied["applied"] is False
    assert not np.array_equal(first, second)


def test_snapshot_records_cublas_workspace_without_applying_it(monkeypatch):
    monkeypatch.setenv("ASP_DETERMINISTIC", "1")
    monkeypatch.setenv("ASP_REPRO_SEED", "42")
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setenv("PYTHONHASHSEED", "42")
    saved = _capture_torch()
    try:
        configure_reproducibility()
        snap = reproducibility_snapshot()
    finally:
        _restore_torch(saved)
    assert snap["requested"] is True
    assert snap["seed"] == 42
    assert snap["environment"]["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert snap["environment"]["PYTHONHASHSEED"] == "42"
    assert snap["numpy_random_seeded"] is True
    if saved["torch"] is not None:
        assert snap["cudnn_deterministic"] is True
        assert snap["cudnn_benchmark"] is False
        assert snap["deterministic_algorithms"] is True
