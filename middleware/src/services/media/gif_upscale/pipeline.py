"""Run one GIF through the selected registry backend and the palette writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, ResampleCancelled
from middleware.src.services.media.gif_upscale.encode import encode_gif
from middleware.src.services.media.gif_upscale.io import decode_gif
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms

__all__ = ["ResampleCancelled", "list_algorithms", "resample_gif", "resample_still"]


def resample_gif(input_path: str, output_path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Raises ResampleCancelled when ``params["progress"]`` raises it. The partial output is removed."""
    progress = params.get("progress")
    try:
        _report(progress, "decode", 0, 1)
        if _needs_stream(input_path, params):
            return _resample_gif_stream(input_path, output_path, params, progress)
        clip = decode_gif(input_path)
        _report(progress, "decode", 1, 1)
        frames = [frame.astype(np.float32) / 255.0 for frame in clip.frames]
        scaled, width, height, _algorithm_id = _scale_frames(frames, params, "gif")
        _report(progress, "encode", 0, 1)
        try:
            encoder = encode_gif(
                output_path,
                scaled,
                clip.durations,
                clip.loop,
                encoder=str(params.get("encoder") or "temporal"),
                dither=str(params.get("dither") or "ordered"),
                progress=progress,
            )
        except ResampleCancelled:
            Path(output_path).unlink(missing_ok=True)
            raise
        _report(progress, "encode", 1, 1)
    except (AlgorithmError, OSError, ValueError) as exc:
        return {"success": False, "message": str(exc)}
    return {
        "success": True,
        "message": f"Wrote {width}x{height} {output_path}",
        "width": width,
        "height": height,
        "encoder": encoder,
    }


