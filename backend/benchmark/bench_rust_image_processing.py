"""Benchmark suite for Rust core image processing operations (via PyO3/base module).

Covers the hot paths most likely to be bottlenecks for large library workflows:
- load_image_batch (Rayon parallel decode)
- image conversion (format re-encode)
- scan_directory (recursive FS enumeration)
- merge_images (horizontal/vertical stacking)

Run standalone:
    python backend/benchmark/bench_rust_image_processing.py
or via the benchmark runner:
    python backend/benchmark/run_all.py --suite rust_image
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

# Ensure repo root on path so `base` Rust module is importable after `maturin develop`.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from backend.benchmark.utils import BenchmarkRunner, measure_memory  # noqa: E402

try:
    import base as rust_core  # type: ignore[import]
    _RUST_AVAILABLE = True
except ImportError:
    rust_core = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False


# ── Shared test fixtures (created once, reused across benchmarks) ─────────────

_TMP_DIR: tempfile.TemporaryDirectory | None = None
_PATHS_512_8: list[str] = []
_PATHS_512_32: list[str] = []
_PATHS_1080_8: list[str] = []
_OUT_DIR: Path | None = None


def _write_png_images(out: Path, count: int, width: int, height: int) -> list[str]:
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        print("WARNING: Pillow not installed — skipping PNG fixture generation.")
        return []

    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    paths: list[str] = []
    for i in range(count):
        arr = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(arr, "RGB")
        p = out / f"img_{i:04d}.png"
        img.save(p, format="PNG", optimize=False, compress_level=1)
        paths.append(str(p))
    return paths


def _setup() -> None:
    global _TMP_DIR, _PATHS_512_8, _PATHS_512_32, _PATHS_1080_8, _OUT_DIR
    _TMP_DIR = tempfile.TemporaryDirectory()
    root = Path(_TMP_DIR.name)
    _PATHS_512_8 = _write_png_images(root / "512_8", 8, 512, 512)
    _PATHS_512_32 = _write_png_images(root / "512_32", 32, 512, 512)
    _PATHS_1080_8 = _write_png_images(root / "1080_8", 8, 1920, 1080)
    _OUT_DIR = root / "out"
    _OUT_DIR.mkdir()


# ── Runner registration ───────────────────────────────────────────────────────

runner = BenchmarkRunner("Rust Image Processing")


@runner.benchmark("load_batch_512px_8images", iterations=5, warmup=1)
@measure_memory
def bench_load_batch_512_8() -> None:
    """Parallel decode of 8 × 512px PNGs via Rayon."""
    if not _RUST_AVAILABLE or not _PATHS_512_8:
        return
    rust_core.load_image_batch(_PATHS_512_8)


@runner.benchmark("load_batch_512px_32images", iterations=3, warmup=1)
@measure_memory
def bench_load_batch_512_32() -> None:
    """Parallel decode of 32 × 512px PNGs via Rayon."""
    if not _RUST_AVAILABLE or not _PATHS_512_32:
        return
    rust_core.load_image_batch(_PATHS_512_32)


@runner.benchmark("load_batch_1080p_8images", iterations=3, warmup=1)
@measure_memory
def bench_load_batch_1080_8() -> None:
    """Parallel decode of 8 × 1080p PNGs via Rayon."""
    if not _RUST_AVAILABLE or not _PATHS_1080_8:
        return
    rust_core.load_image_batch(_PATHS_1080_8)


@runner.benchmark("scan_directory_flat_200files", iterations=10, warmup=2)
@measure_memory
def bench_scan_flat() -> None:
    """Recursive FS scan over 200 files in a flat directory."""
    if not _RUST_AVAILABLE or _TMP_DIR is None:
        return
    rust_core.scan_directory(str(Path(_TMP_DIR.name) / "512_32"), recursive=False)


@runner.benchmark("scan_directory_recursive_multi_subdir", iterations=10, warmup=2)
@measure_memory
def bench_scan_recursive() -> None:
    """Recursive FS scan over all benchmark fixture subdirectories."""
    if not _RUST_AVAILABLE or _TMP_DIR is None:
        return
    rust_core.scan_directory(_TMP_DIR.name, recursive=True)


@runner.benchmark("convert_8x512px_to_webp", iterations=3, warmup=1)
@measure_memory
def bench_convert_512_webp() -> None:
    """Convert 8 × 512px PNG → WebP via Rust encoder."""
    if not _RUST_AVAILABLE or not _PATHS_512_8 or _OUT_DIR is None:
        return
    for p in _PATHS_512_8:
        rust_core.convert_image(p, str(_OUT_DIR), output_format="webp")


@runner.benchmark("convert_8x1080p_to_webp", iterations=3, warmup=1)
@measure_memory
def bench_convert_1080_webp() -> None:
    """Convert 8 × 1080p PNG → WebP via Rust encoder."""
    if not _RUST_AVAILABLE or not _PATHS_1080_8 or _OUT_DIR is None:
        return
    for p in _PATHS_1080_8:
        rust_core.convert_image(p, str(_OUT_DIR), output_format="webp")


@runner.benchmark("convert_8x512px_to_jpg", iterations=3, warmup=1)
@measure_memory
def bench_convert_512_jpg() -> None:
    """Convert 8 × 512px PNG → JPEG via Rust encoder."""
    if not _RUST_AVAILABLE or not _PATHS_512_8 or _OUT_DIR is None:
        return
    for p in _PATHS_512_8:
        rust_core.convert_image(p, str(_OUT_DIR), output_format="jpg")


@runner.benchmark("merge_images_vertical_8x512px", iterations=5, warmup=1)
@measure_memory
def bench_merge_vertical_512() -> None:
    """Vertical stack of 8 × 512px images via Rust."""
    if not _RUST_AVAILABLE or not _PATHS_512_8:
        return
    rust_core.merge_images(_PATHS_512_8, direction="vertical")


@runner.benchmark("merge_images_horizontal_8x1080p", iterations=3, warmup=1)
@measure_memory
def bench_merge_horizontal_1080() -> None:
    """Horizontal stack of 8 × 1080p images via Rust."""
    if not _RUST_AVAILABLE or not _PATHS_1080_8:
        return
    rust_core.merge_images(_PATHS_1080_8, direction="horizontal")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _RUST_AVAILABLE:
        print("ERROR: Rust base module not available.")
        print("       Run `maturin develop` inside the base/ directory first.")
        sys.exit(1)

    _setup()
    try:
        runner.run()
        runner.print_results()
        runner.save_json()
    finally:
        if _TMP_DIR is not None:
            _TMP_DIR.cleanup()
