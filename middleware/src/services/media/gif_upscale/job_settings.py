"""GIF upscale mode and advanced switches as settings (C1, #1159).

UI-agnostic: nothing here imports Qt. A request key always wins over a
setting, so a caller that passes ``workers`` or ``quality`` explicitly is
never overridden. ``with_job_settings`` fills only what the request left out.

Keys (all DEVICE scope, extension settings like ``gif_upscale.weights_policy``):

``gif_upscale.mode``              exact | balanced (default) | fast. Becomes ``quality``.
``gif_upscale.workers``           processes for decode and encode, default 1 (D10).
``gif_upscale.vram_cap_gb``       cap per job in GB; 0 means what is free at start.
``gif_upscale.devices``           CUDA device allow-list; empty means every device.
``gif_upscale.palette_mode``      mediancut (default) | libimagequant.
``gif_upscale.dering_strength``   0.0 to 1.0, default 1.0.
``gif_upscale.no_gpu_threshold_s`` estimate above which the no-GPU window opens, default 120 (D17).
``gif_upscale.no_gpu_prompt``     show that window at all; False is "do not ask again" (D18).
"""

from __future__ import annotations

import math
from typing import Any

from middleware.src.settings.keys import SettingDefinition, register_definitions
from middleware.src.settings.scopes import SettingScope

MODES = ("exact", "balanced", "fast")
PALETTE_MODES = ("mediancut", "libimagequant")

MODE_KEY = "gif_upscale.mode"
WORKERS_KEY = "gif_upscale.workers"
VRAM_CAP_KEY = "gif_upscale.vram_cap_gb"
DEVICES_KEY = "gif_upscale.devices"
PALETTE_MODE_KEY = "gif_upscale.palette_mode"
DERING_STRENGTH_KEY = "gif_upscale.dering_strength"
NO_GPU_THRESHOLD_KEY = "gif_upscale.no_gpu_threshold_s"
NO_GPU_PROMPT_KEY = "gif_upscale.no_gpu_prompt"

DEFAULT_NO_GPU_THRESHOLD_S = 120


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _choice(options: tuple[str, ...]):
    return lambda value: str(value).strip().lower() in options


def _int_at_least(minimum: int):
    def check(value: Any) -> bool:
        number = _number(value)
        return number is not None and number == int(number) and number >= minimum

    return check


def _float_between(low: float, high: float):
    def check(value: Any) -> bool:
        number = _number(value)
        return number is not None and low <= number <= high

    return check


def _device_list(value: Any) -> bool:
    if value in (None, ""):
        return True
    items = value if isinstance(value, (list, tuple)) else [value]
    try:
        return all(int(item) >= 0 for item in items)
    except (TypeError, ValueError):
        return False


DEFINITIONS = [
    SettingDefinition(
        MODE_KEY, SettingScope.DEVICE, "balanced", str, "GIF upscale mode: exact, balanced or fast.", _choice(MODES)
    ),
    SettingDefinition(
        WORKERS_KEY, SettingScope.DEVICE, 1, int, "Processes used to decode and encode one GIF.", _int_at_least(1)
    ),
    SettingDefinition(
        VRAM_CAP_KEY,
        SettingScope.DEVICE,
        0.0,
        float,
        "VRAM cap per job in GB; 0 uses what is free at start.",
        _float_between(0.0, 1024.0),
    ),
    SettingDefinition(
        DEVICES_KEY,
        SettingScope.DEVICE,
        [],
        list,
        "CUDA device indexes GIF jobs may use; empty allows all.",
        _device_list,
    ),
    SettingDefinition(
        PALETTE_MODE_KEY,
        SettingScope.DEVICE,
        "mediancut",
        str,
        "Shared palette method: mediancut or libimagequant.",
        _choice(PALETTE_MODES),
    ),
    SettingDefinition(
        DERING_STRENGTH_KEY,
        SettingScope.DEVICE,
        1.0,
        float,
        "Dering strength from 0.0 to 1.0.",
        _float_between(0.0, 1.0),
    ),
    SettingDefinition(
        NO_GPU_THRESHOLD_KEY,
        SettingScope.DEVICE,
        DEFAULT_NO_GPU_THRESHOLD_S,
        int,
        "Estimated seconds above which the no-GPU window opens.",
        _int_at_least(1),
    ),
    SettingDefinition(
        NO_GPU_PROMPT_KEY, SettingScope.DEVICE, True, bool, "Show the no-GPU window; false means do not ask again."
    ),
]

register_definitions(DEFINITIONS)
_BY_KEY = {definition.key: definition for definition in DEFINITIONS}


def _read(service: Any, key: str, default: Any) -> Any:
    try:
        return service.get(key, default)
    except Exception:
        return default


def _valid(definition: SettingDefinition, value: Any) -> bool:
    return definition.validator is None or bool(definition.validator(value))


def read_setting(definition: SettingDefinition, service: Any) -> Any:
    """The stored value, or the default when it is missing or fails validation."""
    raw = _read(service, definition.key, definition.default)
    if raw is None or not _valid(definition, raw):
        return definition.default
    return definition.cast(raw)


def _service(service: Any | None) -> Any:
    if service is not None:
        return service
    from middleware.src.settings.service import SettingsService

    return SettingsService()


def no_gpu_prompt_enabled(service: Any | None = None) -> bool:
    return bool(read_setting(_BY_KEY[NO_GPU_PROMPT_KEY], _service(service)))


def no_gpu_threshold_s(service: Any | None = None) -> int:
    return int(read_setting(_BY_KEY[NO_GPU_THRESHOLD_KEY], _service(service)))


def with_job_settings(params: dict[str, Any], service: Any | None = None) -> dict[str, Any]:
    """A copy of ``params`` with the settings filled in for keys the request left out.

    ``mode`` fills ``quality``; ``devices`` fills ``allow_devices`` when it is not empty;
    ``vram_cap_gb`` is filled only above zero. Present request keys are never replaced.
    """
    store = _service(service)
    out = dict(params)
    if out.get("quality") in (None, ""):
        out["quality"] = str(read_setting(_BY_KEY[MODE_KEY], store)).strip().lower()
    if out.get("workers") in (None, ""):
        out["workers"] = int(read_setting(_BY_KEY[WORKERS_KEY], store))
    if out.get("vram_cap_gb") in (None, ""):
        cap = float(read_setting(_BY_KEY[VRAM_CAP_KEY], store))
        if cap > 0:
            out["vram_cap_gb"] = cap
    if out.get("allow_devices") in (None, ""):
        devices = read_setting(_BY_KEY[DEVICES_KEY], store)
        indexes = [int(item) for item in (devices if isinstance(devices, (list, tuple)) else [devices]) if item != ""]
        if indexes:
            out["allow_devices"] = indexes
    if out.get("palette_mode") in (None, ""):
        out["palette_mode"] = str(read_setting(_BY_KEY[PALETTE_MODE_KEY], store)).strip().lower()
    if out.get("dering_strength") in (None, ""):
        out["dering_strength"] = float(read_setting(_BY_KEY[DERING_STRENGTH_KEY], store))
    return out
