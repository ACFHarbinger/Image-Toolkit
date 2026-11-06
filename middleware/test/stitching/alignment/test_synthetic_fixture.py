"""Unit tests for the layered synthetic pan/hold fixture (M0c — #1103).

Recovery uses the rendered frames only. No anime corpus, and no call into
the stitcher.
"""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest
from middleware.src.stitching.alignment.synthetic import (
    HeldCel,
    export_synthetic_sequence,
    generate_layered_pan_sequence,
)

# Integer camera alignment of one hold is exact. A new drawing is not.
_SAME_HOLD_MAD = 0.5


def _content_to_camera_step(frame_a: np.ndarray, frame_b: np.ndarray) -> tuple[float, float]:
    """Camera-window step implied by phase correlation.

    ``phaseCorrelate(a, b)`` reports how the pixels moved. The camera moved
    the other way through the plate, so the fixture's ``(dx, dy)`` is the
    negation of that shift.
    """
    gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    window = cv2.createHanningWindow((gray_a.shape[1], gray_a.shape[0]), cv2.CV_32F)
    (shift_x, shift_y), _response = cv2.phaseCorrelate(gray_a, gray_b, window)
    return -float(shift_x), -float(shift_y)


def _camera_step_mad(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    cam_dx: float,
    cam_dy: float,
) -> float:
    """Mean absolute difference after undoing an integer camera step."""
    dx = int(round(cam_dx))
    dy = int(round(cam_dy))
    height, width = frame_a.shape[:2]
    x0 = max(0, dx)
    y0 = max(0, dy)
    x1 = min(width, width + dx)
    y1 = min(height, height + dy)
    if x1 <= x0 or y1 <= y0:
        raise AssertionError(f"camera step {(dx, dy)} leaves no overlap")
    crop_a = frame_a[y0:y1, x0:x1]
    crop_b = frame_b[y0 - dy : y1 - dy, x0 - dx : x1 - dx]
    return float(np.mean(np.abs(crop_a.astype(np.int16) - crop_b.astype(np.int16))))


def _recover_velocity_and_hold_starts(
    frames: list[np.ndarray],
) -> tuple[float, float, list[int], int]:
    """Recover constant camera velocity and the first frame of each hold.

    A pair whose own phase-correlation step makes the frames match is a
    rigid pan of one drawing. The median of those steps is the velocity.
    Pairs that still differ after undoing that velocity are hold cuts.
    """
    rigid: list[tuple[float, float]] = []
    for index in range(len(frames) - 1):
        cam_dx, cam_dy = _content_to_camera_step(frames[index], frames[index + 1])
        mad = _camera_step_mad(frames[index], frames[index + 1], cam_dx, cam_dy)
        if mad <= _SAME_HOLD_MAD:
            rigid.append((cam_dx, cam_dy))
    if not rigid:
        raise AssertionError("no rigid pair recovered a camera step")

    velocity_x = float(np.median([step[0] for step in rigid]))
    velocity_y = float(np.median([step[1] for step in rigid]))
    starts = [0]
    for index in range(len(frames) - 1):
        mad = _camera_step_mad(frames[index], frames[index + 1], velocity_x, velocity_y)
        if mad > _SAME_HOLD_MAD:
            starts.append(index + 1)
    return velocity_x, velocity_y, starts, len(rigid)


def test_synthetic_pan_generation_dimensions_and_counts():
    num_frames = 6
    width, height = 320, 240
    seq = generate_layered_pan_sequence(
        num_frames=num_frames,
        frame_width=width,
        frame_height=height,
        pan_dx=0.0,
        pan_dy=35.0,
        seed=123,
    )

    assert len(seq.frames) == num_frames
    for frame in seq.frames:
        assert frame.shape == (height, width, 3)
        assert frame.dtype == np.uint8

    assert len(seq.camera_positions) == num_frames
    assert seq.ground_truth_displacements == [(0.0, 35.0)] * (num_frames - 1)
    assert len(seq.held_cels) == 2
    assert seq.metadata["pan_dx"] == 0.0
    assert seq.metadata["pan_dy"] == 35.0


def test_three_hold_ids_partition_the_sequence():
    seq = generate_layered_pan_sequence(num_frames=6, num_cels=3, pan_dx=10.0, pan_dy=-4.0, seed=99)
    assert [cel.hold_id for cel in seq.held_cels] == ["hold_alpha", "hold_beta", "hold_gamma"]
    covered: list[int] = []
    for cel in seq.held_cels:
        assert isinstance(cel, HeldCel)
        assert cel.rgba.shape[2] == 4
        assert cel.rgba.dtype == np.uint8
        covered.extend(cel.active_frames)
    assert covered == list(range(6))
    assert seq.ground_truth_displacements == [(10.0, -4.0)] * 5


