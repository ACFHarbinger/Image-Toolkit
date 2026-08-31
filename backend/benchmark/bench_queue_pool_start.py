"""Measure multiprocessing start-method overhead for extraction workers.

This is a controlled #485 microbenchmark, not a corpus run. It imports the
same CV/video/Qt modules as a queue worker, creates a small idle pool with
each available method, and reports start latency plus child USS (private RAM).
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import time

import cv2  # noqa: F401 -- intentionally mirrors queue-worker imports
import psutil
from moviepy.editor import VideoFileClip  # noqa: F401 -- queue-worker baseline
from PySide6.QtCore import QRunnable  # noqa: F401 -- queue-worker baseline


def _child_metrics(_index: int) -> tuple[int, int]:
    process = psutil.Process()
    memory = process.memory_full_info()
    return process.pid, int(getattr(memory, "uss", memory.rss))


def _measure(method: str, workers: int) -> dict[str, float | int | str]:
    context = multiprocessing.get_context(method)
    start = time.perf_counter()
    with context.Pool(processes=workers, maxtasksperchild=1) as pool:
        samples = pool.map(_child_metrics, range(workers))
    elapsed = time.perf_counter() - start
    uss_bytes = [sample[1] for sample in samples]
    return {
        "method": method,
        "workers": workers,
        "wall_seconds": round(elapsed, 3),
        "child_uss_mib_mean": round(sum(uss_bytes) / len(uss_bytes) / 1024**2, 1),
        "child_uss_mib_max": round(max(uss_bytes) / 1024**2, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    workers = max(1, min(args.workers, os.cpu_count() or 1))
    methods = [method for method in ("fork", "spawn") if method in multiprocessing.get_all_start_methods()]

    for method in methods:
        result = _measure(method, workers)
        print(
            f"{result['method']}: {result['workers']} workers, "
            f"{result['wall_seconds']}s start+idle, "
            f"USS mean/max {result['child_uss_mib_mean']}/{result['child_uss_mib_max']} MiB"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
