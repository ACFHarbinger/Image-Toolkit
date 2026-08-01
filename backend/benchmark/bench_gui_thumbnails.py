"""Benchmark suite for GUI thumbnail loading (roadmap analytics_and_interpretability.md §12.3).

Covers the paths behind gallery scrolling performance:
- base.load_image_batch() at gallery-relevant scales (100/500/1000 images)
- LRUImageCache hit vs miss path
- QImage vs QPixmap in-memory footprint for 180px thumbnails

Requires QT_QPA_PLATFORM=offscreen (no real display needed/used) per this
project's GUI-benchmark convention -- never instantiates a visible window.

Run standalone:
    QT_QPA_PLATFORM=offscreen python backend/benchmark/bench_gui_thumbnails.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

# Ensure repo root on path so `base` C++ module and `gui` package are importable.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend.benchmark.managers import BenchmarkManager, measure_memory  # noqa: E402

try:
    import base as cpp_core  # type: ignore[import]
    _CPP_AVAILABLE = True
except ImportError:
    cpp_core = None  # type: ignore[assignment]
    _CPP_AVAILABLE = False

try:
    from PySide6.QtGui import QGuiApplication, QImage, QPixmap  # noqa: E402

    _QT_AVAILABLE = True
except ImportError:
    QGuiApplication = QImage = QPixmap = None  # type: ignore[assignment]
    _QT_AVAILABLE = False

from gui.src.utils.cache.lru_image_cache import LRUImageCache  # noqa: E402


# ── Shared test fixtures (created once, reused across benchmarks) ─────────────

_TMP_DIR: tempfile.TemporaryDirectory | None = None
_PATHS_100: list[str] = []
_PATHS_500: list[str] = []
_PATHS_1000: list[str] = []
_QAPP = None  # keeps the offscreen QGuiApplication alive for the process lifetime
_THUMB_SIZE = 180


def _write_png_images(out: Path, count: int) -> list[str]:
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        print("WARNING: Pillow not installed — skipping PNG fixture generation.")
        return []

    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    paths: list[str] = []
    for i in range(count):
        arr = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
        img = Image.fromarray(arr, "RGB")
        p = out / f"img_{i:04d}.png"
        img.save(p, format="PNG", optimize=False, compress_level=1)
        paths.append(str(p))
    return paths


def _setup() -> None:
    global _TMP_DIR, _PATHS_100, _PATHS_500, _PATHS_1000, _QAPP
    _TMP_DIR = tempfile.TemporaryDirectory()
    root = Path(_TMP_DIR.name)
    # 1000-image set generated once; 100/500 are prefixes of it so timings are
    # comparable (same file content/size distribution at every N).
    _PATHS_1000 = _write_png_images(root / "gallery", 1000)
    _PATHS_100 = _PATHS_1000[:100]
    _PATHS_500 = _PATHS_1000[:500]
    if _QT_AVAILABLE and _QAPP is None:
        _QAPP = QGuiApplication.instance() or QGuiApplication([])


# ── Runner registration ───────────────────────────────────────────────────────

runner = BenchmarkManager("GUI Thumbnail Loading")


@runner.benchmark("load_batch_gallery_100", iterations=3, warmup=1)
@measure_memory
def bench_load_100() -> None:
    """base.load_image_batch() for a 100-image gallery page."""
    if not _CPP_AVAILABLE or not _PATHS_100:
        return
    cpp_core.load_image_batch(_PATHS_100, thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE)


@runner.benchmark("load_batch_gallery_500", iterations=3, warmup=1)
@measure_memory
def bench_load_500() -> None:
    """base.load_image_batch() for a 500-image gallery page."""
    if not _CPP_AVAILABLE or not _PATHS_500:
        return
    cpp_core.load_image_batch(_PATHS_500, thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE)


@runner.benchmark("load_batch_gallery_1000", iterations=3, warmup=1)
@measure_memory
def bench_load_1000() -> None:
    """base.load_image_batch() for a 1000-image gallery page."""
    if not _CPP_AVAILABLE or not _PATHS_1000:
        return
    cpp_core.load_image_batch(_PATHS_1000, thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE)


@runner.benchmark("lru_cache_miss_then_fill_1000", iterations=3, warmup=1)
@measure_memory
def bench_lru_cache_miss() -> None:
    """Cold-cache path: every lookup misses, decode+insert all 1000 thumbnails.

    Mirrors AbstractGalleryBase's per-tab LRUImageCache (default maxsize=300
    per this project's RAM-optimization work) -- a page of 1000 images
    exceeds that bound, so this also exercises eviction under load.
    """
    if not _CPP_AVAILABLE or not _PATHS_1000:
        return
    cache = LRUImageCache(maxsize=300)
    results = cpp_core.load_image_batch(
        _PATHS_1000, thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE, rgb=True
    )
    for path, thumb, _err in results:
        if thumb is None or not _QT_AVAILABLE:
            continue
        h, w = thumb.shape[:2]
        qimg = QImage(
            thumb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888
        ).copy()
        cache[path] = qimg


@runner.benchmark("lru_cache_hit_300", iterations=10, warmup=2)
@measure_memory
def bench_lru_cache_hit() -> None:
    """Warm-cache path: repeated lookups of already-cached entries (no decode)."""
    if not _CPP_AVAILABLE or not _PATHS_100 or not _QT_AVAILABLE:
        return
    cache = LRUImageCache(maxsize=300)
    results = cpp_core.load_image_batch(
        _PATHS_100, thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE, rgb=True
    )
    for path, thumb, _err in results:
        if thumb is None:
            continue
        h, w = thumb.shape[:2]
        qimg = QImage(
            thumb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888
        ).copy()
        cache[path] = qimg
    for path in _PATHS_100:
        _ = cache.get(path)


@runner.benchmark("qimage_vs_qpixmap_memory_300", iterations=1, warmup=0)
@measure_memory
def bench_qimage_vs_qpixmap() -> None:
    """Report the QImage vs QPixmap RSS delta for 300 cached 180px thumbnails.

    Confirms this project's own rationale for storing QImage (not QPixmap) in
    LRUImageCache: QPixmap carries an X11/platform server-side backing copy
    that QImage avoids (`gui/src/utils/lru_image_cache.py`'s own docstring).
    Prints both deltas directly since a single decorator-measured delta can't
    show two separate populations in one pass.
    """
    if not _CPP_AVAILABLE or not _PATHS_1000 or not _QT_AVAILABLE:
        return
    sample = _PATHS_1000[:300]
    results = cpp_core.load_image_batch(
        sample, thumb_w=_THUMB_SIZE, thumb_h=_THUMB_SIZE, rgb=True
    )

    import gc

    import psutil

    proc = psutil.Process()
    gc.collect()
    before = proc.memory_info().rss / 1024 / 1024

    qimages = []
    for _path, thumb, _err in results:
        if thumb is None:
            continue
        h, w = thumb.shape[:2]
        qimages.append(
            QImage(thumb.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        )
    gc.collect()
    after_qimage = proc.memory_info().rss / 1024 / 1024

    qpixmaps = [QPixmap.fromImage(qi) for qi in qimages]
    gc.collect()
    after_qpixmap = proc.memory_info().rss / 1024 / 1024

    print(
        f"    [QImage vs QPixmap] {len(qimages)} thumbnails @ {_THUMB_SIZE}px: "
        f"QImage delta={after_qimage - before:.1f}MB, "
        f"+QPixmap delta={after_qpixmap - after_qimage:.1f}MB "
        f"(total with both alive={after_qpixmap - before:.1f}MB)"
    )
    qpixmaps.clear()
    qimages.clear()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _CPP_AVAILABLE:
        print("ERROR: C++ base module not available.")
        print("       Run the build_base.sh|build_base.bat C++ build script first.")
        sys.exit(1)
    if not _QT_AVAILABLE:
        print("WARNING: PySide6 not available — LRU/QImage/QPixmap benchmarks will no-op.")

    _setup()
    try:
        runner.run()
        runner.print_results()
        runner.save_json()
    finally:
        if _TMP_DIR is not None:
            _TMP_DIR.cleanup()
