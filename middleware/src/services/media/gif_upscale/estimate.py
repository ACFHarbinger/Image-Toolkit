"""Pre-flight estimate for one GIF resample (C2, #1160, D10, D17, D21).

Times a few frames on CPU and projects the rest. It does not run a GPU
kernel. When the job would use a GPU, the path says the CPU sample is an
upper bound. Palette is one quantize of the timed frames, projected to
``min(16, frame count)`` frames. It does not stride through the clip.
The first indexed frame's time is kept once, because balanced and fast
build their palette table there.

``workers`` above 1 with batch multi-core (the Sampler "Multi-core
processing" checkbox) warns, because decode and encode can each use that
many processes (D10).
"""

from __future__ import annotations

import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, ResampleCancelled
from middleware.src.services.media.gif_upscale.encode import IndexedGifWriter, _shared_palette, index_frame
from middleware.src.services.media.gif_upscale.io import iter_gif_frames
from middleware.src.services.media.gif_upscale.job_settings import with_job_settings
from middleware.src.services.media.gif_upscale.parallel_decode import scan_gif
from middleware.src.services.media.gif_upscale.pipeline import _one_frame, _prepare_scale, _uint8, _workers

_STAGES = ("decode", "palette", "scale", "index", "lzw")
_DEFAULT_SAMPLE = 4
_MAX_SAMPLE = 8
_PALETTE_CAP = 16
_GPU_ALGORITHM = "lanczos3-dering"
_PROJECTION_NOTE = (
    "Linear projection: later frames are assumed to cost the same as the timed sample. "
    "Palette is one quantize, scaled from the timed strip to min(16, frame count) frames. "
    "This is not a measured full-job time."
)

DeviceProbe = Callable[[], tuple[bool, str]]


@dataclass(frozen=True)
class GifEstimate:
    """Projected job. ``measured_s`` is the timed sample; ``projected_s`` is the full clip."""

    frame_count: int
    sample_frames: int
    src_w: int
    src_h: int
    dst_w: int
    dst_h: int
    device: str
    timed_device: str
    path: str
    measured_s: dict[str, float]
    projected_s: dict[str, float]
    index_setup_s: float
    total_s: float
    warning: str | None
    notes: tuple[str, ...]
    workers: int
    use_multicore: bool


def workers_batch_warning(workers: int, use_multicore: bool) -> str | None:
    """Warn when intra-file workers and batch multi-core would run together (D10).

    A value that is not an integer at least 1 is treated as 1, matching the
    resample path, so it does not warn.
    """
    count = _workers({"workers": workers})
    if count <= 1 or not use_multicore:
        return None
    return (
        f"workers={count} with batch multi-core: decode and encode can use up to "
        f"{count * 2} processes on top of the batch pool (D10)."
    )


def usable_gif_gpu(probe: DeviceProbe | None = None) -> tuple[bool, str]:
    """Whether a GIF GPU job has a card, and the label the job would use.

    ``probe`` is for tests. The default probe may initialize CUDA and must
    not be called from a test. This function does not run a resample kernel.
    """
    chosen = probe if probe is not None else _default_gpu_probe
    usable, label = chosen()
    if not usable:
        return False, "cpu"
    text = str(label).strip() or "cuda:0"
    return True, text


def _default_gpu_probe() -> tuple[bool, str]:
    """Ask whether CUDA is available. May initialize CUDA. Does not launch a kernel."""
    try:
        import torch
    except ImportError:
        return False, "cpu"
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not bool(cuda.is_available()):
        return False, "cpu"
    if int(cuda.device_count()) < 1:
        return False, "cpu"
    return True, "cuda:0"


