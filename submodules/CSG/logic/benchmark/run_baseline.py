#!/usr/bin/env python3
"""Run deterministic correctness/performance baselines for the Python engine."""

from __future__ import annotations

import argparse
import json
import platform
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from colorization.colorization import colorize_scribble
from colorization.optimal_transport import colorize_reference
from execution import JobRequest, Operation, PersistentIsolatedRunner
from rigging.arap import arap_deform, generate_mesh
from temporal.temporal import colorize_scribble_sequence

ROOT = Path(__file__).resolve().parent
GOLDENS = ROOT / "goldens"


def _scribble() -> np.ndarray:
    gray = np.tile(np.linspace(55, 210, 48, dtype=np.uint8), (48, 1))
    colors = np.zeros((48, 48, 3), dtype=np.uint8)
    mask = np.zeros((48, 48), dtype=bool)
    colors[10:15, 7:12], colors[33:38, 36:41] = (210, 60, 60), (60, 80, 210)
    mask[10:15, 7:12] = mask[33:38, 36:41] = True
    return colorize_scribble(gray, colors, mask, max_solve_dim=0)


def _reference() -> np.ndarray:
    gray = np.full((48, 48), 190, dtype=np.uint8)
    gray[:, 24:] = 70
    reference = np.zeros((48, 48, 3), dtype=np.uint8)
    reference[:, :24], reference[:, 24:] = (205, 135, 135), (135, 145, 205)
    return colorize_reference(
        gray, reference, n_segments_target=24, n_segments_reference=24, max_solve_dim=0
    )


def _temporal() -> np.ndarray:
    gray = np.full((3, 32, 32), 170, dtype=np.uint8)
    colors = np.zeros((3, 32, 32, 3), dtype=np.uint8)
    mask = np.zeros((3, 32, 32), dtype=bool)
    colors[0, 10:14, 10:14], colors[2, 18:22, 18:22] = (210, 60, 60), (60, 80, 210)
    mask[0, 10:14, 10:14] = mask[2, 18:22, 18:22] = True
    return colorize_scribble_sequence(gray, colors, mask, max_solve_dim=0)


def _arap() -> np.ndarray:
    mask = np.zeros((80, 80), dtype=bool)
    mask[10:70, 10:70] = True
    vertices, triangles = generate_mesh(mask, grid_step=10)
    return arap_deform(vertices, triangles, {0: tuple(vertices[0] + (8, -3))}, n_iters=8)


def _isolation_overhead() -> dict[str, float]:
    mask = np.zeros((80, 80), dtype=bool)
    mask[10:70, 10:70] = True
    vertices, triangles = generate_mesh(mask, grid_step=10)
    request = JobRequest(
        Operation.ARAP_DEFORM,
        {
            "vertices": vertices,
            "triangles": triangles,
            "anchors": {0: tuple(vertices[0] + (8, -3))},
        },
        {"n_iters": 8},
    )
    runner = PersistentIsolatedRunner(diagnostics_enabled=False)
    try:
        started = time.perf_counter()
        runner.run(request)
        cold = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        runner.run(request)
        warm = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        arap_deform(vertices, triangles, {0: tuple(vertices[0] + (8, -3))}, n_iters=8)
        direct = (time.perf_counter() - started) * 1000
        return {
            "cold_ms": cold,
            "warm_ms": warm,
            "direct_ms": direct,
            "warm_overhead_ms": warm - direct,
        }
    finally:
        runner.close()


CASES: dict[str, Callable[[], np.ndarray]] = {
    "scribble_colorization": _scribble,
    "reference_colorization": _reference,
    "temporal_propagation": _temporal,
    "arap_deformation": _arap,
}
TOLERANCES = {
    "scribble_colorization": {"mean": 0.25, "maximum": 2.0},
    "reference_colorization": {"mean": 0.25, "maximum": 2.0},
    "temporal_propagation": {"mean": 0.25, "maximum": 2.0},
    "arap_deformation": {"mean": 1e-6, "maximum": 1e-5},
}


def _golden_path(name: str) -> Path:
    return GOLDENS / f"{name}.npy"


def _measure(function: Callable[[], np.ndarray], repeats: int) -> tuple[np.ndarray, dict[str, Any]]:
    function()  # warm-up
    timings = []
    tracemalloc.start()
    result = function()
    for _ in range(repeats):
        start = time.perf_counter()
        result = function()
        timings.append((time.perf_counter() - start) * 1000)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {
        "median_ms": float(np.median(timings)),
        "minimum_ms": min(timings),
        "peak_python_memory_mib": peak / (1024 * 1024),
        "repeats": repeats,
    }


def run(repeats: int, update_goldens: bool, hardware_class: str) -> dict[str, Any]:
    """Run every baseline and return a machine-readable report."""
    GOLDENS.mkdir(exist_ok=True)
    cases = {}
    for name, function in CASES.items():
        result, metrics = _measure(function, repeats)
        golden_path = _golden_path(name)
        if update_goldens:
            np.save(golden_path, result)
        golden = np.load(golden_path)
        difference = np.abs(result.astype(np.float64) - golden.astype(np.float64))
        tolerance = TOLERANCES[name]
        metrics["correctness"] = {
            "shape_matches": result.shape == golden.shape,
            "mean_absolute_error": float(difference.mean()),
            "maximum_absolute_error": float(difference.max()),
            "mean_tolerance": tolerance["mean"],
            "maximum_tolerance": tolerance["maximum"],
            "passed": result.shape == golden.shape
            and float(difference.mean()) <= tolerance["mean"]
            and float(difference.max()) <= tolerance["maximum"],
        }
        cases[name] = metrics
    return {
        "schema_version": 1,
        "environment": {
            "os_class": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(),
            "hardware_class": hardware_class,
        },
        "cases": cases,
        "isolation_overhead": _isolation_overhead(),
        "all_correct": all(case["correctness"]["passed"] for case in cases.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--hardware-class", default="CPU-only / unspecified GPU")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "latest.json")
    parser.add_argument("--update-goldens", action="store_true")
    args = parser.parse_args()
    report = run(args.repeats, args.update_goldens, args.hardware_class)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_correct"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
