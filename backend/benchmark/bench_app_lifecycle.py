"""Benchmark suite for app lifecycle memory profiling (roadmap
development_tool.md §12.5, issue #70).

`backend/src/app.py::launch_app` now calls `lifecycle_memory.snapshot(phase)`
at `qt_init`, `login_window_shown`, and `main_window_shown` for every real
run of the app (see that file) — those three phases involve a real Qt event
loop, a real login (JVM start via `VaultManager`), and real user
credentials, none of which can be driven headlessly/safely from a benchmark
script. This file covers the phase §12.5's spec calls out that *can* be
measured in a controlled, repeatable way without any of that: "after
gallery load (100/500/1000 images)", via the same `base.load_image_batch()`
path `bench_gui_thumbnails.py` (§12.3) already benchmarks for raw
throughput — here the same calls are wrapped in `lifecycle_memory.snapshot()`
so the >200MB-per-phase alert logic gets exercised against real, not
synthetic, RSS deltas.

Run standalone:
    QT_QPA_PLATFORM=offscreen python backend/benchmark/bench_app_lifecycle.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend.benchmark.managers import BenchmarkManager  # noqa: E402
from backend.src.core import lifecycle_memory  # noqa: E402

try:
    import base as cpp_core  # type: ignore[import]

    _CPP_AVAILABLE = True
except ImportError:
    cpp_core = None  # type: ignore[assignment]
    _CPP_AVAILABLE = False

try:
    from PySide6.QtGui import QGuiApplication  # noqa: E402

    _QT_AVAILABLE = True
except ImportError:
    QGuiApplication = None  # type: ignore[assignment]
    _QT_AVAILABLE = False


_TMP_DIR: tempfile.TemporaryDirectory | None = None
_ALL_PATHS: list[str] = []
_QAPP = None
_THUMB_SIZE = 180


def _setup() -> None:
    global _TMP_DIR, _ALL_PATHS, _QAPP
    if not _CPP_AVAILABLE or not _QT_AVAILABLE:
        return
    _QAPP = QGuiApplication.instance() or QGuiApplication([])
    _TMP_DIR = tempfile.TemporaryDirectory(prefix="asp_lifecycle_bench_")
    rng = np.random.default_rng(3)
    for i in range(1000):
        arr = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
        path = os.path.join(_TMP_DIR.name, f"img_{i:04d}.png")
        import cv2

        cv2.imwrite(path, arr)
        _ALL_PATHS.append(path)


def _load_n(n: int) -> None:
    cpp_core.load_image_batch(
        _ALL_PATHS[:n], thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE, rgb=True
    )


runner = BenchmarkManager("App Lifecycle Memory Profiling")


@runner.benchmark("lifecycle_gallery_load_100", iterations=1, warmup=0)
def bench_gallery_load_100():
    if not _CPP_AVAILABLE or not _QT_AVAILABLE:
        return
    _load_n(100)
    lifecycle_memory.snapshot("after_gallery_load_100")


@runner.benchmark("lifecycle_gallery_load_500", iterations=1, warmup=0)
def bench_gallery_load_500():
    if not _CPP_AVAILABLE or not _QT_AVAILABLE:
        return
    _load_n(500)
    lifecycle_memory.snapshot("after_gallery_load_500")


@runner.benchmark("lifecycle_gallery_load_1000", iterations=1, warmup=0)
def bench_gallery_load_1000():
    if not _CPP_AVAILABLE or not _QT_AVAILABLE:
        return
    _load_n(1000)
    lifecycle_memory.snapshot("after_gallery_load_1000")


def _print_lifecycle_summary() -> None:
    print("\n" + "=" * 60)
    print("Lifecycle RSS history")
    print("=" * 60)
    for entry in lifecycle_memory.history():
        delta = entry["delta_mb"]
        delta_str = "baseline" if delta is None else f"Δ{delta:+.1f}MB"
        print(f"  {entry['phase']:<28} RSS={entry['rss_mb']:>8.1f}MB  {delta_str}")
    flagged = lifecycle_memory.alerts()
    if flagged:
        print(
            f"\n⚠️  {len(flagged)} phase(s) exceeded the "
            f"{lifecycle_memory.LIFECYCLE_RSS_ALERT_MB:.0f}MB alert threshold: "
            + ", ".join(e["phase"] for e in flagged)
        )
    else:
        print(
            f"\nNo phase exceeded the {lifecycle_memory.LIFECYCLE_RSS_ALERT_MB:.0f}MB "
            "alert threshold."
        )


if __name__ == "__main__":
    if not _CPP_AVAILABLE:
        print("ERROR: C++ base module not available.")
        sys.exit(1)
    if not _QT_AVAILABLE:
        print("WARNING: PySide6 not available — gallery-load benchmarks will no-op.")

    lifecycle_memory.reset()
    lifecycle_memory.snapshot("process_start")
    _setup()
    lifecycle_memory.snapshot("after_setup_fixtures")
    try:
        runner.run()
        runner.print_results()
        runner.save_json()
        _print_lifecycle_summary()
    finally:
        if _TMP_DIR is not None:
            _TMP_DIR.cleanup()
