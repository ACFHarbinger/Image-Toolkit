"""In-process GPU admission beyond one exclusive job (#758, #1154).

Without a device table the rule is the one ``GpuLease`` already enforces:
one in-process holder. A table gives each device its own holder. Estimated
demand, conservative vs balanced profiles, and a noted Comfy browser
session still apply. The table is injected. ``cuda_device_table`` can build
one, but B3 (#1156) is what passes it into the process-wide lease.
Enumerating at ``GpuLease()`` startup would change admission on multi-GPU
hosts before that scheduler exists.

``empty_cache`` fires only on a job-kind transition, and only when no
device is still held. It releases unused cached CUDA blocks; it does not
free live tensors and is not a general VRAM fix.

GIF resample calls ``ensure_device_table`` with rows from
``cuda_device_table`` before it acquires. That is the first attach on the
process lease. A legacy holder blocks the attach so ``release`` stays on
the legacy path.
"""
from __future__ import annotations

import contextlib
import math
import os
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
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

# Comfy HTTP jobs run in another process. This process's torch peak is
# not their occupancy and must not be recorded as if it were.
COMFY_OWNERS = frozenset({"matrix", "guided", "graph", "promoted", "guidance"})

_PROFILE_ENV = "IMAGE_TOOLKIT_GPU_PROFILE"
_DEVICES_ENV = "IMAGE_TOOLKIT_GPU_DEVICES"


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


def _row_gb(value: object, *, positive: bool) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    gb = float(value)
    if not math.isfinite(gb):
        return None
    if positive and gb <= 0:
        return None
    if not positive and gb < 0:
        return None
    return gb


@dataclass
class _DeviceSlot:
    index: int
    total_gb: float
    free_gb: float
    owner: str | None = None
    kind: str | None = None
    estimated_gb: float | None = None
    estimate_scale: float = 1.0
    granted: int = 0


def _device_rows(devices: Sequence[Mapping[str, object]]) -> tuple[_DeviceSlot, ...]:
    rows: list[_DeviceSlot] = []
    seen: set[int] = set()
    for raw in devices:
        if not isinstance(raw, Mapping):
            raise ValueError("GPU device rows must be mappings with index, total_gb, and free_gb.")
        index = raw.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("GPU device row needs an integer index.")
        total = _row_gb(raw.get("total_gb"), positive=True)
        free = _row_gb(raw.get("free_gb"), positive=False)
        if total is None or free is None:
            raise ValueError(f"GPU device {index} needs a positive total_gb and a non-negative free_gb.")
        if index in seen:
            raise ValueError(f"GPU device {index} is listed more than once.")
        seen.add(index)
        rows.append(_DeviceSlot(index=index, total_gb=total, free_gb=free))
    rows.sort(key=lambda slot: slot.index)
    return tuple(rows)


def _allow_tuple(values: Sequence[int]) -> tuple[int, ...]:
    indexes: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("allow_devices must be integer device indexes.")
        if value not in indexes:
            indexes.append(value)
    return tuple(indexes)


def _parse_allow_env(raw: str) -> tuple[int, ...] | str:
    text = raw.strip()
    if not text:
        return f"GPU admission refused: {_DEVICES_ENV} is empty."
    indexes: list[int] = []
    for part in (piece.strip() for piece in text.split(",")):
        if not part.isdigit():
            return f"GPU admission refused: {_DEVICES_ENV} must be a comma-separated list of device indexes."
        index = int(part)
        if index not in indexes:
            indexes.append(index)
    return tuple(indexes)


def _refusal_for_blocked(blocked: Sequence[tuple[_DeviceSlot, str]]) -> str:
    open_blocks = [(slot, reason) for slot, reason in blocked if slot.owner is None]
    if open_blocks:
        open_blocks.sort(key=lambda item: (-item[0].free_gb, item[0].index))
        return open_blocks[0][1]
    owners: list[str] = []
    for slot, _reason in blocked:
        if slot.owner and slot.owner not in owners:
            owners.append(slot.owner)
    if len(owners) == 1:
        return f"GPU admission is held by {owners[0]}."
    if len(owners) == 2:
        return f"GPU admission is held by {owners[0]} and {owners[1]}."
    if owners:
        listed = ", ".join(owners[:-1]) + f", and {owners[-1]}"
        return f"GPU admission is held by {listed}."
    return "GPU admission refused: no device can take this job."


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


def cuda_device_total_gb(device: int = 0) -> float | None:
    torch = sys.modules.get("torch")
    if torch is None:
        return None
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not callable(getattr(cuda, "is_available", None)):
        return None
    if not cuda.is_available():
        return None
    props = cuda.get_device_properties(device)
    return props.total_memory / (1024**3)


