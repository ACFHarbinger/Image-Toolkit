"""End-to-end before/after memory+time benchmark for the #484 extraction paths.

Measures **peak RSS (whole process tree) + wall time** for the three
resource-hungry extractor paths on a fixed synthetic clip:

- ``gif-export``    — :class:`GifCreationWorker` (MoviePy or ffmpeg GIF path)
- ``video-export``  — :class:`VideoExtractionWorker` (range re-encode)
- ``frames-pool``   — real :class:`QueueExecutionWorker` parallel path
  (:func:`run_extraction_in_process` over a ``multiprocessing.Pool``)

Each arm runs in a **fresh subprocess**: peak RSS is a per-process
high-water mark, so arms that share a process would hide each other's
peak. The parent polls the child's full psutil tree (50 ms) so pool
children and the ffmpeg subprocesses they spawn are counted —
``ru_maxrss`` of the direct child alone would miss them.

The before/after lever is the frame-extraction pool start method
(``--pool-ctx``): current ``main`` uses ``spawn`` (#485 — a forked child
inherits the entire GUI heap copy-on-write); ``fork`` monkeypatches
``multiprocessing.get_context`` in the child to reproduce the pre-#485
behavior so the same harness measures both arms on one checkout. The
historical MoviePy fixes (GIF two-pass palette, ``stderr`` deadlock) have
their own micro-harnesses (``bench_gif_creation.py``,
``bench_queue_pool_start.py``); this is the missing end-to-end harness.

All outputs go under ``~/Downloads/Data/Tests/extraction_bench/`` per the
#484 ask (AGENTS.md scratch-dir rule). The clip is synthetic
(deterministic gradient + frame counter) — no personal content.

Run standalone (RESOURCE RULE: multi-arm runs go through Codex+Harbinger):

    QT_QPA_PLATFORM=offscreen python backend/benchmark/bench_extraction_memory.py
    python backend/benchmark/bench_extraction_memory.py --pool-ctx fork --json out.json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_OUT_ROOT = Path.home() / "Downloads" / "Data" / "Tests" / "extraction_bench"
POLL_INTERVAL_S = 0.05
RESULT_MARKER = "RESULT_JSON:"

# Child arms import PySide6 -> offscreen before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Synthetic fixed clip
# ---------------------------------------------------------------------------


def _generate_clip(path: Path, width: int, height: int, frames: int, fps: int) -> None:
    """Deterministic synthetic clip: moving gradient + frame counter."""
    import cv2
    import numpy as np

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter failed to open {path}")
    rng = np.random.default_rng(394)
    noise = rng.integers(0, 32, size=(height, width, 3), dtype=np.uint8)
    try:
        for i in range(frames):
            base = np.zeros((height, width, 3), dtype=np.uint8)
            base[..., 0] = (i * 255 // max(frames - 1, 1))  # blue ramps with t
            base[..., 1] = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
            base[..., 2] = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
            frame = cv2.add(base, noise)
            cv2.putText(
                frame, f"frame {i:04d}", (12, height - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
            )
            writer.write(frame)
    finally:
        writer.release()


# ---------------------------------------------------------------------------
# Child arms (each runs in its own subprocess)
# ---------------------------------------------------------------------------


def _child_gif_export(clip: Path, out_dir: Path, ms_end: int, use_ffmpeg: bool, fps: int) -> dict:
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gui.src.helpers.video.gif_extractor_worker import GifCreationWorker

    out_path = out_dir / "bench_export.gif"
    worker = GifCreationWorker(
        video_path=str(clip), start_ms=0, end_ms=ms_end, output_path=str(out_path),
        target_size=None, fps=fps, use_ffmpeg=use_ffmpeg, speed=1.0,
    )
    result = worker._execute()
    return {"status": "ok" if out_path.exists() else "no-output",
            "result": str(result)[:200], "output": str(out_path)}


def _child_video_export(clip: Path, out_dir: Path, ms_end: int, use_ffmpeg: bool, fps: int) -> dict:
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gui.src.helpers.video.video_extractor_worker import VideoExtractionWorker

    out_path = out_dir / "bench_export.mp4"
    worker = VideoExtractionWorker(
        video_path=str(clip), start_ms=0, end_ms=ms_end, output_path=str(out_path),
        target_size=None, mute_audio=True, use_ffmpeg=use_ffmpeg, speed=1.0,
    )
    result = worker._execute()
    return {"status": "ok" if out_path.exists() else "no-output",
            "result": str(result)[:200], "output": str(out_path)}


def _child_frames_pool(
    clip: Path, out_dir: Path, ms_end: int, items: int, workers: int, pool_ctx: str, fps: int
) -> dict:
    import multiprocessing

    if pool_ctx == "fork":
        # Reproduce pre-#485 behavior on a post-#485 checkout: the worker
        # calls multiprocessing.get_context("spawn") at run time; patch the
        # module attribute so the fork arm measures the old code path.
        _orig = multiprocessing.get_context
        multiprocessing.get_context = lambda *a, **k: _orig("fork")  # type: ignore[assignment]

    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gui.src.helpers.core.queue_execution_worker import QueueExecutionWorker

    queue_items = []
    for i in range(items):
        item_out = out_dir / f"frames_{i:02d}"
        item_out.mkdir(parents=True, exist_ok=True)  # the impl expects it to exist
        queue_items.append(
            {
                "type": "range",
                "video_path": str(clip),
                "start_ms": 0,
                "end_ms": ms_end,
                "output_dir": str(item_out),
                "target_resolution": None,
                "cuts_ms": [],
                "frame_interval": 1,
                "smart_extract": False,
                "smart_method": "",
                "fps": fps,
                "mute_audio": True,
                "use_ffmpeg": True,
                "speed": 1.0,
            }
        )
    worker = QueueExecutionWorker(queue_items, parallel=True, max_workers=workers)
    results = worker._execute() or []
    ok = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    peaks = [r.get("worker_peak_rss_mb", 0.0) for r in results if isinstance(r, dict)]
    failures = [
        str(r.get("message", r.get("status"))) for r in results
        if isinstance(r, dict) and r.get("status") != "success"
    ]
    return {
        "status": "ok" if ok == items else f"{ok}/{items} succeeded",
        "first_failure": failures[0][:300] if failures else None,
        "child_peak_rss_mb_max": round(max(peaks), 1) if peaks else None,
        "results": len(results),
    }


_CHILD_ARMS = {
    "gif-export": _child_gif_export,
    "video-export": _child_video_export,
    "frames-pool": _child_frames_pool,
}


def _child_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="bench child arm")
    parser.add_argument("--arm", required=True, choices=sorted(_CHILD_ARMS))
    parser.add_argument("--clip", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--ms-end", type=int, required=True)
    parser.add_argument("--items", type=int, default=4)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--pool-ctx", choices=["spawn", "fork"], default="spawn")
    parser.add_argument("--use-ffmpeg", action="store_true")
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arm = _CHILD_ARMS[args.arm]
    if args.arm == "frames-pool":
        result = arm(Path(args.clip), out_dir, args.ms_end, args.items, args.workers, args.pool_ctx, args.fps)
    else:
        result = arm(Path(args.clip), out_dir, args.ms_end, args.use_ffmpeg, args.fps)
    print(RESULT_MARKER + json.dumps(result))
    return 0


# ---------------------------------------------------------------------------
# Parent: run one arm in a subprocess, poll its tree, collect the result
# ---------------------------------------------------------------------------


def _run_arm(arm: str, args: argparse.Namespace, clip: Path, run_dir: Path) -> dict:
    arm_out = run_dir / arm.replace("-", "_")
    ms_end = int(args.frames / args.fps * 1000)
    cmd = [
        sys.executable, str(Path(__file__).resolve()),
        "--child", "--arm", arm,
        "--clip", str(clip),
        "--out-dir", str(arm_out),
        "--ms-end", str(ms_end),
        "--items", str(args.items),
        "--workers", str(args.workers),
        "--pool-ctx", args.pool_ctx,
        "--fps", str(args.fps),
    ]
    if arm in ("gif-export", "video-export") and args.use_ffmpeg:
        cmd.append("--use-ffmpeg")

    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(_ROOT))
    log_path = arm_out / "_child.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    # Redirect to a file, not a pipe: ffmpeg progress spam can fill a pipe
    # buffer the parent isn't draining and deadlock the child mid-run.
    with open(log_path, "w", encoding="utf-8", errors="replace") as log_fh:
        proc = subprocess.Popen(
            cmd, env=env, stdout=log_fh, stderr=subprocess.STDOUT, text=True,
        )
        watcher = psutil.Process(proc.pid)
        peak_tree_mib = 0.0
        peak_single_mib = 0.0
        while proc.poll() is None:
            try:
                tree = [watcher, *watcher.children(recursive=True)]
                rss = [p.memory_info().rss for p in tree if p.is_running()]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                rss = []
            if rss:
                peak_tree_mib = max(peak_tree_mib, sum(rss) / 1024**2)
                peak_single_mib = max(peak_single_mib, max(rss) / 1024**2)
            try:
                time.sleep(POLL_INTERVAL_S)
            except KeyboardInterrupt:
                proc.kill()
                raise
        proc.wait()

    wall_s = time.perf_counter() - start
    stdout_tail = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    result: dict = {"status": "unknown"}
    for line in reversed(stdout_tail.splitlines()):
        if line.startswith(RESULT_MARKER):
            with contextlib.suppress(json.JSONDecodeError):
                result = json.loads(line[len(RESULT_MARKER):])
            break
    if proc.returncode != 0 and result.get("status") == "unknown":
        result = {"status": f"child-exit-{proc.returncode}", "tail": stdout_tail[-2000:]}

    output_bytes = 0
    if arm_out.exists():
        output_bytes = sum(f.stat().st_size for f in arm_out.rglob("*") if f.is_file())
    return {
        "wall_s": round(wall_s, 3),
        "peak_tree_rss_mib": round(peak_tree_mib, 1),
        "peak_single_rss_mib": round(peak_single_mib, 1),
        "output_bytes": output_bytes,
        **result,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--child" in argv:
        return _child_main([a for a in argv if a != "--child"])

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--frames", type=int, default=96)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--items", type=int, default=4, help="frame-extraction queue items")
    parser.add_argument("--workers", type=int, default=2, help="pool workers")
    parser.add_argument("--pool-ctx", choices=["spawn", "fork"], default="spawn",
                        help="frame-extraction pool start method (fork = pre-#485 behavior)")
    parser.add_argument("--use-ffmpeg", action="store_true", help="ffmpeg backend for gif/video arms")
    parser.add_argument("--arms", nargs="*", choices=sorted(_CHILD_ARMS), default=sorted(_CHILD_ARMS))
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--json-out", type=Path, default=None, help="summary JSON path (default: run dir)")
    args = parser.parse_args(argv)

    run_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    run_dir = args.out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    clip = run_dir / "bench_clip.mp4"
    print(f"[bench] clip {args.width}x{args.height} @{args.fps}fps ({args.frames} frames) -> {clip}")
    _generate_clip(clip, args.width, args.height, args.frames, args.fps)

    git_rev = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=_ROOT
    ).stdout.strip() or "unknown"

    summary: dict = {
        "run_id": run_id,
        "git_rev": git_rev,
        "clip": {"path": str(clip), "width": args.width, "height": args.height,
                 "frames": args.frames, "fps": args.fps},
        "pool_ctx": args.pool_ctx,
        "workers": args.workers,
        "items": args.items,
        "arms": {},
    }
    print(f"[bench] arms: {', '.join(args.arms)}  (pool_ctx={args.pool_ctx}, workers={args.workers})")
    for arm in args.arms:
        print(f"[bench] running {arm} ...", flush=True)
        summary["arms"][arm] = _run_arm(arm, args, clip, run_dir)
        r = summary["arms"][arm]
        print(
            f"[bench] {arm}: wall={r['wall_s']}s  peak_tree={r['peak_tree_rss_mib']} MiB  "
            f"peak_single={r['peak_single_rss_mib']} MiB  out={r['output_bytes']} B  status={r['status']}",
            flush=True,
        )

    json_path = args.json_out or (run_dir / "summary.json")
    json_path.write_text(json.dumps(summary, indent=2))
    print(f"[bench] summary -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
