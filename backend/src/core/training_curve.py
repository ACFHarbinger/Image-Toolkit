"""Reader-side loss curve and checkpoint scrubbing (#742).

The JSONL sink stores raw metrics. Smoothing and min/max buckets exist
only so a long run can be drawn without dropping spikes.
"""
from __future__ import annotations

import math
from pathlib import Path


def loss_series(events) -> list[tuple[int, float]]:
    """Finite ``(step, loss)`` points, ordered by step."""
    points: list[tuple[int, float]] = []
    for event in events or ():
        if not isinstance(event, dict):
            continue
        step = _as_int(event.get("step"))
        if step is None or "loss" not in event:
            continue
        try:
            loss = float(event["loss"])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(loss):
            continue
        points.append((step, loss))
    points.sort(key=lambda item: item[0])
    return points


def smooth_series(points: list[tuple[int, float]], window: int = 16) -> list[tuple[int, float]]:
    """Trailing mean. The raw series is unchanged."""
    width = max(1, int(window))
    smoothed: list[tuple[int, float]] = []
    bucket: list[float] = []
    total = 0.0
    for step, loss in points:
        bucket.append(loss)
        total += loss
        if len(bucket) > width:
            total -= bucket.pop(0)
        smoothed.append((step, total / len(bucket)))
    return smoothed


def bucket_minmax(points: list[tuple[int, float]], buckets: int) -> list[tuple[int, int, float, float]]:
    """``(first_step, last_step, min_loss, max_loss)`` per display bucket.

    Every raw point lands in a bucket, so a one-step spike stays visible.
    """
    if not points:
        return []
    count = max(1, min(int(buckets), len(points)))
    width = len(points) / count
    grouped: list[tuple[int, int, float, float]] = []
    for index in range(count):
        start = int(index * width)
        end = int((index + 1) * width)
        chunk = points[start:end] or [points[min(start, len(points) - 1)]]
        losses = [loss for _step, loss in chunk]
        grouped.append((chunk[0][0], chunk[-1][0], min(losses), max(losses)))
    return grouped


def step_at_ratio(points: list[tuple[int, float]], ratio: float) -> int | None:
    if not points:
        return None
    clamped = min(1.0, max(0.0, float(ratio)))
    return round(points[0][0] + clamped * (points[-1][0] - points[0][0]))


def checkpoint_index(steps: list[int], cursor: int) -> int | None:
    """Latest checkpoint whose step is at or before *cursor*."""
    chosen: int | None = None
    for index, step in enumerate(steps):
        if step <= cursor:
            chosen = index
        else:
            break
    return chosen


def latest_epoch(events) -> int | None:
    seen: int | None = None
    for event in events or ():
        if not isinstance(event, dict):
            continue
        epoch = _as_int(event.get("epoch"))
        if epoch is None:
            continue
        seen = epoch if seen is None else max(seen, epoch)
    return seen


def sample_file(run_dir: Path, relative: str) -> Path | None:
    """Resolve a sample path recorded in an event. Rejects paths outside the run."""
    if not isinstance(relative, str) or not relative or relative.startswith(("/", "\\")):
        return None
    parts = Path(relative).parts
    if ".." in parts:
        return None
    root = Path(run_dir).resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        return None
    return path


def _as_int(value) -> int | None:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value, 10)
        except ValueError:
            return None
    return None
