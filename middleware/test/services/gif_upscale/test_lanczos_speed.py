"""One Lanczos3-dering frame, not a corpus run."""

from __future__ import annotations

import time

import numpy as np
from middleware.src.services.media.gif_upscale.classical import _resize
from middleware.src.services.media.gif_upscale.registry import get_algorithm

_LEVEL = 1.0 / 255.0


def _frame(height: int, width: int, *, alpha: float | np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = rng.random((height, width, 4), dtype=np.float64).astype(np.float32)
    frame[..., 3] = np.float32(alpha)
    return frame


def _step(height: int, width: int, lo: float, hi: float, *, alpha: float = 1.0) -> np.ndarray:
    frame = np.full((height, width, 4), lo, dtype=np.float32)
    frame[:, width // 2 :, :3] = np.float32(hi)
    frame[..., 3] = np.float32(alpha)
    return frame


def _mask_reference(frame: np.ndarray, dst_w: int, dst_h: int) -> np.ndarray:
    """Today's tap-and-mask kernel, including premultiply, with no plan cache."""
    kernel = _resize.lanczos_kernel(3.0)
    premul = _resize._premultiply(np.asarray(frame, dtype=np.float32))
    src_h, src_w = premul.shape[:2]
    x_index, x_weight, x_valid = _resize._axis_plan(src_w, dst_w, 3.0, kernel, "lanczos3-dering")
    y_index, y_weight, y_valid = _resize._axis_plan(src_h, dst_h, 3.0, kernel, "lanczos3-dering")
    wide = _resize._apply_taps(premul, x_index, x_weight)
    tall = np.ascontiguousarray(np.swapaxes(wide, 0, 1))
    high = _resize._apply_taps(tall, y_index, y_weight)
    filtered = np.ascontiguousarray(np.swapaxes(high, 0, 1))
    _resize._clamp_rgb_to_neighborhood(filtered, premul[..., :3], y_index, y_valid, x_index, x_valid, "lanczos3-dering")
    return np.clip(_resize._unpremultiply(filtered), 0.0, 1.0).astype(np.float32)


def _upscale(frame: np.ndarray, size: tuple[int, int], params: dict | None = None, *, opts: dict | None = None):
    if opts is None:
        opts = {"size": size}
        if params is not None:
            opts["params"] = params
    out = get_algorithm("lanczos3-dering").upscale([frame], size[0] / frame.shape[1], opts)[0]
    return out, opts


def _visible_max_abs(actual: np.ndarray, reference: np.ndarray) -> float:
    visible = reference[..., 3] > 0.0
    if not np.any(visible):
        return 0.0
    return float(np.max(np.abs(actual[visible] - reference[visible])))


def test_lanczos3_dering_one_frame_finishes_under_eight_seconds() -> None:
    frame = np.zeros((270, 480, 4), dtype=np.float32)
    frame[..., 3] = 1.0
    frame[:, 240:, :3] = 1.0
    started = time.perf_counter()
    out = get_algorithm("lanczos3-dering").upscale([frame], 2.0, {"size": (960, 540)})[0]
    elapsed = time.perf_counter() - started
    print(f"lanczos3-dering 480x270->960x540 {elapsed:.6f}s")
    assert elapsed < 8.0, f"lanczos3-dering took {elapsed:.3f}s"
    assert out.shape == (540, 960, 4)
    assert out.dtype == np.float32
    assert np.isfinite(out).all()
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0
    edge = out[out.shape[0] // 2, :, 0]
    assert float(edge.min()) < 0.05
    assert float(edge.max()) > 0.95
    assert np.any((edge > 0.05) & (edge < 0.95))


def test_exact_matches_the_mask_kernel_bit_for_bit() -> None:
    opaque = _frame(12, 16, alpha=1.0, seed=0)
    translucent = _frame(12, 16, alpha=0.0, seed=1)
    translucent[..., 3] = np.linspace(0.15, 0.9, 16, dtype=np.float32)[None, :]
    for frame in (opaque, translucent):
        reference = _mask_reference(frame, 32, 24)
        fresh, fresh_opts = _upscale(frame, (32, 24), {"quality": "exact"})
        cached, _cached_opts = _upscale(frame, (32, 24), opts=fresh_opts)
        assert fresh_opts["_scale_path"] == "cpu-taps-mask"
        assert np.array_equal(fresh, reference)
        assert np.array_equal(cached, reference)
        assert fresh.shape == (24, 32, 4)
        assert fresh.dtype == np.float32
        assert np.isfinite(fresh).all()
        assert float(fresh.min()) >= 0.0
        assert float(fresh.max()) <= 1.0


def test_balanced_upscale_stays_within_one_level() -> None:
    frame = _step(12, 16, 0.0, 1.0)
    frame[:, :, 1] = 0.25
    frame[:, 8:, 1] = 0.75
    reference = _mask_reference(frame, 32, 24)
    started = time.perf_counter()
    out, opts = _upscale(frame, (32, 24))
    elapsed = time.perf_counter() - started
    diff = _visible_max_abs(out, reference)
    print(f"balanced vs exact max abs {diff:.3e} on 16x12->32x24 in {elapsed:.6f}s")
    assert opts["_scale_path"] == "cpu-sgemm-opencv"
    assert diff <= _LEVEL
    assert np.all(out[..., 3] == np.float32(1.0))
    assert out.shape == (24, 32, 4)
    assert np.isfinite(out).all()
    assert float(out.min()) >= 0.0 and float(out.max()) <= 1.0
    partial = _frame(12, 16, alpha=0.4, seed=2)
    partial_out, partial_opts = _upscale(partial, (32, 24), {"quality": "balanced"})
    partial_diff = _visible_max_abs(partial_out, _mask_reference(partial, 32, 24))
    print(f"balanced translucent max abs {partial_diff:.3e} on 16x12->32x24")
    assert partial_opts["_scale_path"] == "cpu-sgemm-opencv"
    assert partial_diff <= _LEVEL
    assert np.isfinite(partial_out).all()
    assert float(partial_out.min()) >= 0.0 and float(partial_out.max()) <= 1.0


def test_downscale_and_exact_quality_stay_on_the_mask_path() -> None:
    frame = _frame(12, 16, alpha=1.0, seed=3)
    down, down_opts = _upscale(frame, (8, 6), {"quality": "balanced"})
    assert down_opts["_scale_path"] == "cpu-taps-mask"
    assert np.array_equal(down, _mask_reference(frame, 8, 6))
    exact, exact_opts = _upscale(frame, (32, 24), {"quality": "exact"})
    assert exact_opts["_scale_path"] == "cpu-taps-mask"
    assert "sgemm" not in exact_opts["_scale_path"]
    omitted_down, omitted_opts = _upscale(frame, (8, 6))
    assert omitted_opts["_scale_path"] == "cpu-taps-mask"
    assert down.shape == (6, 8, 4) and np.isfinite(down).all()


def test_mismatched_window_and_missing_cv2_fall_back(monkeypatch) -> None:
    # 6->10 drops an in-range +3 tap, so the 6x6 box is not the active window.
    frame = _step(6, 8, 0.0, 1.0)
    out, opts = _upscale(frame, (16, 10), {"quality": "balanced"})
    assert opts["_scale_path"] == "cpu-taps-mask-fallback"
    assert np.array_equal(out, _mask_reference(frame, 16, 10))
    monkeypatch.setattr(_resize, "cv2", None)
    covered = _step(12, 16, 0.0, 1.0)
    fallback, fallback_opts = _upscale(covered, (32, 24), {"quality": "fast", "dering_strength": 0.25})
    assert fallback_opts["_scale_path"] == "cpu-taps-mask-fallback"
    assert np.array_equal(fallback, _mask_reference(covered, 32, 24))


def test_fast_strength_hard_clamp_matches_balanced_and_zero_does_not() -> None:
    frame = _step(12, 16, 0.2, 0.8)
    balanced, balanced_opts = _upscale(frame, (32, 24), {"quality": "balanced"})
    hard, hard_opts = _upscale(frame, (32, 24), {"quality": "fast", "dering_strength": 1})
    loose, loose_opts = _upscale(frame, (32, 24), {"quality": "fast", "dering_strength": 0})
    assert balanced_opts["_scale_path"] == "cpu-sgemm-opencv"
    assert hard_opts["_scale_path"] == "cpu-sgemm-opencv-strength"
    assert loose_opts["_scale_path"] == "cpu-sgemm-opencv-strength"
    assert np.array_equal(hard, balanced)
    assert _visible_max_abs(loose, _mask_reference(frame, 32, 24)) > _LEVEL
    assert float(loose.min()) >= 0.0 and float(loose.max()) <= 1.0
    assert np.all(loose[..., 3] == np.float32(1.0))


def test_plan_cache_is_bit_identical_for_other_scalers() -> None:
    frame = _frame(12, 16, alpha=0.5, seed=4)
    untouched = frame.copy()
    opts = {"size": (32, 24)}
    get_algorithm("lanczos3-dering").upscale([frame, frame], 2.0, opts)
    assert opts["_scale_path"] == "cpu-sgemm-opencv"
    cached = get_algorithm("catmull-rom").upscale([frame], 2.0, opts)[0]
    assert opts["_scale_path"] == "cpu-sgemm-opencv"
    fresh = get_algorithm("catmull-rom").upscale([frame], 2.0, {"size": (32, 24)})[0]
    assert np.array_equal(cached, fresh)
    assert np.array_equal(frame, untouched)
    other = {"size": (32, 24)}
    get_algorithm("bicubic-sharper").upscale([frame], 2.0, other)
    assert "_scale_path" not in other


def test_adversarial_geometries_and_alpha_match_reference():
    """#1152: phase, border and alpha errors can hide on even opaque images."""
    for height, width, size in ((1, 1, (3, 2)), (3, 5, (9, 7)), (7, 9, (13, 11)), (9, 7, (3, 4))):
        yy, xx = np.mgrid[:height, :width]
        for pattern in ("impulse", "checker", "transparent"):
            frame = np.zeros((height, width, 4), dtype=np.float32)
            frame[..., 3] = 1
            if pattern == "impulse":
                frame[height // 2, width // 2, :3] = 1
            else:
                frame[..., :3] = ((yy + xx) % 2)[..., None]
            if pattern == "transparent":
                frame[..., 3] = np.linspace(0, 1, width, dtype=np.float32)[None, :]
            reference = _mask_reference(frame, *size)
            for quality in ("exact", "balanced", "fast"):
                actual, opts = _upscale(frame, size, {"quality": quality})
                repeated, _ = _upscale(frame, size, opts=opts)
                assert np.isfinite(actual).all()
                np.testing.assert_array_equal(actual, repeated)
                np.testing.assert_allclose(actual[..., 3], reference[..., 3], atol=_LEVEL, rtol=0)
                visible = reference[..., 3] > 1e-6
                np.testing.assert_allclose(actual[..., :3][visible], reference[..., :3][visible], atol=_LEVEL, rtol=0)
