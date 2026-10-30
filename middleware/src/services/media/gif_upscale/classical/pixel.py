"""Pixel-art GIF scalers. Each algorithm registers on import.

Frames are HxWx4 float32 in 0..1 with straight alpha. ``looks_like_pixel_art``
is a detector only — it is not a resample backend. Border samples are the
nearest edge pixel, which is the published Scale2x rule for out-of-range neighbors.
"""

from __future__ import annotations

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.registry import register_algorithm

# hq2x declares a neighbor different above these YUV gaps on a 0..255 scale.
_HQ_Y = 48.0
_HQ_U = 7.0
_HQ_V = 6.0
_CW_3X3 = (6, 3, 0, 7, 4, 1, 8, 5, 2)
# One 90° turn moves the bottom-right corner test onto the next corner.
_XBR_SLOTS = ((1, 1), (0, 1), (0, 0), (1, 0))


def looks_like_pixel_art(frame: np.ndarray) -> bool:
    """True when some block size >= 2 tiles the frame into constant rectangles.

    An 8x8 image of 4x4 flat blocks passes. A smooth ramp does not: every block
    of size >= 2 contains a step. Native 1x sprites, where each pixel is its own
    color, also return False — this catches integer-scaled pixel art, not a
    palette count.
    """

    image = np.asarray(frame)
    if image.ndim == 2:
        image = image[:, :, None]
    if image.ndim != 3:
        return False
    height, width = int(image.shape[0]), int(image.shape[1])
    if height < 2 or width < 2:
        return False
    channels = int(image.shape[2])
    limit = min(height, width)
    for block in range(2, limit + 1):
        if height % block or width % block:
            continue
        tiles_y = height // block
        tiles_x = width // block
        view = np.ascontiguousarray(image).reshape(tiles_y, block, tiles_x, block, channels)
        if np.all(view == view[:, :1, :, :1, :]):
            return True
    return False


def _available() -> tuple[bool, str]:
    return True, ""


def _as_frame(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame, dtype=np.float32)
    if image.ndim != 3 or image.shape[2] != 4:
        raise AlgorithmError("pixel scalers expect HxWx4 frames.")
    return image


def _is_scale(scale_x: float, scale_y: float, allowed: frozenset[float]) -> bool:
    return any(abs(scale_x - item) < 1e-3 and abs(scale_y - item) < 1e-3 for item in allowed)


def _target_size(
    image: np.ndarray,
    scale: float,
    opts: dict,
    allowed: frozenset[float],
    algorithm_id: str,
) -> tuple[int, int]:
    height, width = int(image.shape[0]), int(image.shape[1])
    if width < 1 or height < 1:
        raise AlgorithmError(f"{algorithm_id} needs a positive frame.")
    size = opts.get("size") if opts else None
    if size:
        target_w, target_h = int(size[0]), int(size[1])
    else:
        factor = float(scale)
        target_w = int(round(width * factor))
        target_h = int(round(height * factor))
    if target_w < 1 or target_h < 1:
        raise AlgorithmError(f"{algorithm_id} needs a positive size.")
    if not allowed:
        return target_w, target_h
    scale_x = target_w / width
    scale_y = target_h / height
    scale_ok = any(abs(float(scale) - item) < 1e-3 for item in allowed)
    if scale_ok and _is_scale(scale_x, scale_y, allowed):
        return target_w, target_h
    supported = ", ".join(str(item) for item in sorted(allowed))
    raise AlgorithmError(
        f"{algorithm_id} supports scales {supported}, not {scale} "
        f"({target_w}x{target_h} from {width}x{height})."
    )


def _map_frames(frames: list[np.ndarray], scale: float, opts: dict, allowed: frozenset[float], algorithm_id: str, expand):
    scaled: list[np.ndarray] = []
    for frame in frames:
        image = _as_frame(frame)
        target_w, target_h = _target_size(image, scale, opts, allowed, algorithm_id)
        output = expand(image)
        if (int(output.shape[0]), int(output.shape[1])) != (target_h, target_w):
            raise AlgorithmError(
                f"{algorithm_id} produced {output.shape[1]}x{output.shape[0]}, expected {target_w}x{target_h}."
            )
        scaled.append(output)
    return scaled