def cuda_device_count() -> int:
    """CUDA devices visible to an already-imported torch, else zero."""
    torch = sys.modules.get("torch")
    if torch is None:
        return 0
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not callable(getattr(cuda, "is_available", None)):
        return 0
    count = getattr(cuda, "device_count", None)
    if not callable(count):
        return 0
    try:
        if not cuda.is_available():
            return 0
        return max(0, int(count()))
    except Exception:
        return 0


def cuda_device_table() -> tuple[dict[str, float | int], ...]:
    """Rows of index, total_gb, and free_gb from mem_get_info and device props.

    Empty when torch is not already imported or CUDA is unavailable. B3
    (#1156) passes the result into the process-wide GpuLease. Startup and
    snapshot must not call this: enumerating here would change admission on
    multi-GPU hosts before that scheduler exists.
    """
    torch = sys.modules.get("torch")
    if torch is None:
        return ()
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not callable(getattr(cuda, "is_available", None)):
        return ()
    props_of = getattr(cuda, "get_device_properties", None)
    mem_info = getattr(cuda, "mem_get_info", None)
    if not callable(props_of) or not callable(mem_info):
        return ()
    try:
        if not cuda.is_available():
            return ()
        count = cuda_device_count()
    except Exception:
        return ()
    rows: list[dict[str, float | int]] = []
    for index in range(count):
        try:
            props = props_of(index)
            free_bytes, _total_bytes = mem_info(index)
            total_gb = float(props.total_memory) / (1024**3)
            free_gb = float(free_bytes) / (1024**3)
        except Exception:
            return ()
        rows.append({"index": index, "total_gb": total_gb, "free_gb": free_gb})
    return tuple(rows)


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
    held_devices: tuple[tuple[int, str], ...] = ()


