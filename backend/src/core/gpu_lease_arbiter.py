"""In-process GPU admission beyond one exclusive job (#758).

The mutex is the same rule ``GpuLease`` already enforces: one in-process
holder at a time. This module adds the occupancy the mutex cannot see —
estimated demand vs device VRAM, conservative vs balanced profiles, and a
noted Comfy browser session whose queue is outside this process.

``empty_cache`` is an optional post-release hook that fires only on a
job-kind transition. It releases unused cached CUDA blocks; it does not
free live tensors and is not a general VRAM fix.
"""
from __future__ import annotations

import contextlib
import math
import os
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

PROFILE_BALANCED = "balanced"
PROFILE_CONSERVATIVE = "conservative"
PROFILES = (PROFILE_BALANCED, PROFILE_CONSERVATIVE)

# Conservative refuses when the estimate would occupy more than this
# fraction of device VRAM. Balanced ignores the estimate and keeps the
# exclusive in-process mutex.
CONSERVATIVE_VRAM_FRACTION = 0.90

KIND_TRAIN = "train"
KIND_GENERATE = "generate"
KIND_OTHER = "other"

_PROFILE_ENV = "IMAGE_TOOLKIT_GPU_PROFILE"


def parse_profile(value: str | None) -> str:
    raw = (value or PROFILE_BALANCED).strip().lower()
    if raw not in PROFILES:
        raise ValueError(
            f"GPU admission profile must be {PROFILE_BALANCED!r} or {PROFILE_CONSERVATIVE!r}."
        )
    return raw


def profile_from_env() -> str:
    raw = os.environ.get(_PROFILE_ENV)
    if not raw or not raw.strip():
        return PROFILE_BALANCED
    return parse_profile(raw)


def infer_kind(owner: str, kind: str | None = None) -> str:
    if kind:
        return kind
    lowered = owner.lower()
    if "train" in lowered:
        return KIND_TRAIN
    tokens = ("generate", "guided", "graph", "matrix", "promoted", "upscale")
    if any(token in lowered for token in tokens):
        return KIND_GENERATE
    return KIND_OTHER


