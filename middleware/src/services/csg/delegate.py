"""CSG solver delegate.

Calls the cel-shaded generator in ``submodules/CSG`` and writes the image it
returns. A missing solver is an unavailable result. This module does not
invent dimensions or write an empty file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

SOLVER_UNAVAILABLE = "CSG solver is unavailable"


class SubmoduleCsgDelegate:
    """Run the in-repo CSG solvers. Imports stay inside each call."""

    def colorize_scribble(self, command: ColorizeScribbleCommand) -> ColorizeScribbleResult:
        loaded = _load_runtime()
        if loaded is None:
            return ColorizeScribbleResult(success=False, error=SOLVER_UNAVAILABLE)
        cv2, np = loaded
        try:
            gray, scribble_rgb, mask = _scribble_inputs(cv2, np, command.lineart_path, command.scribble_path)
            if command.use_screentone:
                from colorization.screentone import colorize_scribble_screentone as solve
            else:
                from colorization.colorization import colorize_scribble as solve
            colored = solve(gray, scribble_rgb, mask)
            if command.intensity < 1.0:
                colored = _blend_intensity(np, gray, colored, command.intensity)
            path = _write_rgb(cv2, colored, _png_path(command.output_path, command.lineart_path, ".csg"))
        except Exception as exc:
            return ColorizeScribbleResult(success=False, error=str(exc))
        height, width = colored.shape[:2]
        return ColorizeScribbleResult(success=True, output_path=path, width=int(width), height=int(height))

    def colorize_reference(self, command: ColorizeReferenceCommand) -> ColorizeReferenceResult:
        loaded = _load_runtime()
        if loaded is None:
            return ColorizeReferenceResult(success=False, error=SOLVER_UNAVAILABLE)
        cv2, np = loaded
        try:
            gray = _read_gray(cv2, command.lineart_path)
            reference = _read_rgb(cv2, command.reference_path)
            from colorization.optimal_transport import colorize_reference

            segments = _segment_budget(gray.shape[0] * gray.shape[1])
            colored = colorize_reference(
                gray,
                reference,
                n_segments_target=segments,
                n_segments_reference=segments,
                epsilon=command.epsilon if command.epsilon > 0 else 0.01,
            )
            path = _write_rgb(cv2, colored, _png_path(command.output_path, command.lineart_path, ".csg"))
        except Exception as exc:
            return ColorizeReferenceResult(success=False, error=str(exc))
        height, width = colored.shape[:2]
        return ColorizeReferenceResult(success=True, output_path=path, width=int(width), height=int(height))

    def arap_deform(self, command: ArapDeformCommand) -> ArapDeformResult:
        loaded = _load_runtime()
        if loaded is None:
            return ArapDeformResult(success=False, error=SOLVER_UNAVAILABLE)
        cv2, np = loaded
        try:
            image = _read_bgr(cv2, command.image_path)
            from rigging.arap import arap_deform, generate_mesh

            mask = np.ones(image.shape[:2], dtype=bool)
            vertices, _triangles = generate_mesh(mask, grid_step=_grid_step(image.shape, command.mesh_resolution))
            # generate_mesh samples arange(0, dimension, step), so the grid stops
            # short of the far pixel edge. The rasterizer leaves that strip black.
            vertices, triangles = _cover_image_rect(np, vertices, image.shape[0], image.shape[1])
            anchors = _anchors(np, vertices, command.control_points, command.target_points)
            deformed = arap_deform(vertices, triangles, anchors)
            warped = _warp_bgr(cv2, np, image, vertices, deformed, triangles)
            path = _write_bgr(cv2, warped, _png_path(command.output_path, command.image_path, ".csg-arap"))
        except Exception as exc:
            return ArapDeformResult(success=False, error=str(exc))
        return ArapDeformResult(
            success=True,
            output_path=path,
            num_vertices=int(vertices.shape[0]),
            num_triangles=int(triangles.shape[0]),
        )

    def propagate_sequence(self, command: TemporalPropagateCommand) -> TemporalPropagateResult:
        loaded = _load_runtime()
        if loaded is None:
            return TemporalPropagateResult(success=False, error=SOLVER_UNAVAILABLE)
        cv2, np = loaded
        try:
            if not command.keyframe_color_path or not Path(command.keyframe_color_path).is_file():
                raise ValueError("keyframe color is required for temporal propagation")
            gray_stack, scribble_rgb, mask = _sequence_inputs(cv2, np, command)
            from temporal.temporal import colorize_scribble_sequence

            colored = colorize_scribble_sequence(gray_stack, scribble_rgb, mask)
            output_dir = (
                Path(command.output_dir) if command.output_dir else Path(command.frame_paths[0]).parent / "csg-sequence"
            )
            paths = _write_sequence(cv2, colored, output_dir)
        except Exception as exc:
            return TemporalPropagateResult(success=False, frames_processed=0, error=str(exc))
        return TemporalPropagateResult(success=True, output_paths=tuple(paths), frames_processed=len(paths))


def _load_runtime() -> tuple[Any, Any] | None:
    from middleware.src.services._submodule_loader import ensure_submodules_registered

    ensure_submodules_registered()
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    return cv2, np


def _png_path(requested: str | None, source: str, suffix: str) -> str:
    if requested:
        return requested
    src = Path(source)
    return str(src.with_name(f"{src.stem}{suffix}.png"))


def _read_bgr(cv2: Any, path: str) -> Any:
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not read image: {path}")
    return image


def _read_gray(cv2: Any, path: str) -> Any:
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"could not read image: {path}")
    return image


def _read_rgb(cv2: Any, path: str) -> Any:
    image = _read_bgr(cv2, path)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _scribble_inputs(cv2: Any, np: Any, lineart_path: str, scribble_path: str) -> tuple[Any, Any, Any]:
    gray = _read_gray(cv2, lineart_path)
    scribble = _read_rgb(cv2, scribble_path)
    if scribble.shape[:2] != gray.shape:
        scribble = cv2.resize(scribble, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST)
    chroma = scribble.max(axis=2).astype(np.int16) - scribble.min(axis=2).astype(np.int16)
    mask = chroma > 16
    if not np.any(mask):
        raise ValueError("scribble has no color marks")
    return gray, scribble, mask


def _blend_intensity(np: Any, gray: Any, colored: Any, intensity: float) -> Any:
    import cv2

    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB).astype(np.float32)
    mixed = base * (1.0 - intensity) + colored.astype(np.float32) * intensity
    return np.clip(mixed, 0, 255).astype(np.uint8)


def _segment_budget(pixels: int) -> int:
    return max(8, min(80, pixels // 32))


def _write_rgb(cv2: Any, rgb: Any, path: str) -> str:
    return _write_bgr(cv2, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), path)


def _write_bgr(cv2: Any, bgr: Any, path: str) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), bgr):
        raise ValueError(f"failed to write image: {destination}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ValueError(f"solver wrote an empty image: {destination}")
    return str(destination)


def _grid_step(shape: tuple[int, ...], requested: int) -> int:
    height, width = shape[:2]
    step = requested if requested > 0 else 16
    while step > 1 and (height // step) * (width // step) < 16:
        step //= 2
    return max(step, 1)


def _cover_image_rect(np: Any, vertices: Any, height: int, width: int) -> tuple[Any, Any]:
    """Rebuild the sampled grid so every pixel center lies inside a triangle.

    OpenCV fills a pixel when its center is inside the polygon. A vertex on
    the last pixel index (``width - 1``) leaves that column outside, so the
    far edge is the exclusive bound ``width`` / ``height``.
    """
    if height < 1 or width < 1 or len(vertices) == 0:
        return vertices, np.zeros((0, 3), dtype=np.int64)
    xs = np.unique(vertices[:, 0].astype(np.float64))
    ys = np.unique(vertices[:, 1].astype(np.float64))
    right = float(width)
    bottom = float(height)
    if xs[0] > 0:
        xs = np.insert(xs, 0, 0.0)
    if ys[0] > 0:
        ys = np.insert(ys, 0, 0.0)
    if xs[-1] < right:
        xs = np.append(xs, right)
    if ys[-1] < bottom:
        ys = np.append(ys, bottom)
    grid_x, grid_y = np.meshgrid(xs, ys, indexing="xy")
    covered = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1).astype(np.float64)
    nx = int(xs.size)
    ny = int(ys.size)
    tris: list[tuple[int, int, int]] = []
    for row in range(ny - 1):
        for col in range(nx - 1):
            origin = row * nx + col
            tris.append((origin, origin + 1, origin + nx + 1))
            tris.append((origin, origin + nx + 1, origin + nx))
    return covered, np.asarray(tris, dtype=np.int64)


def _anchors(
    np: Any,
    vertices: Any,
    control_points: tuple[tuple[float, float], ...],
    target_points: tuple[tuple[float, float], ...],
) -> dict[int, tuple[float, float]]:
    anchors: dict[int, tuple[float, float]] = {}
    for (cx, cy), (tx, ty) in zip(control_points, target_points, strict=True):
        distance = np.hypot(vertices[:, 0] - cx, vertices[:, 1] - cy)
        anchors[int(np.argmin(distance))] = (float(tx), float(ty))
    if not anchors:
        raise ValueError("ARAP deformation requires a control point")
    return anchors


def _warp_bgr(cv2: Any, np: Any, image: Any, src_vertices: Any, dst_vertices: Any, triangles: Any) -> Any:
    height, width = image.shape[:2]
    canvas = np.zeros_like(image)
    for tri in triangles:
        src = np.asarray(src_vertices[tri], dtype=np.float32)
        dst = np.asarray(dst_vertices[tri], dtype=np.float32)
        if cv2.contourArea(src.reshape(-1, 1, 2)) < 0.5 or cv2.contourArea(dst.reshape(-1, 1, 2)) < 0.5:
            continue
        matrix = cv2.getAffineTransform(src, dst)
        warped = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillConvexPoly(mask, np.round(dst).astype(np.int32), 255)
        canvas[mask > 0] = warped[mask > 0]
    if int(canvas.sum()) == 0:
        raise ValueError("ARAP warp produced an empty image")
    return canvas


def _sequence_inputs(cv2: Any, np: Any, command: TemporalPropagateCommand) -> tuple[Any, Any, Any]:
    frames = [_read_gray(cv2, path) for path in command.frame_paths]
    height, width = frames[0].shape
    aligned = [
        frame if frame.shape == (height, width) else cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        for frame in frames
    ]
    gray_stack = np.stack(aligned)
    count = gray_stack.shape[0]
    scribble_rgb = np.zeros((count, height, width, 3), dtype=np.uint8)
    mask = np.zeros((count, height, width), dtype=bool)
    index = min(max(command.keyframe_index, 0), count - 1)
    color = _read_rgb(cv2, command.keyframe_color_path)
    if color.shape[:2] != (height, width):
        color = cv2.resize(color, (width, height), interpolation=cv2.INTER_NEAREST)
    chroma = color.max(axis=2).astype(np.int16) - color.min(axis=2).astype(np.int16)
    frame_mask = chroma > 16
    if not np.any(frame_mask):
        raise ValueError("keyframe color has no color marks")
    scribble_rgb[index] = color
    mask[index] = frame_mask
    return gray_stack, scribble_rgb, mask


def _write_sequence(cv2: Any, colored: Any, output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, frame in enumerate(colored):
        paths.append(_write_rgb(cv2, frame, str(output_dir / f"colorized_{index:04d}.png")))
    return paths
