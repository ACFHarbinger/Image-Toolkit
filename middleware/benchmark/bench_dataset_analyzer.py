"""Benchmark for Gate D.4's deterministic dataset checks (issue #757).

Times `middleware/src/core/dataset_advisor.py::scan_dataset` — the shipped
Python implementation of the advisor's I/O-bound pre-analysis (sha256
hashing, PIL header dimension probe, caption sidecar read, frame-group
keying, duplicate grouping, co-occurrence build) — against a synthetic
1000+ image dataset. CLIP diversity analysis is out of scope by design
(needs PyTorch; stays Python regardless).

The dataset is generated under `~/Downloads/Data/Tests/ds-analyzer-bench`
(per AGENTS.md, never inside the repo) and reused across runs; delete the
directory or pass --regenerate to rebuild it.

Run standalone:
    python middleware/benchmark/bench_dataset_analyzer.py
    python middleware/benchmark/bench_dataset_analyzer.py --save
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from middleware.benchmark.managers import BenchmarkManager  # noqa: E402
from middleware.src.core import dataset_advisor  # noqa: E402

TRIGGER = "ohwx"
_DEFAULT_DATA_DIR = Path.home() / "Downloads" / "Data" / "Tests" / "ds-analyzer-bench"
_FIXTURE_MARKER = ".bench_fixture_v2.json"
# Fixed non-"normal" files: 20 dup pairs, 3x8 burst frames, 10 extreme
# aspect, 10 unreadable. Everything else up to --count is a normal image.
_FIXTURE_FILES = 20 + 24 + 10 + 10

_FIXTURE_SUMMARY: dict = {}
_ALL_PATHS: list[str] = []


def _make_image(rng: np.random.Generator, width: int, height: int) -> np.ndarray:
    """Gradient base + coarse and fine noise: encodes like a real
    photo-ish frame (poorly compressible), and gives every file distinct
    hash content."""
    yy, xx = np.mgrid[0:height, 0:width]
    base = np.stack([
        (xx * 255 // max(width - 1, 1)),
        (yy * 255 // max(height - 1, 1)),
        np.full((height, width), 128),
    ], axis=-1).astype(np.uint8)
    block = rng.integers(0, 64, (height // 8 + 1, width // 8 + 1, 1), dtype=np.uint8)
    noise = block.repeat(8, axis=0).repeat(8, axis=1)[:height, :width]
    fine = rng.integers(0, 48, (height, width, 1), dtype=np.uint8)
    return (base.astype(np.uint16) + noise.astype(np.uint16) // 4
            + fine.astype(np.uint16) // 2).clip(0, 255).astype(np.uint8)


def _save(arr: np.ndarray, path: Path, fmt: str) -> None:
    from PIL import Image

    image = Image.fromarray(arr, "RGB")
    if fmt == "jpeg":
        image.save(path, format="JPEG", quality=88)
    elif fmt == "webp":
        image.save(path, format="WEBP", quality=90)
    else:
        image.save(path, format="PNG", compress_level=1)


_TAG_POOL = [
    "1girl", "solo", "long hair", "blue eyes", "smile", "dress", "white background",
    "looking at viewer", "1boy", "short hair", "jacket", "outdoors", "night", "city",
    "standing", "anime style", "masterpiece", "ribbon", "hat", "sitting", "sky",
    "cloud", "tree", "forest", "rain", "umbrella", "school uniform", "animal ears",
    "tail", "wings", "flying", "magic", "glowing", "dark", "light rays", "profile",
    "from behind", "arms up", "jumping", "running", "holding hands",
    "multiple girls", "duo",
]


def _caption(rng: np.random.Generator, with_trigger: bool) -> str:
    tags = [t for t in rng.choice(_TAG_POOL, size=rng.integers(8, 18), replace=False)]
    if with_trigger:
        tags.insert(0, TRIGGER)
    return ", ".join(tags)


def _generate_dataset(root: Path, count: int) -> list[str]:
    rng = np.random.default_rng(757)
    root.mkdir(parents=True, exist_ok=True)
    normal = count - _FIXTURE_FILES
    paths: list[str] = []

    def emit(name: str, width: int, height: int, fmt: str,
             caption: str | None, content_key: np.ndarray | None = None) -> Path:
        path = root / f"{name}.{ 'jpg' if fmt == 'jpeg' else fmt}"
        arr = content_key if content_key is not None else _make_image(rng, width, height)
        _save(arr, path, fmt)
        if caption is not None:
            path.with_suffix(".txt").write_text(caption, encoding="utf-8")
        paths.append(str(path))
        return path

    sizes = [(1024, 1024)] * 46 + [(2048, 2048)] * 14 + [(1216, 832)] * 12 \
        + [(832, 1216)] * 12 + [(3840, 2160)] * 6 + [(512, 512)] * 10
    for i in range(normal):
        width, height = sizes[i % len(sizes)]
        if i % 10 < 7:
            fmt = "jpeg"
        elif i % 10 < 9:
            fmt = "png"
        else:
            fmt = "webp"
        # ~7% lack captions; ~60% of the rest carry the trigger token.
        caption = None if i % 14 == 0 else _caption(rng, with_trigger=i % 5 != 0)
        emit(f"img_{i:04d}", width, height, fmt, caption)

    dup_sources = rng.choice(normal, size=20, replace=False)
    for j, src in enumerate(dup_sources):
        src_path = root / f"img_{src:04d}.jpg"
        if not src_path.is_file():
            src_path = next(p for p in root.glob(f"img_{src:04d}.*") if p.suffix != ".txt")
        dup = root / f"dup_{j:03d}{src_path.suffix}"
        shutil.copyfile(src_path, dup)
        sidecar = src_path.with_suffix(".txt")
        if sidecar.is_file():
            shutil.copyfile(sidecar, dup.with_suffix(".txt"))
        paths.append(str(dup))

    for scene in range(3):
        arr = _make_image(rng, 1024, 1024)
        for frame in range(8):
            emit(f"scene_{scene}_{frame:04d}", 1024, 1024, "png",
                 _caption(rng, with_trigger=True), content_key=arr)

    for j in range(10):
        wide = j % 2 == 0
        emit(f"extreme_{j:02d}", 1024 if wide else 256, 256 if wide else 1024,
             "jpeg", _caption(rng, with_trigger=False))

    for j in range(10):
        junk = root / f"broken_{j:02d}.{'png' if j % 2 else 'jpg'}"
        junk.write_bytes(b"not an image at all " + bytes(rng.integers(0, 255, 64)))
        paths.append(str(junk))

    manifest = {
        "files": sorted(p.name for p in root.iterdir() if p.is_file()),
        "version": 2, "count": len(paths), "normal": normal,
        "bytes": sum(p.stat().st_size for p in root.iterdir() if p.is_file()),
    }
    (root / _FIXTURE_MARKER).write_text(json.dumps(manifest), encoding="utf-8")
    return paths


def _setup(data_dir: Path, count: int, regenerate: bool) -> None:
    global _FIXTURE_SUMMARY, _ALL_PATHS
    data_dir = data_dir.expanduser().resolve()
    allowed = (Path.home() / "Downloads" / "Data" / "Tests").resolve()
    if data_dir == allowed or not data_dir.is_relative_to(allowed):
        raise ValueError("Fixture directory must be a child of ~/Downloads/Data/Tests.")
    if count < _FIXTURE_FILES + 20:
        raise ValueError("count must leave at least 20 normal images for duplicate fixtures")
    marker = data_dir / _FIXTURE_MARKER
    if data_dir.exists() and any(data_dir.iterdir()):
        if not marker.is_file():
            raise ValueError("Refusing to modify a non-fixture directory.")
        manifest = json.loads(marker.read_text(encoding="utf-8"))
        paths = [str(p) for p in sorted(data_dir.iterdir())
                 if p.suffix in {".png", ".jpg", ".jpeg", ".webp"} and p.is_file()]
        if not regenerate and manifest.get("count") == count and len(paths) == count:
            _FIXTURE_SUMMARY, _ALL_PATHS = manifest, paths
            _WARM_CACHE.clear()
            return
        owned = manifest.get("files")
        if manifest.get("version") != 2 or not isinstance(owned, list):
            raise ValueError("Legacy fixture cannot be removed automatically; choose an empty directory.")
        actual = {p.name for p in data_dir.iterdir()}
        if actual != set(owned) | {_FIXTURE_MARKER}:
            raise ValueError("Fixture contains unrecognized files; refusing regeneration.")
        if any(not isinstance(name, str) or Path(name).name != name or
               not re.fullmatch(r"(?:img|dup|scene|extreme|broken)_[0-9_]+\.(?:png|jpg|webp|txt)", name)
               for name in owned):
            raise ValueError("Invalid fixture manifest.")
        for name in owned:
            (data_dir / name).unlink()
        marker.unlink()
    _WARM_CACHE.clear()
    started = time.perf_counter()
    _ALL_PATHS = _generate_dataset(data_dir, count)
    _FIXTURE_SUMMARY = json.loads(marker.read_text(encoding="utf-8"))
    _FIXTURE_SUMMARY["generation_sec"] = round(time.perf_counter() - started, 3)


# Populated once by the first warm-benchmark call (and the warmup run), then
# shared across iterations — the panel's re-scan after a trigger-token edit.
_WARM_CACHE: dict = {}



def bench_scan_cold() -> None:
    """Full scan, hash cache disabled: every file re-hashed + probed."""
    dataset_advisor.scan_dataset(_ALL_PATHS, trigger=TRIGGER)


def bench_scan_warm() -> None:
    """Panel re-scan path: mtime/size-validated cache skips re-hashing."""
    dataset_advisor.scan_dataset(_ALL_PATHS, trigger=TRIGGER, hash_cache=_WARM_CACHE)


def _fixture_files() -> list[Path]:
    """Every image plus its caption sidecar: all bytes a scan touches."""
    files = [Path(p) for p in _ALL_PATHS]
    return files + [f.with_suffix(".txt") for f in files if f.with_suffix(".txt").is_file()]


def _evict_page_cache() -> None:
    """Drop the fixture's clean pages from the OS page cache (no root needed).

    POSIX_FADV_DONTNEED on unmodified files releases their cached pages, so the
    next scan reads from storage. Verify with ``fincore`` when it matters.
    """
    for path in _fixture_files():
        fd = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)


def _scan_page_cold(iterations: int) -> list[float]:
    """Full scans with no hash cache and an evicted page cache."""
    times = []
    for _ in range(iterations):
        _evict_page_cache()
        started = time.perf_counter()
        dataset_advisor.scan_dataset(_ALL_PATHS, trigger=TRIGGER)
        times.append(time.perf_counter() - started)
    return times


def _native_floor() -> dict:
    """Work a native analyzer cannot remove: reading the bytes and OpenSSL sha256.

    hashlib's sha256 is OpenSSL's, which a C++ module would also call, so
    ``scan - (read + sha256)`` bounds what native code could save. The bound is
    generous: it assumes native header probing, captions, and grouping are free.
    Measured with a warm page cache to match the warm-storage scan it is
    compared against.
    """
    paths = [Path(p) for p in _ALL_PATHS]
    for path in paths:  # warm the page cache
        path.read_bytes()
    read_sec = sha_sec = 0.0
    for path in paths:
        started = time.perf_counter()
        data = path.read_bytes()
        read_sec += time.perf_counter() - started
        started = time.perf_counter()
        hashlib.sha256(data).digest()
        sha_sec += time.perf_counter() - started
    started = time.perf_counter()
    dataset_advisor.scan_dataset(_ALL_PATHS, trigger=TRIGGER)
    scan_sec = time.perf_counter() - started
    floor = read_sec + sha_sec
    return {"read_sec": read_sec, "sha256_sec": sha_sec, "floor_sec": floor,
            "scan_warm_storage_sec": scan_sec,
            "max_native_saving_sec": max(scan_sec - floor, 0.0)}

def _phase_breakdown() -> dict:
    """One cold scan with module functions wrapped in timers, attributing
    wall time to hashing/probing, caption reading, duplicate grouping, and
    co-occurrence construction."""
    timers: dict[str, float] = {"probe": 0.0, "captions": 0.0,
                                "duplicates": 0.0, "cooccurrence": 0.0}
    originals = {}

    def wrap(name: str, attr: str):
        original = getattr(dataset_advisor, attr)

        def timed(*args, **kwargs):
            started = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                timers[name] += time.perf_counter() - started

        originals[attr] = original
        setattr(dataset_advisor, attr, timed)

    total_start = time.perf_counter()
    for attr, name in (("_probe", "probe"), ("_read_captions", "captions"),
                       ("_duplicate_groups", "duplicates"),
                       ("_cooccurrence_findings", "cooccurrence")):
        wrap(name, attr)
    try:
        report = dataset_advisor.scan_dataset(_ALL_PATHS, trigger=TRIGGER)
    finally:
        for attr, original in originals.items():
            setattr(dataset_advisor, attr, original)
    timers["total"] = time.perf_counter() - total_start
    timers["findings"] = len(report.findings)
    return timers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=_DEFAULT_DATA_DIR)
    parser.add_argument("--count", type=int, default=1200,
                        help="total image files including 64 fixed fixtures (minimum 84)")
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--save", action="store_true", help="write JSON report")
    args = parser.parse_args()
    if args.count < _FIXTURE_FILES + 20:
        parser.error(f"--count must be at least {_FIXTURE_FILES + 20}")

    _setup(args.data_dir, args.count, args.regenerate)
    total_bytes = _FIXTURE_SUMMARY["bytes"]
    generated = _FIXTURE_SUMMARY.get("generation_sec")
    gen_note = f"generated in {generated}s" if generated is not None else "reused from disk"
    print(f"dataset: {_FIXTURE_SUMMARY['count']} files, "
          f"{total_bytes / 1e9:.2f} GB ({gen_note})")

    runner = BenchmarkManager("Dataset Analyzer (Gate D.4 deterministic checks)")
    runner.benchmark("scan_no_hash_cache", iterations=3, warmup=0)(bench_scan_cold)
    runner.benchmark("scan_warm_hash_cache", iterations=5, warmup=1)(bench_scan_warm)
    runner.run()

    page_cold = _scan_page_cold(3)
    print("\nscan, no hash cache, page cache evicted: "
          + ", ".join(f"{t:.3f}s" for t in page_cold)
          + f" (avg {sum(page_cold) / len(page_cold):.3f}s)")
    floor = _native_floor()
    print(f"native floor (read + OpenSSL sha256): {floor['floor_sec']:.3f}s "
          f"(read {floor['read_sec']:.3f}s, sha256 {floor['sha256_sec']:.3f}s) "
          f"vs scan {floor['scan_warm_storage_sec']:.3f}s "
          f"-> native saves at most {floor['max_native_saving_sec']:.3f}s")
    breakdown = _phase_breakdown()
    per_image_ms = breakdown["total"] / len(_ALL_PATHS) * 1000
    print("\nphase attribution (one cold scan):")
    for phase in ("probe", "captions", "duplicates", "cooccurrence"):
        print(f"  {phase:<14} {breakdown[phase]:7.3f}s "
              f"({breakdown[phase] / breakdown['total'] * 100:5.1f}%)")
    print(f"  {'total':<14} {breakdown['total']:7.3f}s  ({per_image_ms:.2f} ms/image)"
          f"  findings={breakdown['findings']}")

    if args.save:
        out = runner.save_json(args.data_dir.resolve().parent / (args.data_dir.name + "-results.json"))
        print(f"\nreport saved: {out}")
        payload = json.loads(Path(out).read_text(encoding="utf-8"))
        payload["dataset"] = _FIXTURE_SUMMARY
        payload["phase_breakdown_sec"] = breakdown
        payload["per_image_ms_cold"] = per_image_ms
        payload["scan_page_cache_evicted_sec"] = page_cold
        payload["native_floor"] = floor
        Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