def resample_still(input_path: str, output_path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Resize one still with the same registry entry a GIF would use, then save that format."""
    from PIL import Image

    progress = params.get("progress")
    try:
        _report(progress, "decode", 0, 1)
        with Image.open(input_path) as image:
            frame = np.asarray(image.convert("RGBA")).astype(np.float32) / 255.0
        _report(progress, "decode", 1, 1)
        scaled, width, height, _algorithm_id = _scale_frames([frame], params, "still")
        _report(progress, "encode", 0, 1)
        _save_still(scaled[0], output_path)
        _report(progress, "encode", 1, 1)
    except (AlgorithmError, OSError, ValueError) as exc:
        return {"success": False, "message": str(exc)}
    return {"success": True, "message": f"Wrote {width}x{height} {output_path}", "width": width, "height": height}


def _needs_stream(input_path: str, params: dict[str, Any]) -> bool:
    """Long clips cannot keep every scaled frame. 8327 frames at 2x is hundreds of GB."""
    from PIL import Image

    from middleware.src.services.media.gif_upscale.encode import STREAM_RGBA_BYTES

    with Image.open(input_path) as image:
        count = int(getattr(image, "n_frames", 1) or 1)
        width, height = _target_size(image.size, params)
    return count * width * height * 4 * 4 > STREAM_RGBA_BYTES


def _resample_gif_stream(
    input_path: str,
    output_path: str,
    params: dict[str, Any],
    progress: Any,
) -> dict[str, Any]:
    """Scale and write one frame at a time. The palette comes from a spread of frames."""
    from middleware.src.services.media.gif_upscale.encode import (
        IndexedGifWriter,
        _shared_palette,
        index_frame,
    )
    from middleware.src.services.media.gif_upscale.io import iter_gif_frames

    _report(progress, "decode", 1, 1)
    prepared = _prepare_scale(params, "gif", *_first_size(input_path))
    registered, scale, width, height, algorithm_id = prepared
    if registered.spec.needs_gpu:
        raise AlgorithmError("Neural processing of streaming clips requires a prepared temporal inference session; reduce clip size.")
    opts = {"size": (width, height), "params": {key: value for key, value in params.items() if key != "progress"}}
    samples, count, loop = _palette_samples(input_path, registered, scale, opts, algorithm_id, progress)
    transparent = True
    colors = 255 if transparent else 256
    palette = _shared_palette(samples, colors, "mediancut")
    if transparent:
        palette = np.vstack([np.zeros((1, 3), dtype=np.float32), palette])
    del samples
    writer = IndexedGifWriter(output_path, width, height, palette, loop, transparent=transparent)
    cancelled = False
    try:
        _report(progress, "scale", 0, count)
        for seen, (frame, duration, _frame_loop) in enumerate(iter_gif_frames(input_path), start=1):
            scaled = _one_frame(registered, frame.astype(np.float32) / 255.0, float(scale), opts, algorithm_id)
            writer.add_frame(
                index_frame(_uint8(scaled), palette, transparent=transparent),
                duration,
            )
            _report(progress, "scale", seen, count)
        _report(progress, "encode", 0, 1)
    except ResampleCancelled:
        cancelled = True
        raise
    finally:
        writer.close()
        if cancelled:
            Path(output_path).unlink(missing_ok=True)
    _report(progress, "encode", 1, 1)
    return {
        "success": True,
        "message": f"Wrote {width}x{height} {output_path}",
        "width": width,
        "height": height,
        "encoder": "temporal",
    }


def _first_size(input_path: str) -> tuple[int, int]:
    from PIL import Image

    with Image.open(input_path) as image:
        return image.size


def _palette_samples(
    input_path: str, registered: Any, scale: float, opts: dict, algorithm_id: str, progress: Any = None
) -> tuple[list[np.ndarray], int, int]:
    from PIL import Image

    with Image.open(input_path) as image:
        count = int(getattr(image, "n_frames", 1) or 1)
        loop = int(image.info.get("loop", 0) or 0)
    stride = max(1, count // 16)
    wanted = set(range(0, count, stride))
    samples: list[np.ndarray] = []
    for index, (frame, _duration, _loop) in enumerate(_iter_rgba(input_path)):
        # Cancel has to land while the sample frames decode too; this scan can cross most of a long clip.
        _report(progress, "decode", index, count)
        if index not in wanted:
            continue
        scaled = _one_frame(registered, frame.astype(np.float32) / 255.0, scale, opts, algorithm_id)
        samples.append(_uint8(scaled))
        if len(samples) == len(wanted):
            break
    if not samples:
        raise AlgorithmError("GIF has no frames.")
    return samples, count, loop


def _iter_rgba(input_path: str):
    from middleware.src.services.media.gif_upscale.io import iter_gif_frames

    return iter_gif_frames(input_path)


def _one_frame(registered: Any, frame: np.ndarray, scale: float, opts: dict, algorithm_id: str) -> np.ndarray:
    one = registered.upscale([frame], scale, opts)
    if len(one) != 1:
        raise AlgorithmError(f"{algorithm_id} returned {len(one)} frames for 1 input.")
    return one[0]


def _uint8(frame: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(np.asarray(frame) * 255.0), 0, 255).astype(np.uint8)


def _prepare_scale(params: dict[str, Any], container: str, source_width: int, source_height: int):
    algorithm_id = str(params.get("algorithm") or "lanczos").strip().lower()
    registered = get_algorithm(algorithm_id)
    if container not in registered.spec.containers:
        raise AlgorithmError(f"{algorithm_id} does not resample {container} images.")
    available, reason = registered.spec.available()
    if not available:
        raise AlgorithmError(reason or f"{algorithm_id} is unavailable.")
    width, height = _target_size((source_width, source_height), params)
    refusal = _scale_refusal(registered.spec, source_width, source_height, width, height)
    if refusal:
        raise AlgorithmError(refusal)
    return registered, width / source_width, width, height, algorithm_id


def _report(progress: Any, stage: str, done: int, total: int) -> None:
    if progress is None:
        return
    progress(stage, int(done), int(total))


def _scale_frames(frames: list[np.ndarray], params: dict[str, Any], container: str) -> tuple[list[np.ndarray], int, int, str]:
    algorithm_id = str(params.get("algorithm") or "lanczos").strip().lower()
    registered = get_algorithm(algorithm_id)
    if container not in registered.spec.containers:
        raise AlgorithmError(f"{algorithm_id} does not resample {container} images.")
    available, reason = registered.spec.available()
    if not available:
        raise AlgorithmError(reason or f"{algorithm_id} is unavailable.")
    source_height, source_width = frames[0].shape[:2]
    width, height = _target_size((source_width, source_height), params)
    refusal = _scale_refusal(registered.spec, source_width, source_height, width, height)
    if refusal:
        raise AlgorithmError(refusal)
    scale = width / source_width
    progress = params.get("progress")
    # No callback keeps the one batch call. A callback has to run between frames,
    # so those jobs scale one frame at a time.
    if progress is None or registered.spec.needs_gpu:
        opts = {"size": (width, height), "params": params}
        _report(progress, "scale", 0, len(frames))
        scaled = registered.upscale(frames, float(scale), opts)
        _report(progress, "scale", len(frames), len(frames))
    else:
        backend_params = {key: value for key, value in params.items() if key != "progress"}
        opts = {"size": (width, height), "params": backend_params}
        scaled = _scale_frame_by_frame(registered, frames, float(scale), opts, progress, algorithm_id)
    if len(scaled) != len(frames):
        raise AlgorithmError(f"{algorithm_id} returned {len(scaled)} frames for {len(frames)} inputs.")
    return scaled, width, height, algorithm_id


def _scale_frame_by_frame(
    registered: Any,
    frames: list[np.ndarray],
    scale: float,
    opts: dict[str, Any],
    progress: Any,
    algorithm_id: str,
) -> list[np.ndarray]:
    total = len(frames)
    scaled: list[np.ndarray] = []
    _report(progress, "scale", 0, total)
    for index, frame in enumerate(frames):
        one = registered.upscale([frame], scale, opts)
        if len(one) != 1:
            raise AlgorithmError(f"{algorithm_id} returned {len(one)} frames for 1 input.")
        scaled.append(one[0])
        _report(progress, "scale", index + 1, total)
    return scaled


def _save_still(frame: np.ndarray, path: str) -> None:
    from PIL import Image

    pixels = np.clip(np.rint(np.asarray(frame) * 255.0), 0, 255).astype(np.uint8)
    image = Image.fromarray(pixels, "RGBA")
    converted = image
    try:
        if Path(path).suffix.lower() in {".jpg", ".jpeg", ".bmp"}:
            converted = image.convert("RGB")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        converted.save(path)
    finally:
        if converted is not image:
            converted.close()
        image.close()


def _target_size(size: tuple[int, int], params: dict[str, Any]) -> tuple[int, int]:
    width, height = size
    if str(params.get("mode") or "factor") == "dimensions":
        width = int(params.get("width") or 0)
        height = int(params.get("height") or 0)
    else:
        factor = float(params.get("factor") or 1)
        width = max(1, round(width * factor))
        height = max(1, round(height * factor))
    if width < 1 or height < 1:
        raise ValueError("target size must be positive")
    return width, height


def _scale_refusal(spec: Any, source_width: int, source_height: int, width: int, height: int) -> str:
    if (width < source_width or height < source_height) and not spec.supports_downscale:
        return f"{spec.id} does not downscale."
    if not spec.supports_scale:
        return ""
    scale_x = width / source_width
    scale_y = height / source_height
    if any(abs(scale_x - allowed) < 1e-3 and abs(scale_y - allowed) < 1e-3 for allowed in spec.supports_scale):
        return ""
    supported = ", ".join(str(value) for value in sorted(spec.supports_scale))
    return (
        f"{spec.id} supports scales {supported}, not {width}x{height} from {source_width}x{source_height}."
    )