def _register(algorithm_id: str, allowed: frozenset[float], upscale) -> None:
    register_algorithm(
        AlgorithmSpec(
            id=algorithm_id,
            family="pixel",
            content="pixel",
            kind="classical",
            supports_scale=allowed,
            supports_downscale=False,
            needs_gpu=False,
            vram_mb_estimate=0,
            license="MIT",
            weights_sha256=None,
            available=_available,
        ),
        upscale,
    )


def _bind(algorithm_id: str, allowed: frozenset[float], expand) -> None:
    def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
        return _map_frames(frames, scale, opts, allowed, algorithm_id, expand)

    _register(algorithm_id, allowed, upscale)


def _neighbors(frame: np.ndarray) -> dict[str, np.ndarray]:
    padded = np.pad(frame, ((1, 1), (1, 1), (0, 0)), mode="edge")
    return {
        "A": padded[:-2, :-2],
        "B": padded[:-2, 1:-1],
        "C": padded[:-2, 2:],
        "D": padded[1:-1, :-2],
        "E": frame,
        "F": padded[1:-1, 2:],
        "G": padded[2:, :-2],
        "H": padded[2:, 1:-1],
        "I": padded[2:, 2:],
    }


def _eq(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.all(left == right, axis=-1)


def _assemble2(e0: np.ndarray, e1: np.ndarray, e2: np.ndarray, e3: np.ndarray) -> np.ndarray:
    height, width = e0.shape[:2]
    out = np.empty((height * 2, width * 2, e0.shape[2]), dtype=np.float32)
    out[0::2, 0::2] = e0
    out[0::2, 1::2] = e1
    out[1::2, 0::2] = e2
    out[1::2, 1::2] = e3
    return out


def _assemble3(blocks: tuple[np.ndarray, ...]) -> np.ndarray:
    height, width = blocks[0].shape[:2]
    out = np.empty((height * 3, width * 3, blocks[0].shape[2]), dtype=np.float32)
    for index, block in enumerate(blocks):
        row, col = divmod(index, 3)
        out[row::3, col::3] = block
    return out


def _pick(active: np.ndarray, cond: np.ndarray, chosen: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    return np.where((active & cond)[..., None], chosen, fallback)


def _scale2x_frame(frame: np.ndarray) -> np.ndarray:
    """AdvMAME Scale2x. The 2x2 is E0 E1 / E2 E3. If B!=H and D!=F, a corner
    copies the matching orthogonal neighbor; otherwise all four stay E.
    """

    n = _neighbors(frame)
    up, left, center, right, down = n["B"], n["D"], n["E"], n["F"], n["H"]
    active = ~_eq(up, down) & ~_eq(left, right)
    return _assemble2(
        _pick(active, _eq(left, up), left, center),
        _pick(active, _eq(up, right), right, center),
        _pick(active, _eq(left, down), left, center),
        _pick(active, _eq(down, right), right, center),
    )


def _scale3x_frame(frame: np.ndarray) -> np.ndarray:
    """AdvMAME Scale3x. The center of the 3x3 stays E. Other products copy an
    orthogonal neighbor only when B!=H and D!=F and that neighbor's rule matches.
    A straight run fails B!=H or D!=F, so it stays a rectangle rather than a blob.
    """

    n = _neighbors(frame)
    a, up, c = n["A"], n["B"], n["C"]
    left, center, right = n["D"], n["E"], n["F"]
    g, down, i = n["G"], n["H"], n["I"]
    active = ~_eq(up, down) & ~_eq(left, right)
    return _assemble3(
        (
            _pick(active, _eq(left, up), left, center),
            _pick(active, (_eq(left, up) & ~_eq(center, c)) | (_eq(up, right) & ~_eq(center, a)), up, center),
            _pick(active, _eq(up, right), right, center),
            _pick(active, (_eq(left, up) & ~_eq(center, g)) | (_eq(left, down) & ~_eq(center, a)), left, center),
            center,
            _pick(active, (_eq(up, right) & ~_eq(center, i)) | (_eq(down, right) & ~_eq(center, c)), right, center),
            _pick(active, _eq(left, down), left, center),
            _pick(active, (_eq(left, down) & ~_eq(center, i)) | (_eq(down, right) & ~_eq(center, g)), down, center),
            _pick(active, _eq(down, right), right, center),
        )
    )


def _epx_frame(frame: np.ndarray) -> np.ndarray:
    """Eric Johnston's EPX. A quadrant becomes the shared color of its two
    adjacent neighbors when those parents match. Three or more identical
    orthogonal parents leave the center alone; the ``!=`` tests are that
    exception (a parent must differ from the one opposite the other parent).
    """

    n = _neighbors(frame)
    center = n["E"]
    up, left, right, down = n["B"], n["D"], n["F"], n["H"]
    top_left = _eq(left, up) & ~_eq(left, down) & ~_eq(up, right)
    top_right = _eq(up, right) & ~_eq(up, left) & ~_eq(right, down)
    bottom_left = _eq(down, left) & ~_eq(down, right) & ~_eq(left, up)
    bottom_right = _eq(right, down) & ~_eq(right, up) & ~_eq(down, left)
    return _assemble2(
        np.where(top_left[..., None], up, center),
        np.where(top_right[..., None], right, center),
        np.where(bottom_left[..., None], left, center),
        np.where(bottom_right[..., None], down, center),
    )


def _luma(color: np.ndarray) -> np.ndarray:
    rgb = color[..., :3]
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _ydf(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.abs(_luma(left) - _luma(right))


def _xbr_corner(
    center: np.ndarray,
    up: np.ndarray,
    up_right: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    down_left: np.ndarray,
    down: np.ndarray,
    down_right: np.ndarray,
) -> np.ndarray:
    """One corner of Hyllian's xBR lv1 test. ``down_right`` is the diagonal.

    The half mix is the discrete 2x corner: the shader ramps across that same
    quadrant, and a hard step lands strictly between the two colors.
    """

    near = _ydf(down_left, center) + _ydf(center, up_right) + 3.0 * _ydf(down, right)
    far = _ydf(up, right) + _ydf(left, down) + 3.0 * _ydf(center, down_right)
    # lv0 only. Hyllian's stricter CORNER_C gate also requires a neighbor equality
    # that rejects this square stair, so the corner would stay a hard nearest step.
    edge = (near < far) & ~_eq(center, right) & ~_eq(center, down)
    choose_right = _ydf(center, right) <= _ydf(center, down)
    target = np.where(choose_right[..., None], right, down)
    mixed = (center + target) * np.float32(0.5)
    return np.where(edge[..., None], mixed, center).astype(np.float32, copy=False)


def _turn(neighborhood: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    return tuple(neighborhood[index] for index in _CW_3X3)


def _xbrz_frame(frame: np.ndarray) -> np.ndarray:
    """2x xBR-style corner scaler (lv1 3x3 distance, not the full xBRZ kernel).

    Flat regions fail the strict distance test and stay copies of E. A one-pixel
    stair blends the outer corner. Scales other than 2 are refused by the registry
    wrapper. This is an original port of the published rule, not zenju's xBRZ table.
    """

    n = _neighbors(frame)
    neighborhood = (n["A"], n["B"], n["C"], n["D"], n["E"], n["F"], n["G"], n["H"], n["I"])
    height, width = frame.shape[:2]
    out = np.empty((height * 2, width * 2, 4), dtype=np.float32)
    out[0::2, 0::2] = frame
    out[0::2, 1::2] = frame
    out[1::2, 0::2] = frame
    out[1::2, 1::2] = frame
    for slot_y, slot_x in _XBR_SLOTS:
        _a, up, up_right, left, _center, right, down_left, down, down_right = neighborhood
        out[slot_y::2, slot_x::2] = _xbr_corner(frame, up, up_right, left, right, down_left, down, down_right)
        neighborhood = _turn(neighborhood)
    return out


def _hq_yuv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = (red + green + blue) * (0.25 * (63.5 / 48.0))
    u = ((red - blue) * 0.25 + 128.0) * (7.5 / 7.0)
    v = ((green * 2.0 - red - blue) * 0.125 + 128.0) * (7.5 / 6.0)
    return y, u, v


def _hq_differs(center: np.ndarray, neighbor: np.ndarray) -> np.ndarray:
    y1, u1, v1 = _hq_yuv(center[..., :3] * 255.0)
    y2, u2, v2 = _hq_yuv(neighbor[..., :3] * 255.0)
    return (np.abs(y1 - y2) > _HQ_Y) | (np.abs(u1 - u2) > _HQ_U) | (np.abs(v1 - v2) > _HQ_V)


def _hq_luma(color: np.ndarray) -> np.ndarray:
    rgb = color[..., :3] * 255.0
    return (rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) * (0.25 * (63.5 / 48.0))


def _hqx_frame(frame: np.ndarray) -> np.ndarray:
    """Reduced hq2x.

    Difference bits use Maxim Stepin's YUV thresholds (Y>48, U>7, V>6). Covered
    cases: no difference (including a solid field) is a 2x2 copy; a hard
    luminance step (Y gap > 48, including a pure black/white checker) is also a
    2x2 copy so the palette is not grayed; a diagonal that differs only in
    chroma mixes that corner 3:1 toward the neighbor. Orthogonal patterns and
    the full 256-entry hq2x table are not in this port.
    """

    n = _neighbors(frame)
    center = n["E"]
    out = _assemble2(center, center, center, center)
    # Diagonal corners of the 2x2, in E0 E1 / E2 E3 order.
    diagonals = (n["A"], n["C"], n["G"], n["I"])
    slots = ((0, 0), (0, 1), (1, 0), (1, 1))
    for (slot_y, slot_x), diagonal in zip(slots, diagonals, strict=True):
        differs = _hq_differs(center, diagonal)
        # A set bit with luma still under 48 is chroma. Hard black/white fails
        # that test, so the checker stays on the two source colors.
        mild = differs & (np.abs(_hq_luma(center) - _hq_luma(diagonal)) < _HQ_Y)
        mixed = (center * np.float32(3.0) + diagonal) * np.float32(0.25)
        view = out[slot_y::2, slot_x::2]
        out[slot_y::2, slot_x::2] = np.where(mild[..., None], mixed, view)
    return out


def _upscale_integer(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    """Repeat each pixel by a positive integer factor. Alpha is copied, not mixed."""

    scaled: list[np.ndarray] = []
    for frame in frames:
        image = _as_frame(frame)
        target_w, target_h = _target_size(image, scale, opts, frozenset(), "integer-nearest")
        height, width = int(image.shape[0]), int(image.shape[1])
        if target_w % width or target_h % height or target_w < width or target_h < height:
            raise AlgorithmError(
                f"integer-nearest supports integer multiples only, not {target_w}x{target_h} from {width}x{height}."
            )
        scaled.append(np.repeat(np.repeat(image, target_h // height, axis=0), target_w // width, axis=1))
    return scaled


_bind("scale2x", frozenset({2.0}), _scale2x_frame)
_bind("scale3x", frozenset({3.0}), _scale3x_frame)
_bind("epx", frozenset({2.0}), _epx_frame)
_bind("xbrz", frozenset({2.0}), _xbrz_frame)
_bind("hqx", frozenset({2.0}), _hqx_frame)
_register("integer-nearest", frozenset(), _upscale_integer)
