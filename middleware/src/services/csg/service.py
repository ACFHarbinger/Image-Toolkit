"""Cel-Shaded Generator (CSG) service implementation.

Canonical service home for CSG colorization, puppeteering, and animation
propagation (W0-03 Phase C, #867). Unblocks Wave 8 editor #916 E-03.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from middleware.src.services._submodule_loader import ensure_submodules_registered
from middleware.src.services.base import CommandValidationError
from middleware.src.services.csg.commands import (
    ArapDeformCommand,
    ArapDeformResult,
    ColorizeReferenceCommand,
    ColorizeReferenceResult,
    ColorizeScribbleCommand,
    ColorizeScribbleResult,
    TemporalPropagateCommand,
    TemporalPropagateResult,
)
from middleware.src.services.csg.protocols import CsgServiceProtocol

# Pixels at or above this level in every channel are paper, not the subject.
_NEAR_WHITE = 250
# Channel spread below this is gray line art, not a color scribble.
_SCRIBBLE_SPREAD = 16
_EMPTY_SCRIBBLE = "scribble mask is empty"


def _error_text(exc: BaseException) -> str:
    text = str(exc)
    if isinstance(exc, ImportError) and "unavailable" not in text.lower():
        return f"CSG backend unavailable: {text}"
    return text


def _backend(loader: Callable[[], Any]) -> Any:
    try:
        return loader()
    except Exception as exc:
        raise ImportError(f"CSG backend unavailable: {exc}") from exc


def _load_scribble() -> Any:
    from colorization.colorization import colorize_scribble

    return colorize_scribble


def _load_reference() -> Any:
    from colorization.optimal_transport import colorize_reference

    return colorize_reference


def _load_arap() -> tuple[Any, Any]:
    from rigging.arap import arap_deform, generate_mesh

    return generate_mesh, arap_deform


def _load_sequence() -> Any:
    from temporal.temporal import colorize_scribble_sequence

    return colorize_scribble_sequence


def _read_rgb(path: str) -> np.ndarray:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(rgb)


def _fit_rgb(rgb: np.ndarray, height: int, width: int) -> np.ndarray:
    if rgb.shape[0] == height and rgb.shape[1] == width:
        return np.ascontiguousarray(rgb)
    # Nearest keeps a one-pixel stroke from being blended into gray.
    resized = Image.fromarray(rgb, mode="RGB").resize((width, height), Image.Resampling.NEAREST)
    return np.ascontiguousarray(np.asarray(resized, dtype=np.uint8))


def _luminance(rgb: np.ndarray) -> np.ndarray:
    acc = (
        rgb[..., 0].astype(np.uint16) * 299
        + rgb[..., 1].astype(np.uint16) * 587
        + rgb[..., 2].astype(np.uint16) * 114
    )
    return np.ascontiguousarray((acc // 1000).astype(np.uint8))


def _colored_mask(rgb: np.ndarray) -> np.ndarray:
    channels = rgb.astype(np.int16)
    spread = channels.max(axis=2) - channels.min(axis=2)
    return spread >= _SCRIBBLE_SPREAD


def _subject_mask(rgb: np.ndarray) -> np.ndarray:
    ink = np.any(rgb < _NEAR_WHITE, axis=-1)
    if float(ink.mean()) >= 0.9:
        return np.ones(ink.shape, dtype=bool)
    return ink


def _mesh_step(mask: np.ndarray, requested: int) -> int:
    """Clamp the requested grid step until at least three mask samples remain.

    ``generate_mesh`` refuses a grid with fewer than three interior points.
    A 64×64 frame at step 32 is enough; a coarser request is halved until
    the mask can form a triangle.
    """
    height, width = mask.shape
    step = int(requested) if requested and int(requested) > 0 else 16
    step = max(1, step)
    while step > 1:
        ys = np.arange(0, height, step)
        xs = np.arange(0, width, step)
        if int(mask[np.ix_(ys, xs)].sum()) >= 3:
            return step
        step //= 2
    return 1


def _anchors(
    vertices: np.ndarray,
    control_points: tuple[tuple[float, float], ...],
    target_points: tuple[tuple[float, float], ...],
) -> dict[int, tuple[float, float]]:
    anchors: dict[int, tuple[float, float]] = {}
    if len(vertices) == 0:
        return anchors
    for (cx, cy), (tx, ty) in zip(control_points, target_points, strict=True):
        dist = (vertices[:, 0] - float(cx)) ** 2 + (vertices[:, 1] - float(cy)) ** 2
        anchors[int(np.argmin(dist))] = (float(tx), float(ty))
    return anchors


def _warp_rgb(rgb: np.ndarray, rest: np.ndarray, moved: np.ndarray) -> np.ndarray:
    import cv2
    from scipy.interpolate import griddata

    height, width = rgb.shape[:2]
    disp = np.asarray(moved, dtype=np.float64) - np.asarray(rest, dtype=np.float64)
    yy, xx = np.mgrid[0:height, 0:width]
    sampled = griddata(np.asarray(rest, dtype=np.float64), disp, (xx, yy), method="linear")
    if sampled is None or np.isnan(sampled).any():
        nearest = griddata(np.asarray(rest, dtype=np.float64), disp, (xx, yy), method="nearest")
        if sampled is None:
            sampled = nearest
        else:
            missing = np.isnan(sampled).any(axis=-1)
            sampled = np.where(missing[..., None], nearest, sampled)
    map_x = (xx - sampled[..., 0]).astype(np.float32)
    map_y = (yy - sampled[..., 1]).astype(np.float32)
    return cv2.remap(
        rgb,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def _as_rgb_uint8(rgb: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgb)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"CSG output is not HxWx3 RGB, got shape {arr.shape}")
    return np.ascontiguousarray(arr)


def _save_png(path: str | Path, rgb: np.ndarray) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    try:
        Image.fromarray(_as_rgb_uint8(rgb), mode="RGB").save(partial, format="PNG")
        if partial.stat().st_size <= 0:
            raise ValueError("CSG writer produced an empty file")
        partial.replace(dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return dest


def _unlink_created(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue


def _elapsed(t0: float) -> float:
    return round(time.monotonic() - t0, 4)


def _sequence_arrays(
    command: TemporalPropagateCommand,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frames = [_read_rgb(path) for path in command.frame_paths]
    height, width = frames[0].shape[:2]
    fitted = [_fit_rgb(frame, height, width) for frame in frames]
    gray = np.stack([_luminance(frame) for frame in fitted], axis=0)
    colors = np.zeros((len(fitted), height, width, 3), dtype=np.uint8)
    mask = np.zeros((len(fitted), height, width), dtype=bool)
    index = command.keyframe_index
    if index < 0 or index >= len(fitted):
        raise ValueError(f"keyframe_index out of range: {index}")
    color_path = command.keyframe_color_path
    if color_path and os.path.isfile(color_path):
        scribble = _fit_rgb(_read_rgb(color_path), height, width)
    else:
        scribble = fitted[index]
    colors[index] = scribble
    mask[index] = _colored_mask(scribble)
    return gray, colors, mask


class CsgService(CsgServiceProtocol):
    """Canonical domain service for cel-shaded colorization and puppeteering."""

    def __init__(self, csg_delegate: Any = None) -> None:
        """Initialize CsgService with optional delegate."""
        self._delegate = csg_delegate
        ensure_submodules_registered()

    def colorize_scribble(self, command: ColorizeScribbleCommand) -> ColorizeScribbleResult:
        """Colorize lineart using scribble guidance."""
        t0 = time.monotonic()
        if not os.path.isfile(command.lineart_path):
            raise CommandValidationError(
                f"Lineart path does not exist: {command.lineart_path}", field="lineart_path"
            )
        if not os.path.isfile(command.scribble_path):
            raise CommandValidationError(
                f"Scribble path does not exist: {command.scribble_path}", field="scribble_path"
            )

        written: list[Path] = []
        try:
            if self._delegate is not None and hasattr(self._delegate, "colorize_scribble"):
                return self._delegate.colorize_scribble(command)

            lineart = _read_rgb(command.lineart_path)
            height, width = lineart.shape[:2]
            scribble = _fit_rgb(_read_rgb(command.scribble_path), height, width)
            mask = _colored_mask(scribble)
            if not np.any(mask):
                return ColorizeScribbleResult(
                    success=False,
                    elapsed_seconds=_elapsed(t0),
                    error=_EMPTY_SCRIBBLE,
                )
            colorize = _backend(_load_scribble)
            rgb = _as_rgb_uint8(colorize(_luminance(lineart), scribble, mask))
            if command.output_path:
                written.append(_save_png(command.output_path, rgb))
            out_h, out_w = rgb.shape[:2]
            return ColorizeScribbleResult(
                success=True,
                output_path=command.output_path,
                width=int(out_w),
                height=int(out_h),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            _unlink_created(written)
            return ColorizeScribbleResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=_error_text(exc),
            )

    def colorize_reference(self, command: ColorizeReferenceCommand) -> ColorizeReferenceResult:
        """Transfer colors from style reference onto target lineart."""
        t0 = time.monotonic()
        if not os.path.isfile(command.lineart_path):
            raise CommandValidationError(
                f"Lineart path does not exist: {command.lineart_path}", field="lineart_path"
            )
        if not os.path.isfile(command.reference_path):
            raise CommandValidationError(
                f"Reference path does not exist: {command.reference_path}", field="reference_path"
            )

        written: list[Path] = []
        try:
            if self._delegate is not None and hasattr(self._delegate, "colorize_reference"):
                return self._delegate.colorize_reference(command)

            lineart = _read_rgb(command.lineart_path)
            reference = _read_rgb(command.reference_path)
            colorize = _backend(_load_reference)
            rgb = _as_rgb_uint8(
                colorize(_luminance(lineart), reference, epsilon=float(command.epsilon))
            )
            if command.output_path:
                written.append(_save_png(command.output_path, rgb))
            out_h, out_w = rgb.shape[:2]
            return ColorizeReferenceResult(
                success=True,
                output_path=command.output_path,
                width=int(out_w),
                height=int(out_h),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            _unlink_created(written)
            return ColorizeReferenceResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=_error_text(exc),
            )

    def arap_deform(self, command: ArapDeformCommand) -> ArapDeformResult:
        """Perform As-Rigid-As-Possible 2D mesh deformation."""
        t0 = time.monotonic()
        if not os.path.isfile(command.image_path):
            raise CommandValidationError(
                f"Image path does not exist: {command.image_path}", field="image_path"
            )
        if len(command.control_points) != len(command.target_points):
            raise CommandValidationError(
                "Control points and target points must have identical lengths",
                field="control_points",
            )

        written: list[Path] = []
        try:
            if self._delegate is not None and hasattr(self._delegate, "arap_deform"):
                return self._delegate.arap_deform(command)

            rgb = _read_rgb(command.image_path)
            mask = _subject_mask(rgb)
            generate_mesh, deform = _backend(_load_arap)
            vertices, triangles = generate_mesh(mask, _mesh_step(mask, command.mesh_resolution))
            if len(vertices) < 1 or len(triangles) < 1:
                raise ValueError("mesh cannot be built")
            anchors = _anchors(vertices, command.control_points, command.target_points)
            moved = deform(vertices, triangles, anchors)
            warped = _warp_rgb(rgb, vertices, moved)
            if command.output_path:
                written.append(_save_png(command.output_path, warped))
            return ArapDeformResult(
                success=True,
                output_path=command.output_path,
                num_vertices=int(len(vertices)),
                num_triangles=int(len(triangles)),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            _unlink_created(written)
            return ArapDeformResult(
                success=False,
                elapsed_seconds=_elapsed(t0),
                error=_error_text(exc),
            )

    def propagate_sequence(self, command: TemporalPropagateCommand) -> TemporalPropagateResult:
        """Propagate colorization temporally across a sequence of animation frames."""
        t0 = time.monotonic()
        if not command.frame_paths:
            raise CommandValidationError(
                "Temporal propagation requires at least one frame path", field="frame_paths"
            )

        for frame_path in command.frame_paths:
            if not os.path.isfile(frame_path):
                return TemporalPropagateResult(
                    success=False,
                    frames_processed=0,
                    elapsed_seconds=_elapsed(t0),
                    error=f"Frame file does not exist: {frame_path}",
                )

        written: list[Path] = []
        try:
            if self._delegate is not None and hasattr(self._delegate, "propagate_sequence"):
                return self._delegate.propagate_sequence(command)

            gray, colors, mask = _sequence_arrays(command)
            if not np.any(mask):
                return TemporalPropagateResult(
                    success=False,
                    frames_processed=0,
                    elapsed_seconds=_elapsed(t0),
                    error=_EMPTY_SCRIBBLE,
                )
            propagate = _backend(_load_sequence)
            stack = propagate(gray, colors, mask)
            if getattr(stack, "shape", (0,))[0] != gray.shape[0]:
                raise ValueError("temporal colorization did not return one frame per input")
            output_paths: list[str] = []
            if command.output_dir:
                for index in range(stack.shape[0]):
                    dest = Path(command.output_dir) / f"colorized_{index:04d}.png"
                    written.append(_save_png(dest, stack[index]))
                    output_paths.append(str(dest))
            return TemporalPropagateResult(
                success=True,
                output_paths=tuple(output_paths),
                frames_processed=len(output_paths),
                elapsed_seconds=_elapsed(t0),
            )
        except Exception as exc:
            _unlink_created(written)
            return TemporalPropagateResult(
                success=False,
                frames_processed=0,
                elapsed_seconds=_elapsed(t0),
                error=_error_text(exc),
            )