class GpuLeaseArbiter:
    """Exclusive in-process GPU admission plus occupancy the mutex cannot see.

    ``devices=None`` is the legacy one-owner mutex. A non-empty table admits
    one owner per device and picks the allow-listed row with the most free
    VRAM. ``free_gb`` is that configured value; a hold does not subtract a
    running estimate.
    """

    def __init__(
        self,
        *,
        profile: str = PROFILE_BALANCED,
        device_total_gb: float | None = None,
        empty_cache: Callable[[], None] | None = None,
        peak_reader: Callable[[], float | None] | None = None,
        device_probe: Callable[[], float | None] | None = None,
        devices: tuple[dict, ...] | None = None,
        allow_devices: tuple[int, ...] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._transition = threading.Lock()
        # Blocks overlapping legacy acquires. Per-device admission uses a
        # blocking lock instead, so a second free device is not rejected
        # just because the first is already held.
        self._admission = threading.Lock()
        self._embedded_views: set[str] = set()
        self._owner: str | None = None
        self._kind: str | None = None
        self._last_kind: str | None = None
        self._estimated_gb: float | None = None
        self._estimate_scale = 1.0
        self._measured_peak_gb: float | None = None
        self._external_browser = False
        self._last_refusal: str | None = None
        self._profile = parse_profile(profile)
        self._device_total_gb = _finite_gb(device_total_gb)
        self._empty_cache = empty_cache
        self._peak_reader = peak_reader
        self._device_probe = device_probe
        self._grant_clock = 0
        # None stays on the legacy path. B3 (#1156) supplies the table;
        # this object does not enumerate CUDA.
        self._allow_devices = None if allow_devices is None else _allow_tuple(allow_devices)
        self._slots: tuple[_DeviceSlot, ...] | None = None if devices is None else _device_rows(devices)

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

    def ensure_device_table(self, devices: Sequence[Mapping[str, object]]) -> bool:
        """Install or refresh a per-device table. The caller supplies the rows.

        Returns False when a legacy holder is on this lease. The table stays
        off in that case so ``release`` keeps using the legacy path. Free and
        total VRAM of unheld rows are refreshed from ``devices``. Held rows
        are left alone. This method does not read CUDA.
        """
        rows = _device_rows(tuple(devices))
        with self._transition:
            if self._slots is None:
                if self._owner is not None or self._lock.locked():
                    return False
                self._slots = rows
                return True
        with self._admission:
            self._refresh_free(rows)
        return True

    def device_indexes(self) -> tuple[int, ...] | None:
        """Configured device indexes, or None when this lease has no table."""
        if self._slots is None:
            return None
        return tuple(slot.index for slot in self._slots)

    def allow_indexes(self) -> tuple[int, ...] | str | None:
        """Allow-list for this lease.

        None when there is no table and no env allow-list. A string is a
        refusal (the env value is not a device list).
        """
        if self._slots is None and self._allow_devices is None and os.environ.get(_DEVICES_ENV) is None:
            return None
        if self._slots is None and self._allow_devices is not None:
            return self._allow_devices
        if self._slots is None:
            raw = os.environ.get(_DEVICES_ENV)
            assert raw is not None
            return _parse_allow_env(raw)
        return self._allow_indexes()

    def note_external_browser(self, active: bool = True) -> None:
        self._external_browser = bool(active)

    def note_embedded_view(self, owner: str, active: bool) -> None:
        if active:
            self._embedded_views.add(owner)
        else:
            self._embedded_views.discard(owner)

    def _unknown_comfy_occupancy(self) -> bool:
        return self._external_browser or bool(self._embedded_views)

    def scope_text(self) -> str:
        if self._unknown_comfy_occupancy():
            browser = " A Comfy browser session is open and can submit work this admission cannot see."
        else:
            browser = " Comfy browser jobs are outside this admission."
        return (
            "In-process jobs share one GPU admission "
            "(Comfy queues, training, and other model jobs)." + browser + f" Profile: {self._profile}."
        )

    def free_gb(self, device: int) -> float | None:
        """Configured free VRAM for *device*. A hold does not change it."""
        slot = self._slot(device)
        if slot is None:
            return None
        return slot.free_gb

    def device_for(self, owner: str) -> int | None:
        """The one device *owner* holds, or None when they hold several or none.

        The legacy mutex has no device index, so this is None there too.
        """
        held = self.devices_for(owner)
        if len(held) == 1:
            return held[0]
        return None

    def devices_for(self, owner: str) -> tuple[int, ...]:
        if self._slots is None:
            return ()
        return tuple(slot.index for slot in self._slots if slot.owner == owner)

    def snapshot(self) -> GpuLeaseSnapshot:
        # Do not probe CUDA from a GUI snapshot path.
        return GpuLeaseSnapshot(
            owner=self._owner,
            profile=self._profile,
            estimated_gb=self._estimated_gb,
            measured_peak_gb=self._measured_peak_gb,
            device_total_gb=self._device_total_gb,
            external_browser=self._unknown_comfy_occupancy(),
            kind=self._kind,
            held_devices=self._held_pairs(),
        )

    def refusal_text(self) -> str:
        if self._last_refusal:
            return self._last_refusal
        return f"GPU admission is held by {self._owner or 'another job'}."

    def try_acquire(
        self,
        owner: str,
        *,
        estimated_gb: float | None = None,
        kind: str | None = None,
        device: int | None = None,
        allow_devices: Sequence[int] | None = None,
    ) -> bool:
        if self._slots is not None:
            with self._admission:
                return self._try_acquire_devices(
                    owner,
                    estimated_gb=estimated_gb,
                    kind=kind,
                    device=device,
                    allow_devices=allow_devices,
                )
        if device is not None:
            if self._owner is not None:
                self._last_refusal = f"GPU admission is held by {self._owner}."
                return False
            self._last_refusal = "GPU admission refused: no per-device table is configured."
            return False
        # Non-blocking so an overlapping acquire fails closed. The
        # duplicate-release test depends on this lock staying blocking
        # only for release.
        if not self._transition.acquire(blocking=False):
            self._last_refusal = f"GPU admission is held by {self._owner or 'another job'}."
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
        if self._profile == PROFILE_CONSERVATIVE and self._unknown_comfy_occupancy():
            self._last_refusal = (
                "GPU admission refused: a Comfy browser session is open (conservative profile)."
            )
            return False
        if self._owner is not None:
            self._last_refusal = f"GPU admission is held by {self._owner}."
            return False
        device = None
        if self._profile == PROFILE_CONSERVATIVE and estimate is not None:
            device = self._resolve_device_total()
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
        from middleware.src.core.gpu_vram_calibration import owner_scale

        self._estimate_scale = owner_scale(owner)
        return True

    def release(
        self,
        owner: str,
        *,
        measured_peak_gb: float | None = None,
        device: int | None = None,
    ) -> None:
        if self._slots is not None:
            with self._admission:
                self._release_devices(owner, measured_peak_gb=measured_peak_gb, device=device)
            return
        with self._transition:
            self._release(owner, measured_peak_gb=measured_peak_gb)

    def _release(self, owner: str, *, measured_peak_gb: float | None = None) -> None:
        if self._owner != owner:
            return
        peak = _finite_gb(measured_peak_gb)
        if peak is None and self._peak_reader is not None and owner not in COMFY_OWNERS:
            try:
                peak = _finite_gb(self._peak_reader())
            except Exception:
                peak = None
        estimate = self._estimated_gb
        self._measured_peak_gb = peak
        if peak is not None and estimate is not None and owner not in COMFY_OWNERS:
            from middleware.src.core.gpu_vram_calibration import record_peak

            # Admission already applied this scale; compare against the raw prior.
            record_peak(owner, peak, estimate / self._estimate_scale)
        self._last_kind = self._kind
        self._owner = None
        self._kind = None
        self._estimated_gb = None
        self._lock.release()

    def _refresh_free(self, rows: tuple[_DeviceSlot, ...]) -> None:
        assert self._slots is not None
        incoming = {slot.index: slot for slot in rows}
        for slot in self._slots:
            fresh = incoming.get(slot.index)
            if fresh is None or slot.owner is not None:
                continue
            slot.total_gb = fresh.total_gb
            slot.free_gb = fresh.free_gb

    def _restrict_allow(self, override: Sequence[int] | None) -> tuple[int, ...] | str:
        base = self._allow_indexes()
        if isinstance(base, str) or override is None:
            return base
        try:
            wanted = _allow_tuple(override)
        except ValueError as exc:
            return str(exc)
        allowed = set(base)
        return tuple(index for index in wanted if index in allowed)

    def _slot(self, device: int) -> _DeviceSlot | None:
        if self._slots is None:
            return None
        for slot in self._slots:
            if slot.index == device:
                return slot
        return None

    def _held_pairs(self) -> tuple[tuple[int, str], ...]:
        if self._slots is None:
            return ()
        return tuple((slot.index, slot.owner) for slot in self._slots if slot.owner is not None)

    def _allow_indexes(self) -> tuple[int, ...] | str:
        if self._allow_devices is not None:
            return self._allow_devices
        raw = os.environ.get(_DEVICES_ENV)
        if raw is None:
            assert self._slots is not None
            return tuple(slot.index for slot in self._slots)
        return _parse_allow_env(raw)

    def _sync_holder_view(self) -> None:
        assert self._slots is not None
        holders: list[str] = []
        for slot in self._slots:
            if slot.owner is not None and slot.owner not in holders:
                holders.append(slot.owner)
        if len(holders) != 1:
            self._owner = None
            self._kind = None
            self._estimated_gb = None
            return
        owned = [slot for slot in self._slots if slot.owner == holders[0]]
        latest = max(owned, key=lambda slot: slot.granted)
        self._owner = holders[0]
        self._kind = latest.kind
        self._estimated_gb = latest.estimated_gb
        self._estimate_scale = latest.estimate_scale

    def _device_refusal(self, slot: _DeviceSlot, estimate: float | None) -> str | None:
        if slot.owner is not None:
            return f"GPU admission is held by {slot.owner}."
        if slot.free_gb <= 0:
            return f"GPU admission refused: device {slot.index} has no free VRAM."
        if self._profile != PROFILE_CONSERVATIVE or estimate is None:
            return None
        ceiling = CONSERVATIVE_VRAM_FRACTION * slot.total_gb
        if estimate > ceiling:
            return (
                f"GPU admission refused: estimated {estimate:.1f} GB exceeds "
                f"{CONSERVATIVE_VRAM_FRACTION:.0%} of {slot.total_gb:.1f} GB on device "
                f"{slot.index} (conservative profile)."
            )
        if estimate > slot.free_gb:
            return (
                f"GPU admission refused: estimated {estimate:.1f} GB exceeds "
                f"{slot.free_gb:.1f} GB free on device {slot.index}."
            )
        return None

    def _grant_device(
        self,
        slot: _DeviceSlot,
        owner: str,
        estimate: float | None,
        kind: str | None,
    ) -> None:
        assert self._slots is not None
        next_kind = infer_kind(owner, kind)
        # empty_cache is process-wide. Skip it while another device is in use.
        if (
            self._empty_cache is not None
            and not any(row.owner is not None for row in self._slots)
            and self._last_kind is not None
            and self._last_kind != next_kind
        ):
            with contextlib.suppress(Exception):
                self._empty_cache()
        slot.owner = owner
        slot.kind = next_kind
        slot.estimated_gb = estimate
        from middleware.src.core.gpu_vram_calibration import owner_scale

        slot.estimate_scale = owner_scale(owner)
        self._grant_clock += 1
        slot.granted = self._grant_clock
        self._sync_holder_view()

    def _try_acquire_devices(
        self,
        owner: str,
        *,
        estimated_gb: float | None,
        kind: str | None,
        device: int | None,
        allow_devices: Sequence[int] | None = None,
    ) -> bool:
        self._last_refusal = None
        estimate = _finite_gb(estimated_gb)
        if self._profile == PROFILE_CONSERVATIVE and self._unknown_comfy_occupancy():
            self._last_refusal = (
                "GPU admission refused: a Comfy browser session is open (conservative profile)."
            )
            return False
        if not self._slots:
            self._last_refusal = "GPU admission refused: no GPU devices are configured."
            return False
        allow = self._restrict_allow(allow_devices)
        if device is not None:
            return self._acquire_targeted(owner, estimate, kind, device, allow)
        return self._acquire_freest(owner, estimate, kind, allow)

    def _acquire_targeted(
        self,
        owner: str,
        estimate: float | None,
        kind: str | None,
        device: object,
        allow: tuple[int, ...] | str,
    ) -> bool:
        if isinstance(allow, str):
            self._last_refusal = allow
            return False
        if isinstance(device, bool) or not isinstance(device, int):
            self._last_refusal = "GPU admission refused: device must be an integer index."
            return False
        slot = self._slot(device)
        if slot is None:
            self._last_refusal = f"GPU admission refused: device {device} is not configured."
            return False
        if device not in allow:
            self._last_refusal = f"GPU admission refused: device {device} is not allow-listed."
            return False
        reason = self._device_refusal(slot, estimate)
        if reason is not None:
            self._last_refusal = reason
            return False
        self._grant_device(slot, owner, estimate, kind)
        return True

    def _acquire_freest(
        self,
        owner: str,
        estimate: float | None,
        kind: str | None,
        allow: tuple[int, ...] | str,
    ) -> bool:
        assert self._slots is not None
        if isinstance(allow, str):
            self._last_refusal = allow
            return False
        allowed = set(allow)
        candidates = [slot for slot in self._slots if slot.index in allowed]
        if not candidates:
            self._last_refusal = "GPU admission refused: no allow-listed device is present."
            return False
        fitting: list[_DeviceSlot] = []
        blocked: list[tuple[_DeviceSlot, str]] = []
        for slot in candidates:
            reason = self._device_refusal(slot, estimate)
            if reason is None:
                fitting.append(slot)
            else:
                blocked.append((slot, reason))
        if not fitting:
            self._last_refusal = _refusal_for_blocked(blocked)
            return False
        fitting.sort(key=lambda slot: (-slot.free_gb, slot.index))
        self._grant_device(fitting[0], owner, estimate, kind)
        return True

    def _release_devices(
        self,
        owner: str,
        *,
        measured_peak_gb: float | None,
        device: int | None,
    ) -> None:
        assert self._slots is not None
        if device is not None and (isinstance(device, bool) or not isinstance(device, int)):
            return
        targets = [
            slot
            for slot in self._slots
            if slot.owner == owner and (device is None or slot.index == device)
        ]
        if not targets:
            return
        released_kind = max(targets, key=lambda slot: slot.granted).kind
        self._note_peak(owner, targets, measured_peak_gb)
        for slot in targets:
            slot.owner = None
            slot.kind = None
            slot.estimated_gb = None
            slot.estimate_scale = 1.0
            slot.granted = 0
        if not any(slot.owner is not None for slot in self._slots):
            self._last_kind = released_kind
        self._sync_holder_view()

    def _note_peak(
        self,
        owner: str,
        slots: Sequence[_DeviceSlot],
        measured_peak_gb: float | None,
    ) -> None:
        peak = _finite_gb(measured_peak_gb)
        if peak is None and self._peak_reader is not None and owner not in COMFY_OWNERS:
            try:
                peak = _finite_gb(self._peak_reader())
            except Exception:
                peak = None
        priors = [
            slot.estimated_gb / slot.estimate_scale
            for slot in slots
            if slot.estimated_gb is not None and slot.estimate_scale > 0
        ]
        self._measured_peak_gb = peak
        if peak is None or not priors or owner in COMFY_OWNERS:
            return
        from middleware.src.core.gpu_vram_calibration import record_peak

        record_peak(owner, peak, sum(priors))

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
    "COMFY_OWNERS",
    "CONSERVATIVE_VRAM_FRACTION",
    "KIND_GENERATE",
    "KIND_OTHER",
    "KIND_TRAIN",
    "PROFILE_BALANCED",
    "PROFILE_CONSERVATIVE",
    "GpuLeaseArbiter",
    "GpuLeaseSnapshot",
    "cuda_device_count",
    "cuda_device_table",
    "cuda_device_total_gb",
    "cuda_peak_gb",
    "infer_kind",
    "parse_profile",
    "profile_from_env",
    "release_unused_cuda_blocks",
]