def test_active_cel_is_the_only_change_from_the_plate():
    seq = generate_layered_pan_sequence(
        num_frames=6,
        frame_width=400,
        frame_height=300,
        pan_dx=16.0,
        pan_dy=-22.0,
        num_cels=3,
        seed=7,
    )
    height, width = seq.frames[0].shape[:2]
    for index, (cam_x, cam_y) in enumerate(seq.camera_positions):
        plate = seq.background_plate[cam_y : cam_y + height, cam_x : cam_x + width]
        diff = np.any(seq.frames[index] != plate, axis=2)
        active = [cel for cel in seq.held_cels if index in cel.active_frames]
        assert len(active) == 1
        cel = active[0]
        x0 = cel.world_pos[0] - cam_x
        y0 = cel.world_pos[1] - cam_y
        x1 = x0 + cel.rgba.shape[1]
        y1 = y0 + cel.rgba.shape[0]
        outside = diff.copy()
        outside[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)] = False
        assert diff.any()
        assert not outside.any()


@pytest.mark.parametrize(
    ("num_cels", "pan_dx", "pan_dy"),
    [
        (2, 0.0, 30.0),
        (2, -12.0, 8.0),
        (3, 16.0, -22.0),
    ],
)
def test_recovers_known_translation_and_hold_ids(num_cels: int, pan_dx: float, pan_dy: float):
    num_frames = 6
    seq = generate_layered_pan_sequence(
        num_frames=num_frames,
        frame_width=400,
        frame_height=300,
        pan_dx=pan_dx,
        pan_dy=pan_dy,
        num_cels=num_cels,
        seed=77,
    )
    assert seq.ground_truth_displacements == [(pan_dx, pan_dy)] * (num_frames - 1)

    velocity_x, velocity_y, starts, n_rigid = _recover_velocity_and_hold_starts(seq.frames)

    assert velocity_x == pytest.approx(pan_dx, abs=0.75)
    assert velocity_y == pytest.approx(pan_dy, abs=0.75)
    # One rigid pair per frame that stays on the same drawing.
    assert n_rigid == num_frames - num_cels
    assert starts == [cel.active_frames[0] for cel in seq.held_cels]

    expected_ids = ["hold_alpha", "hold_beta", "hold_gamma"][:num_cels]
    span_ends = starts[1:] + [num_frames]
    recovered_ids: list[str] = []
    for index, (cel, start, end) in enumerate(zip(seq.held_cels, starts, span_ends, strict=True)):
        assert cel.hold_id == expected_ids[index]
        assert cel.active_frames == tuple(range(start, end))
        recovered_ids.extend([cel.hold_id] * (end - start))
    assert recovered_ids == [
        cel.hold_id
        for frame in range(num_frames)
        for cel in seq.held_cels
        if frame in cel.active_frames
    ]


def test_export_and_manifest_serialization(tmp_path):
    seq = generate_layered_pan_sequence(num_frames=6, num_cels=3, pan_dx=8.0, pan_dy=5.0, seed=55)
    out_dir = tmp_path / "synthetic_pan_run"

    export_synthetic_sequence(seq, out_dir)

    assert (out_dir / "frame_000.png").exists()
    assert (out_dir / "frame_005.png").exists()
    assert (out_dir / "ground_truth_panorama.png").exists()
    assert (out_dir / "background_plate.png").exists()

    with open(out_dir / "manifest.json", encoding="utf-8") as handle:
        doc = json.load(handle)

    assert doc["version"] == "1.0.0"
    assert doc["frame_count"] == 6
    assert doc["ground_truth_displacements"] == [[8.0, 5.0]] * 5
    assert [cel["hold_id"] for cel in doc["held_cels"]] == [
        "hold_alpha",
        "hold_beta",
        "hold_gamma",
    ]
    assert doc["metadata"]["num_cels"] == 3


def test_same_seed_is_deterministic():
    kwargs = {"num_frames": 4, "pan_dx": 4.0, "pan_dy": 6.0, "num_cels": 2, "seed": 5}
    first = generate_layered_pan_sequence(**kwargs)
    second = generate_layered_pan_sequence(**kwargs)
    assert np.array_equal(first.background_plate, second.background_plate)
    assert np.array_equal(first.frames[0], second.frames[0])
    assert first.ground_truth_displacements == second.ground_truth_displacements


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_cels": 1},
        {"num_cels": 4},
        {"num_frames": 2, "num_cels": 3},
        {"num_frames": 1, "num_cels": 2},
    ],
)
def test_rejects_invalid_shape(kwargs):
    with pytest.raises(ValueError):
        generate_layered_pan_sequence(**kwargs)
