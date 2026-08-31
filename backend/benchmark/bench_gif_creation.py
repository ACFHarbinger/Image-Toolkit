"""
GIF creation memory/time benchmark: eager pre-load vs streaming frames (#484).

``ImageMerger._create_gif`` used to open *every* source frame into a list and
hold them decoded for the whole ``save()`` run, so peak RSS scaled with the
total frame count. The streaming version opens/produces one frame at a time
and closes each source once Pillow has copied it, so peak allocation stays
~one frame regardless of count.

This harness re-implements the old (eager) path inline as the "before" arm and
calls the live ``ImageMerger._create_gif`` as the "after" arm. Each arm runs in
a **fresh subprocess** (``resource.ru_maxrss`` is a process-wide high-water
mark, so running both in one process would hide the second arm's peak). It
reports peak RSS delta and wall time for each, plus the before/after ratio.

Usage
-----
    python backend/benchmark/bench_gif_creation.py
    python backend/benchmark/bench_gif_creation.py --frames 60 --res 800x600
    python backend/benchmark/bench_gif_creation.py --save-json results.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

# Allow `python backend/benchmark/bench_gif_creation.py` to resolve the
# package regardless of the invoking cwd.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_CHILD_CODE = """
import gc, json, resource, sys, time
from PIL import Image
from {pkg}._gif_video import _GifVideoMixin

impl = sys.argv[1]
paths = sys.argv[2].split("\\n")
out = sys.argv[3]
duration = int(sys.argv[4])

base_size = Image.open(paths[0]).size

def legacy():
    images = [Image.open(p) for p in paths]
    frames = []
    for img in images:
        frames.append(
            img.resize(base_size, Image.Resampling.LANCZOS)
            if img.size != base_size
            else img
        )
    frames[0].save(
        out, format="GIF", append_images=frames[1:], save_all=True,
        duration=duration, loop=0, optimize=True,
    )
    return frames[0]

gc.collect()
baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
t0 = time.perf_counter()
if impl == "legacy":
    legacy()
else:
    _GifVideoMixin._create_gif(paths, out, duration)
elapsed = time.perf_counter() - t0
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps({{
    "mode": impl,
    "elapsed_s": round(elapsed, 4),
    "peak_delta_mib": round((peak - baseline) / 1024, 2),
}}))
""".strip()


def _legacy_create_gif(image_paths, output_path, duration):
    """The pre-#484 eager implementation, preserved as the ``before`` arm."""
    images = [Image.open(p) for p in image_paths]
    base_size = images[0].size
    frames = [
        img.resize(base_size, Image.Resampling.LANCZOS) if img.size != base_size else img
        for img in images
    ]
    frames[0].save(
        output_path,
        format="GIF",
        append_images=frames[1:],
        save_all=True,
        duration=duration,
        loop=0,
        optimize=True,
    )
    return frames[0]


def _make_frames(frames_dir: Path, count: int, wh: tuple[int, int]) -> list[str]:
    paths = []
    for i in range(count):
        # Alternate sizes ~10% of the time so the resize path is exercised.
        h, w = wh[1], wh[0]
        if i % 10 == 9:
            w = w * 3 // 2
        arr = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
        p = frames_dir / f"frame_{i:03d}.png"
        Image.fromarray(arr).save(p)
        paths.append(str(p))
    return paths


def _run_arm(python: str, mode: str, paths: list[str], output: Path, duration: int) -> dict:
    code = _CHILD_CODE.format(pkg="backend.src.core.image")
    proc = subprocess.run(
        [python, "-c", code, mode, "\n".join(paths), str(output), str(duration)],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{mode} arm failed: {proc.stderr[-800:]}\n{proc.stdout[-800:]}")
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GIF creation before/after benchmark")
    parser.add_argument("--frames", type=int, default=48, help="frame count")
    parser.add_argument("--res", default="800x600", help="frame WxH")
    parser.add_argument("--duration", type=int, default=120, help="per-frame ms")
    parser.add_argument("--iterations", type=int, default=3, help="runs per arm")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="where to write synthetic frames (default: temp dir, deleted)")
    parser.add_argument("--keep-data", action="store_true",
                        help="do not delete the frames dir afterwards")
    parser.add_argument("--save-json", type=Path, default=None, help="write results JSON")
    args = parser.parse_args(argv)

    w, h = (int(x) for x in args.res.lower().split("x"))
    tmp = tempfile.mkdtemp(prefix="imgtoolkit-gif-bench-")
    frames_dir = args.data_dir or Path(tmp)
    if args.data_dir:
        frames_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = _make_frames(frames_dir, args.frames, (w, h))

        out_dir = Path(tempfile.mkdtemp(prefix="imgtoolkit-gif-out-"))
        try:
            per_arm: dict[str, list[dict]] = {"legacy": [], "streaming": []}
            for _ in range(args.iterations):
                for mode in ("legacy", "streaming"):
                    out = out_dir / f"{mode}.gif"
                    result = _run_arm(sys.executable, mode, paths, out, args.duration)
                    per_arm[mode].append(result)
            return _report(per_arm, args)
        finally:
            import shutil

            shutil.rmtree(out_dir, ignore_errors=True)
    finally:
        if not args.keep_data:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)


def _report(per_arm: dict[str, list[dict]], args: argparse.Namespace) -> int:
    def avg(key: str, mode: str) -> float:
        return sum(d[key] for d in per_arm[mode]) / len(per_arm[mode])

    leg_t = avg("elapsed_s", "legacy")
    str_t = avg("elapsed_s", "streaming")
    leg_m = avg("peak_delta_mib", "legacy")
    str_m = avg("peak_delta_mib", "streaming")

    print(f"\nGIF creation ({args.frames} frames @ {args.res})")
    print(f"{'Arm':<16}{'Time (s)':<12}{'Peak RSS Δ (MiB)':<18}")
    print(f"{'-' * 46}")
    print(f"{'before (eager)':<16}{leg_t:<12.4f}{leg_m:<18.2f}")
    print(f"{'after (stream)':<16}{str_t:<12.4f}{str_m:<18.2f}")
    print(f"{'-' * 46}")
    if leg_m:
        print(f"peak memory reduction: {1 - str_m / leg_m:+.1%} "
              f"({leg_m:.1f} -> {str_m:.1f} MiB)")
    print(f"time delta: {str_t - leg_t:+.4f}s")

    if args.save_json:
        payload = {
            "suite": "gif_creation_streaming",
            "frames": args.frames,
            "resolution": args.res,
            "iterations": args.iterations,
            "arms": per_arm,
            "summary": {
                "legacy_time_s": round(leg_t, 4),
                "streaming_time_s": round(str_t, 4),
                "legacy_peak_mib": round(leg_m, 2),
                "streaming_peak_mib": round(str_m, 2),
                "peak_reduction_pct": round((1 - str_m / leg_m) * 100, 1) if leg_m else None,
            },
        }
        args.save_json.write_text(json.dumps(payload, indent=2))
        print(f"\nResults written to {args.save_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
