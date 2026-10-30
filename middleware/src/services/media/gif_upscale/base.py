"""Shared types for GIF upscale and downscale backends."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

# Frames are HxWx4 float32 in 0..1, straight (not premultiplied) alpha.
Frames = list[np.ndarray]
UpscaleFn = Callable[[Frames, float, dict], Frames]


class AlgorithmError(Exception):
    """The chosen backend refused the job. Callers surface this text; they do not swap algorithms."""


@dataclass(frozen=True)
class AlgorithmSpec:
    """One registered backend. ``supports_scale`` empty means any positive scale."""

    id: str
    family: str
    content: str
    kind: str
    supports_scale: frozenset[float]
    supports_downscale: bool
    needs_gpu: bool
    vram_mb_estimate: int
    license: str
    weights_sha256: str | None
    available: Callable[[], tuple[bool, str]]
    containers: tuple[str, ...] = ("gif", "still")


@dataclass(frozen=True)
class RegisteredAlgorithm:
    spec: AlgorithmSpec
    upscale: UpscaleFn
