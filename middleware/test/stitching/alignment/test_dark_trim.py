"""Dark-border (letterbox) trim at frame load: per-frame vs sequence mode."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from middleware.src.stitching.alignment.canvas import _load_frames
from middleware.src.stitching.core.stateless import _dark_border_box, _trim_dark_border

H, W, BAR = 240, 320, 20


def _frame(seed: int, dark_bottom: int = 0, bars: bool = True) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = rng.integers(90, 220, (H, W, 3), dtype=np.uint8)
    if dark_bottom:  # dark scene content (e.g. a night floor), not a bar
        img[H - dark_bottom :] = rng.integers(25, 45, (dark_bottom, W, 3), dtype=np.uint8)
    if bars:  # broadcast letterbox: pure black, identical in every frame
        img[:BAR] = 0
        img[H - BAR :] = 0
    return img


def _write(tmp_path, frames):
    paths = []
    for k, f in enumerate(frames):
        p = str(tmp_path / f"f{k:02d}.png")
        cv2.imwrite(p, f)
        paths.append(p)
    return paths


def _legacy_trim(arr, pct=0.35):
    """Pre-refactor _trim_dark_border, verbatim logic."""
    gray = arr.mean(axis=2)
    row_m, col_m = gray.mean(axis=1), gray.mean(axis=0)
    thr_r = max((float(np.median(row_m)) or 1.0) * pct, 4.0)
    thr_c = max((float(np.median(col_m)) or 1.0) * pct, 4.0)
    top = next((y for y in range(len(row_m)) if row_m[y] >= thr_r), 0)
    bot = next((y for y in range(len(row_m) - 1, -1, -1) if row_m[y] >= thr_r), len(row_m) - 1) + 1
    left = next((x for x in range(len(col_m)) if col_m[x] >= thr_c), 0)
    right = next((x for x in range(len(col_m) - 1, -1, -1) if col_m[x] >= thr_c), len(col_m) - 1) + 1
    out = arr[top:bot, left:right]
    return out if out.size > 0 else arr


@pytest.mark.parametrize("seed,dark", [(0, 60), (1, 0), (2, 120)])
def test_trim_unchanged_from_legacy(seed, dark):
    img = _frame(seed, dark_bottom=dark)
    assert np.array_equal(_trim_dark_border(img), _legacy_trim(img))
    t, b, left, r = _dark_border_box(img)
    assert np.array_equal(img[t:b, left:r], _legacy_trim(img))


def test_frame_mode_cuts_dark_content(tmp_path, monkeypatch):
    monkeypatch.setenv("ASP_DARK_TRIM", "frame")
    frames = _load_frames(_write(tmp_path, [_frame(0, 60), _frame(1, 0)]))
    # Legacy: the dark-content frame loses its dark rows (60, of which the
    # bottom bar covers BAR) as well as the bars.
    assert frames[0].shape[0] == H - 2 * BAR - (60 - BAR)
    assert frames[1].shape[0] == H - 2 * BAR


def test_sequence_mode_trims_only_shared_bars(tmp_path, monkeypatch):
    monkeypatch.setenv("ASP_DARK_TRIM", "sequence")
    frames = _load_frames(_write(tmp_path, [_frame(0, 60), _frame(1, 0), _frame(2, 0)]))
    assert {f.shape for f in frames} == {(H - 2 * BAR, W, 3)}
    # The dark content rows survive.
    assert frames[0][-30:].mean() > 20


def test_sequence_mode_keeps_dark_content_in_every_frame(tmp_path, monkeypatch):
    # Dark (but not black) at the bottom of every frame: content, not a bar.
    monkeypatch.setenv("ASP_DARK_TRIM", "sequence")
    frames = _load_frames(_write(tmp_path, [_frame(k, 60, bars=False) for k in range(3)]))
    assert {f.shape for f in frames} == {(H, W, 3)}


def test_off_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("ASP_DARK_TRIM", "off")
    frames = _load_frames(_write(tmp_path, [_frame(0, 60)]))
    assert frames[0].shape == (H, W, 3)


@pytest.mark.parametrize("mode", ["frame", "sequence"])
def test_mixed_sizes_fall_back_per_frame(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("ASP_DARK_TRIM", mode)
    small = cv2.resize(_frame(1), (W // 2, H // 2), interpolation=cv2.INTER_NEAREST)
    frames = _load_frames(_write(tmp_path, [_frame(0), small]))
    assert len(frames) == 2 and all(f.size for f in frames)