def _finite_gb(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        gb = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(gb) or gb <= 0:
        return None
    return gb


def release_unused_cuda_blocks() -> None:
    """Release unused cached CUDA blocks. Not a general VRAM fix."""
    torch = sys.modules.get("torch")
    if torch is None:
        return
    cuda = getattr(torch, "cuda", None)
    if cuda is None:
        return
    is_available = getattr(cuda, "is_available", None)
    empty = getattr(cuda, "empty_cache", None)
    if callable(is_available) and callable(empty) and is_available():
        empty()


def cuda_device_total_gb() -> float | None:
    torch = sys.modules.get("torch")
    if torch is None:
        return None
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not callable(getattr(cuda, "is_available", None)):
        return None
    if not cuda.is_available():
        return None
    props = cuda.get_device_properties(0)
    return props.total_memory / (1024**3)


def cuda_peak_gb() -> float | None:
    torch = sys.modules.get("torch")
    if torch is None:
        return None
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not callable(getattr(cuda, "is_available", None)):
        return None
    if not cuda.is_available():
        return None
    peak = cuda.max_memory_allocated() / (1024**3)
    reset = getattr(cuda, "reset_peak_memory_stats", None)
    if callable(reset):
        reset()
    return peak


@dataclass(frozen=True)
class GpuLeaseSnapshot:
    owner: str | None
    profile: str
    estimated_gb: float | None
    measured_peak_gb: float | None
    device_total_gb: float | None
    external_browser: bool
    kind: str | None


class GpuLeaseArbiter:
    """Exclusive in-process GPU admission plus occupancy the mutex cannot see."""

    def __init__(
        self,
        *,
        profile: str = PROFILE_BALANCED,
        device_total_gb: float | None = None,
        empty_cache: Callable[[], None] | None = None,
        peak_reader: Callable[[], float | None] | None = None,
        device_probe: Callable[[], float | None] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._transition = threading.Lock()
        self._embedded_views: set[str] = set()
        self._owner: str | None = None
        self._kind: str | None = None
        self._last_kind: str | None = None
        self._estimated_gb: float | None = None
        self._measured_peak_gb: float | None = None
        self._external_browser = False
        self._last_refusal: str | None = None
        self._profile = parse_profile(profile)
        self._device_total_gb = _finite_gb(device_total_gb)
        self._empty_cache = empty_cache
        self._peak_reader = peak_reader
        self._device_probe = device_probe

    @property
    def machine_wide(self) -> bool:
        return False

    @property
    def owner(self) -> str | None:
        return self._owner

    @property
    def external_browser(self) -> bool:
        return self._external_browser

    @property
    def profile(self) -> str:
        return self._profile

    def set_profile(self, profile: str) -> None:
        self._profile = parse_profile(profile)

    def set_device_total_gb(self, total_gb: float | None) -> None:
        self._device_total_gb = _finite_gb(total_gb)

    def set_empty_cache(self, hook: Callable[[], None] | None) -> None:
        self._empty_cache = hook

    def note_external_browser(self, active: bool = True) -> None:
        self._external_browser = bool(active)

    def note_embedded_view(self, owner: str, active: bool) -> None:
        if active:
            self._embedded_views.add(owner)
        else:
            self._embedded_views.discard(owner)

    def scope_text(self) -> str:
        if self._external_browser or self._embedded_views:
            browser = " A Comfy browser session is open and can submit work this admission cannot see."
        else:
            browser = " Comfy browser jobs are outside this admission."
        return (
            "In-process jobs share one GPU admission "
            "(Comfy queues, training, and other model jobs)." + browser + f" Profile: {self._profile}."
        )

    def snapshot(self) -> GpuLeaseSnapshot:
        return GpuLeaseSnapshot(
            owner=self._owner,
            profile=self._profile,
            estimated_gb=self._estimated_gb,
            measured_peak_gb=self._measured_peak_gb,
            device_total_gb=self._device_total_gb,
            external_browser=self._external_browser or bool(self._embedded_views),
            kind=self._kind,
        )

    def refusal_text(self) -> str:
        if self._last_refusal:
            return self._last_refusal
        return f"GPU admission is held by {self._owner or 'another job'}."

    def try_acquire(self, owner: str, *, estimated_gb=None, kind=None) -> bool:
        if not self._transition.acquire(blocking=False):
            return False
        try:
            return self._try_acquire(owner, estimated_gb=estimated_gb, kind=kind)
        finally:
            self._transition.release()

    def _try_acquire(
        self,
        owner: str,
        *,
        estimated_gb: float | None = None,
        kind: str | None = None,
    ) -> bool:
        self._last_refusal = None
        estimate = _finite_gb(estimated_gb)
        if self._profile == PROFILE_CONSERVATIVE and (self._external_browser or self._embedded_views):
            self._last_refusal = (
                "GPU admission refused: a Comfy browser session is open (conservative profile)."
            )
            return False
        if self._owner is not None:
            self._last_refusal = f"GPU admission is held by {self._owner}."
            return False
        device = self._resolve_device_total() if self._profile == PROFILE_CONSERVATIVE and estimate is not None else None
        if self._profile == PROFILE_CONSERVATIVE and estimate is not None and device is not None:
            ceiling = CONSERVATIVE_VRAM_FRACTION * device
            if estimate > ceiling:
                self._last_refusal = (
                    f"GPU admission refused: estimated {estimate:.1f} GB exceeds "
                    f"{CONSERVATIVE_VRAM_FRACTION:.0%} of {device:.1f} GB device VRAM "
                    "(conservative profile)."
                )
                return False
        if not self._lock.acquire(blocking=False):
            self._last_refusal = f"GPU admission is held by {self._owner or 'another job'}."
            return False
        next_kind = infer_kind(owner, kind)
        if self._empty_cache is not None and self._last_kind is not None and self._last_kind != next_kind:
            with contextlib.suppress(Exception):
                self._empty_cache()
        self._owner = owner
        self._kind = next_kind
        self._estimated_gb = estimate
        return True

    def release(self, owner: str, *, measured_peak_gb: float | None = None) -> None:
        with self._transition:
            self._release(owner, measured_peak_gb=measured_peak_gb)

    def _release(self, owner: str, *, measured_peak_gb: float | None = None) -> None:
        if self._owner != owner:
            return
        peak = _finite_gb(measured_peak_gb)
        if peak is None and self._peak_reader is not None and owner not in {"matrix", "guided", "graph", "promoted", "guidance"}:
            try:
                peak = _finite_gb(self._peak_reader())
            except Exception:
                peak = None
        self._measured_peak_gb = peak
        self._last_kind = self._kind
        self._owner = None
        self._kind = None
        self._estimated_gb = None
        self._lock.release()

    def _resolve_device_total(self) -> float | None:
        if self._device_total_gb is not None:
            return self._device_total_gb
        if self._device_probe is None:
            return None
        try:
            probed = _finite_gb(self._device_probe())
        except Exception:
            return None
        if probed is not None:
            self._device_total_gb = probed
        return probed


__all__ = [
    "CONSERVATIVE_VRAM_FRACTION",
    "KIND_GENERATE",
    "KIND_OTHER",
    "KIND_TRAIN",
    "PROFILE_BALANCED",
    "PROFILE_CONSERVATIVE",
    "GpuLeaseArbiter",
    "GpuLeaseSnapshot",
    "cuda_device_total_gb",
    "cuda_peak_gb",
    "infer_kind",
    "parse_profile",
    "profile_from_env",
    "release_unused_cuda_blocks",
]