def estimate_gif_job(
    input_path: str,
    params: dict[str, Any] | None = None,
    *,
    sample_frames: int = _DEFAULT_SAMPLE,
    use_multicore: bool = False,
    device_probe: DeviceProbe | None = None,
    scratch_dir: str | Path | None = None,
    settings_service: Any | None = None,
) -> GifEstimate:
    """Time ``sample_frames`` (at most 8) and project decode, palette, scale, index, and LZW.

    ``progress`` in ``params`` is called as ``(stage, done, total)``. If it
    raises ``ResampleCancelled``, that exception propagates and the scratch
    GIF is removed. Settings fill only keys the request left out.
    """
    if sample_frames < 1:
        raise ValueError("sample_frames must be at least 1")
    request = with_job_settings(dict(params or {}), settings_service)
    progress = request.get("progress")
    info, records = _scan(input_path)
    frame_count = len(records)
    if frame_count < 1:
        raise AlgorithmError("GIF has no frames.")
    sample = min(int(sample_frames), frame_count, _MAX_SAMPLE)
    workers = _workers(request)
    device, device_note = _job_device(request, device_probe)
    _report(progress, "estimate", 0, frame_count)

    measured = {stage: 0.0 for stage in _STAGES}
    decoded, measured["decode"] = _decode_sample(input_path, sample, progress, frame_count)
    if len(decoded) != sample:
        raise AlgorithmError(f"GIF decode returned {len(decoded)} frames; the header said {frame_count}.")

    registered, _scale, width, height, algorithm_id = _prepare_scale(request, "gif", info.width, info.height)
    opts = {
        "size": (width, height),
        "scale": float(_scale),
        "params": {key: value for key, value in request.items() if key != "progress"},
    }
    scaled = _scale_sample(decoded, registered, _scale, opts, algorithm_id)
    measured["scale"] = scaled[1]
    rgba = scaled[0]
    transparent = any(int(frame[:, :, 3].min()) < 128 for frame in rgba)
    colors = 255 if transparent else 256
    palette_mode = str(request.get("palette_mode") or "mediancut")
    started = time.perf_counter()
    palette = _shared_palette(rgba, colors, palette_mode)
    measured["palette"] = time.perf_counter() - started
    if transparent:
        palette = np.vstack([np.zeros((1, 3), dtype=np.float32), palette])

    quality = str(request.get("quality") or "balanced")
    dither = str(request.get("dither") or "ordered")
    indexed, index_setup, index_rest = _index_sample(
        rgba, palette, transparent, dither, quality, progress, frame_count, sample
    )
    measured["index"] = index_setup + index_rest
    measured["lzw"] = _time_lzw(indexed, decoded, width, height, palette, info.loop, transparent, scratch_dir)

    frame_ratio = frame_count / sample
    palette_target = min(_PALETTE_CAP, frame_count)
    palette_ratio = palette_target / sample
    projected = {stage: measured[stage] * frame_ratio for stage in _STAGES}
    projected["palette"] = measured["palette"] * palette_ratio
    projected["index"] = _project_index(index_setup, index_rest, sample, frame_count)
    warning = workers_batch_warning(workers, use_multicore)
    notes = _notes(device, device_note, workers, frame_ratio, palette_ratio, palette_target, sample)
    path = _path_text(
        algorithm_id, sample, frame_count, device, workers, bool(use_multicore), device != "cpu"
    )
    return GifEstimate(
        frame_count=frame_count,
        sample_frames=sample,
        src_w=int(info.width),
        src_h=int(info.height),
        dst_w=int(width),
        dst_h=int(height),
        device=device,
        timed_device="cpu",
        path=path,
        measured_s=measured,
        projected_s=projected,
        index_setup_s=index_setup,
        total_s=sum(projected.values()),
        warning=warning,
        notes=notes,
        workers=workers,
        use_multicore=bool(use_multicore),
    )


def _scan(input_path: str):
    try:
        return scan_gif(input_path)
    except ValueError as exc:
        raise AlgorithmError(str(exc)) from exc


def _report(progress: Any, stage: str, done: int, total: int) -> None:
    if progress is None:
        return
    progress(stage, int(done), int(total))


def _decode_sample(
    input_path: str, sample: int, progress: Any, frame_count: int
) -> tuple[list[tuple[np.ndarray, int, int]], float]:
    frames: list[tuple[np.ndarray, int, int]] = []
    source = iter_gif_frames(input_path)
    started = time.perf_counter()
    try:
        for index in range(sample):
            try:
                frames.append(next(source))
            except StopIteration:
                break
            _report(progress, "estimate", index + 1, frame_count)
    finally:
        close = getattr(source, "close", None)
        if callable(close):
            close()
    return frames, time.perf_counter() - started


def _scale_sample(decoded, registered, scale: float, opts: dict[str, Any], algorithm_id: str):
    started = time.perf_counter()
    rgba = [
        _uint8(_one_frame(registered, frame.astype(np.float32) / 255.0, scale, opts, algorithm_id))
        for frame, _duration, _loop in decoded
    ]
    return rgba, time.perf_counter() - started


def _index_sample(rgba, palette, transparent, dither, quality, progress, frame_count, sample):
    """Time the first frame apart from the rest.

    Balanced and fast build a palette table on the first call. That cost is
    once per clip, so the projection must not multiply it by the frame count.
    """
    indexed = []
    started = time.perf_counter()
    indexed.append(index_frame(rgba[0], palette, transparent=transparent, dither=dither, quality=quality))
    setup = time.perf_counter() - started
    started = time.perf_counter()
    for frame in rgba[1:]:
        indexed.append(index_frame(frame, palette, transparent=transparent, dither=dither, quality=quality))
    rest = time.perf_counter() - started
    _report(progress, "estimate", sample, frame_count)
    return indexed, setup, rest


def _project_index(setup: float, rest: float, sample: int, frame_count: int) -> float:
    if sample <= 1:
        # The one-time table is inside the only sample, so this index number is high.
        return setup * frame_count
    per_frame = rest / (sample - 1)
    return setup + per_frame * (frame_count - 1)


def _time_lzw(indexed, decoded, width, height, palette, loop, transparent, scratch_dir) -> float:
    if scratch_dir is None:
        with tempfile.TemporaryDirectory(prefix="gif-estimate-") as directory:
            return _write_lzw(indexed, decoded, width, height, palette, loop, transparent, Path(directory))
    directory = Path(scratch_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return _write_lzw(indexed, decoded, width, height, palette, loop, transparent, directory)


def _write_lzw(indexed, decoded, width, height, palette, loop, transparent, directory: Path) -> float:
    path = directory / "gif-estimate-lzw.gif"
    writer = IndexedGifWriter(
        str(path), width, height, palette, int(loop), transparent=transparent, workers=1
    )
    started = time.perf_counter()
    try:
        for index, (_frame, duration, _loop) in zip(indexed, decoded, strict=True):
            writer.add_frame(index, int(duration))
    finally:
        writer.close()
        path.unlink(missing_ok=True)
    return time.perf_counter() - started


def _job_device(params: dict[str, Any], probe: DeviceProbe | None) -> tuple[str, str]:
    requested = str(params.get("device") or "").strip().lower()
    algorithm = str(params.get("algorithm") or "lanczos").strip().lower()
    encoder = str(params.get("encoder") or "temporal").strip().lower()
    if requested == "cpu":
        return "cpu", "the request asked for cpu"
    if algorithm != _GPU_ALGORITHM or encoder != "temporal":
        return "cpu", f"{algorithm}/{encoder} runs on cpu"
    usable, label = usable_gif_gpu(probe)
    if not usable:
        return "cpu", "no usable GPU; fell back to cpu"
    if requested.startswith("cuda:") or requested.isdigit():
        pinned = requested if requested.startswith("cuda:") else f"cuda:{requested}"
        return pinned, "pinned by the request; the sample did not time that card"
    return label, "a GPU is available; the sample did not time it"


def _notes(device, device_note, workers, frame_ratio, palette_ratio, palette_target, sample) -> tuple[str, ...]:
    notes = [
        _PROJECTION_NOTE,
        (
            f"Frame stages use ratio {frame_ratio:.6g} (frame count / sample). "
            f"Palette uses ratio {palette_ratio:.6g} ({palette_target} / {sample})."
        ),
        device_note,
    ]
    if device != "cpu":
        notes.append(f"Timed on CPU. The job would use {device}, so this total is an upper bound, not a GPU time.")
    if workers > 1:
        notes.append(
            f"Decode and LZW were timed in this process. workers={workers} can run up to "
            f"{workers * 2} processes, so those stages may finish sooner than this projection."
        )
    return tuple(notes)


def _path_text(algorithm, sample, frame_count, device, workers, use_multicore, gpu_job: bool) -> str:
    bound = "; CPU sample is an upper bound" if gpu_job else ""
    multicore = "on" if use_multicore else "off"
    return (
        f"timed cpu {algorithm} on {sample} of {frame_count} frames; "
        f"job would use {device}{bound}; workers={workers}; batch multi-core {multicore}"
    )


__all__ = [
    "GifEstimate",
    "ResampleCancelled",
    "estimate_gif_job",
    "usable_gif_gpu",
    "workers_batch_warning",
]
