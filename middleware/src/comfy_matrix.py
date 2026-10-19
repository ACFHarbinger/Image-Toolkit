"""Guided/Graph override checks and Generate matrix sweeps (#739, #740).

Lives outside ``middleware.src.models`` so GUI tests can import it. That
suite replaces ``middleware.src.models`` with an empty package stub.
"""
from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable
from dataclasses import dataclass

from middleware.src.core.gpu_lease_arbiter import (
    PROFILE_BALANCED,
    GpuLeaseArbiter,
    cuda_device_total_gb,
    cuda_peak_gb,
    profile_from_env,
    release_unused_cuda_blocks,
)
from middleware.src.core.gpu_vram_estimate import estimate_job_gb

CELL_MIN = 3
CELL_MAX = 9
CELL_CAP = 25
PREVIEW_EDGE = 512
# Stop between sweep cells when free VRAM falls below this fraction.
VRAM_FREE_FLOOR = 0.15

KSAMPLER_TYPES = ("KSampler", "KSamplerAdvanced")
LORA_TYPES = ("LoraLoader", "LoraLoaderModelOnly")
CONTROLNET_TYPES = ("ControlNetApplyAdvanced", "ControlNetApply")
LATENT_TYPES = ("EmptyLatentImage",)


class UnknownWorkflowNodeError(ValueError):
    """An override named a node id the workflow does not contain."""

    def __init__(self, node_ids: list[str]) -> None:
        self.node_ids = list(node_ids)
        listed = ", ".join(self.node_ids)
        super().__init__(f"Unknown workflow node id(s): {listed}")


class AxisNotInWorkflow(ValueError):
    """The sweep axis has no matching node in this workflow."""

    def __init__(self, axis: str, class_types: tuple[str, ...]) -> None:
        self.axis = axis
        self.class_types = class_types
        names = " or ".join(class_types)
        super().__init__(f"Axis '{axis}' needs a {names} node, and this workflow has none.")


def _parse_int(text: str) -> int:
    try:
        return int(text, 10)
    except ValueError as exc:
        raise ValueError(f"Could not read integer value {text!r}.") from exc


def _parse_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"Could not read number {text!r}.") from exc
    if not math.isfinite(value):
        raise ValueError(f"Could not read number {text!r}.")
    return value


@dataclass(frozen=True)
class AxisSpec:
    key: str
    class_types: tuple[str, ...]
    input_name: str
    caster: Callable[[str], object]


AXES: dict[str, AxisSpec] = {
    "seed": AxisSpec("seed", KSAMPLER_TYPES, "seed", _parse_int),
    "cfg": AxisSpec("cfg", KSAMPLER_TYPES, "cfg", _parse_float),
    "steps": AxisSpec("steps", KSAMPLER_TYPES, "steps", _parse_int),
    "lora_weight": AxisSpec("lora_weight", LORA_TYPES, "strength_model", _parse_float),
    "controlnet_strength": AxisSpec("controlnet_strength", CONTROLNET_TYPES, "strength", _parse_float),
}


@dataclass(frozen=True)
class SweepResult:
    prompt_ids: tuple[str, ...]
    parent_prompt_id: str | None
    stopped: str | None = None  # "cap" | "lease" | "stop" | "pressure" | "thermal" | "execution"


# Stop a sweep when a GPU sensor reports at least this temperature.
THERMAL_CEILING_C = 85.0
VIEW_BYTE_CAP = 2_000_000


class GpuLease(GpuLeaseArbiter):
    """In-process admission: one holder at a time.

    Comfy submissions, training, and other model jobs share this object.
    A matrix sweep keeps it until each cell's execution returns. Comfy's
    browser queue is not visible here, so ``machine_wide`` stays false.

    Occupancy the mutex cannot cover (estimated vs device VRAM, conservative
    vs balanced profiles, a noted Comfy browser session) lives on
    ``GpuLeaseArbiter``. ``empty_cache`` on the process lease only runs on a
    job-kind transition and is not a general VRAM fix.
    """


def _startup_profile() -> str:
    try:
        return profile_from_env()
    except ValueError:
        return PROFILE_BALANCED


gpu_lease = GpuLease(
    profile=_startup_profile(),
    empty_cache=release_unused_cuda_blocks,
    peak_reader=cuda_peak_gb,
    device_probe=cuda_device_total_gb,
)


def try_admit(
    owner: str,
    lease: GpuLease | None = None,
    *,
    estimated_gb: float | None = None,
    kind: str | None = None,
) -> str | None:
    """Acquire *lease* for *owner*. Return a refusal message when it cannot."""
    holder = lease or gpu_lease
    if holder.try_acquire(owner, estimated_gb=estimated_gb, kind=kind):
        return None
    return holder.refusal_text()


def apply_node_overrides(workflow: dict, overrides: dict | None) -> dict:
    """Copy *workflow* and merge per-node inputs. Unknown ids raise."""
    result = copy.deepcopy(workflow)
    missing: list[str] = []
    for node_id, node_overrides in (overrides or {}).items():
        key = str(node_id)
        node = result.get(key)
        if not isinstance(node, dict):
            missing.append(key)
            continue
        if not isinstance(node_overrides, dict) or not isinstance(node.get("inputs", {}), dict):
            raise ValueError(f"Overrides and inputs for node '{key}' must be objects.")
        node.setdefault("inputs", {}).update(node_overrides)
    if missing:
        raise UnknownWorkflowNodeError(missing)
    return result


def find_node_id(workflow: dict, class_types: tuple[str, ...]) -> str | None:
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") in class_types:
            return str(node_id)
    return None


def merge_sampler_overrides(
    workflow: dict,
    overrides: dict,
    *,
    seed: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Add sampler/latent inputs to *overrides* when the caller set them."""
    merged = {str(key): dict(value) for key, value in overrides.items() if isinstance(value, dict)}
    sampler_inputs = _present(seed=seed, steps=steps, cfg=cfg)
    if sampler_inputs:
        node_id = find_node_id(workflow, KSAMPLER_TYPES)
        if node_id is None:
            raise AxisNotInWorkflow("seed", KSAMPLER_TYPES)
        if "seed" in sampler_inputs and workflow[node_id]["class_type"] == "KSamplerAdvanced":
            sampler_inputs["noise_seed"] = sampler_inputs.pop("seed")
        merged.setdefault(node_id, {}).update(sampler_inputs)
    latent_inputs = _present(width=width, height=height)
    if latent_inputs:
        node_id = find_node_id(workflow, LATENT_TYPES)
        if node_id is None:
            raise AxisNotInWorkflow("size", LATENT_TYPES)
        merged.setdefault(node_id, {}).update(latent_inputs)
    return merged


def _present(**values: object) -> dict:
    return {key: value for key, value in values.items() if value is not None}


def merge_override_maps(base: dict | None, extra: dict) -> dict:
    merged = {str(key): dict(value) for key, value in (base or {}).items() if isinstance(value, dict)}
    for key, values in extra.items():
        if isinstance(values, dict):
            merged.setdefault(str(key), {}).update(values)
    return merged


def output_paths(record) -> tuple[str, ...]:
    paths: list[str] = []
    for item in getattr(record, "outputs", ()) or ():
        filename = getattr(item, "filename", None)
        if not isinstance(filename, str) or not filename:
            continue
        subfolder = getattr(item, "subfolder", "") or ""
        paths.append(f"{subfolder}/{filename}" if subfolder else filename)
    return tuple(paths)


def parse_graph_submission(workflow_text: str, overrides_text: str) -> tuple[dict, dict]:
    """Parse a graph draft plus an override object. Unknown node ids raise."""
    workflow = _json_object(workflow_text, "Graph JSON")
    raw = overrides_text.strip() or "{}"
    overrides = _json_object(raw, "Override JSON")
    return apply_node_overrides(workflow, overrides), overrides


def _json_object(text: str, label: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def parse_axis_values(axis: str, text: str) -> list:
    spec = AXES.get(axis)
    if spec is None:
        raise ValueError(f"Unknown sweep axis {axis!r}.")
    parts = [part.strip() for part in text.replace("\n", ",").split(",")]
    parts = [part for part in parts if part]
    return [spec.caster(part) for part in parts]


def check_cell_count(count: int) -> str | None:
    if count > CELL_CAP:
        return f"{count} cells exceeds the cap of {CELL_CAP}."
    if count < CELL_MIN or count > CELL_MAX:
        return f"Use {CELL_MIN} to {CELL_MAX} values (got {count})."
    return None


def cost_estimate(count: int, steps: int | None = None) -> str:
    steps_bit = f" × {steps} steps" if steps else ""
    return (
        f"{count} cells{steps_bit}. {gpu_lease.scope_text()} "
        f"Cell cap {CELL_CAP}. Cells queue at {PREVIEW_EDGE}px. "
        "Promote restores the guided width and height. "
        f"Stops between cells if free VRAM is under {int(VRAM_FREE_FLOOR * 100)}% "
        f"or GPU temperature reaches {int(THERMAL_CEILING_C)}C."
    )


def prepare_sweep(axis: str, text: str) -> tuple[list | None, str]:
    if not text.strip():
        return None, f"Enter {CELL_MIN}–{CELL_MAX} comma-separated values. Cell cap {CELL_CAP}."
    try:
        values = parse_axis_values(axis, text)
    except ValueError as exc:
        return None, str(exc)
    error = check_cell_count(len(values))
    if error:
        return None, error
    return values, cost_estimate(len(values))


def cell_overrides(workflow: dict, axis: str, value, preview_edge: int | None) -> dict:
    spec = AXES[axis]
    node_id = find_node_id(workflow, spec.class_types)
    if node_id is None:
        raise AxisNotInWorkflow(axis, spec.class_types)
    input_name = spec.input_name
    if axis == "seed" and workflow[node_id]["class_type"] == "KSamplerAdvanced":
        input_name = "noise_seed"
    overrides: dict = {node_id: {input_name: value}}
    if preview_edge is not None:
        latent = find_node_id(workflow, LATENT_TYPES)
        if latent is None:
            raise AxisNotInWorkflow("preview size", LATENT_TYPES)
        if latent is not None:
            overrides[latent] = {"width": preview_edge, "height": preview_edge}
    return overrides


def with_latent_size(workflow: dict, width: int, height: int) -> dict:
    latent = find_node_id(workflow, LATENT_TYPES)
    if latent is None:
        return copy.deepcopy(workflow)
    return apply_node_overrides(workflow, {latent: {"width": width, "height": height}})


def promote_cell(workflow: dict, *, full_width: int, full_height: int) -> dict:
    """Clone a sweep cell at the guided full resolution."""
    return with_latent_size(workflow, full_width, full_height)


def build_promoted_submission(
    workflow: dict,
    *,
    full_width: int,
    full_height: int,
    parent_prompt_id: str | None,
    template_name: str | None,
) -> tuple[dict, dict]:
    promoted = promote_cell(workflow, full_width=full_width, full_height=full_height)
    latent = find_node_id(promoted, LATENT_TYPES)
    overrides = {latent: {"width": full_width, "height": full_height}} if latent else {}
    meta = {
        "surface_mode": "promoted",
        "template_name": template_name,
        "applied_overrides": overrides,
        "parent_prompt_id": parent_prompt_id,
    }
    return promoted, meta


def vram_pressure(free_ratio_floor: float = VRAM_FREE_FLOOR) -> bool:
    """True when CUDA reports little free memory. CPU-only sessions are not pressure."""
    try:
        import torch
    except Exception:
        return False
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not cuda.is_available():
        return False
    try:
        free, total = cuda.mem_get_info()
    except Exception:
        return False
    if not total:
        return False
    return (free / total) < free_ratio_floor


def _under_pressure(pressure_check: Callable[[], bool] | None) -> bool:
    check = pressure_check or vram_pressure
    try:
        return bool(check())
    except Exception:
        return False


def read_gpu_temperature_c() -> float | None:
    """NVIDIA sensor in Celsius, or None when no reading is available."""
    import shutil
    import subprocess

    if shutil.which("nvidia-smi") is None:
        return None
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    line = output.strip().splitlines()[0].strip() if output.strip() else ""
    try:
        return float(line.split()[0])
    except (IndexError, ValueError):
        return None


def thermal_pressure(
    read_celsius: Callable[[], float | None] | None = None,
    ceiling: float = THERMAL_CEILING_C,
) -> bool:
    """True when a temperature reading reaches *ceiling*. A missing sensor is not pressure."""
    reader = read_celsius or read_gpu_temperature_c
    try:
        value = reader()
    except Exception:
        return False
    if value is None:
        return False
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(temperature):
        return False
    return temperature >= ceiling


def _under_thermal(thermal_check: Callable[[], bool] | None) -> bool:
    check = thermal_pressure if thermal_check is None else thermal_check
    try:
        return bool(check())
    except Exception:
        return False


def fetch_comfy_view(
    base_url: str,
    filename: str,
    subfolder: str = "",
    kind: str = "output",
    limit: int = VIEW_BYTE_CAP,
) -> bytes:
    """GET ComfyUI ``/view``. Callers run this off the GUI thread."""
    from urllib.parse import urlencode
    from urllib.request import urlopen

    query = urlencode({"filename": filename, "subfolder": subfolder or "", "type": kind,
                       "preview": "webp;80"})
    with urlopen(f"{base_url.rstrip('/')}/view?{query}", timeout=5) as response:
        data = response.read(limit + 1)
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("Comfy /view did not return bytes.")
    if len(data) > limit:
        raise ValueError("Comfy preview exceeds the byte limit.")
    return bytes(data)


def run_matrix_sweep(
    *,
    workflow: dict,
    axis: str,
    values: list,
    queue: Callable[[dict, dict], str],
    wait_for_completion: Callable[[str], bool],
    template_name: str | None = None,
    base_overrides: dict | None = None,
    preview_edge: int | None = PREVIEW_EDGE,
    parent_prompt_id: str | None = None,
    stop_check: Callable[[], bool] | None = None,
    pressure_check: Callable[[], bool] | None = None,
    thermal_check: Callable[[], bool] | None = None,
    lease: GpuLease | None = None,
    lease_owner: str = "matrix",
) -> SweepResult:
    """Submit and await each cell under one lease, checking limits between jobs."""
    if len(values) > CELL_CAP:
        return SweepResult((), parent_prompt_id, "cap")
    holder = lease or gpu_lease
    edge = preview_edge or PREVIEW_EDGE
    if not holder.try_acquire(
        lease_owner,
        estimated_gb=estimate_job_gb(
            lease_owner,
            workflow=workflow,
            width=edge,
            height=edge,
        ),
    ):
        return SweepResult((), parent_prompt_id, "lease")
    prompt_ids: list[str] = []
    parent = parent_prompt_id
    stopped: str | None = None
    try:
        for value in values:
            if stop_check is not None and stop_check():
                stopped = "stop"
                break
            if _under_thermal(thermal_check):
                stopped = "thermal"
                break
            if _under_pressure(pressure_check):
                stopped = "pressure"
                break
            extra = cell_overrides(workflow, axis, value, preview_edge)
            applied = merge_override_maps(base_overrides, extra)
            cell = apply_node_overrides(workflow, extra)
            meta = {
                "surface_mode": "matrix",
                "template_name": template_name,
                "applied_overrides": applied,
                "parent_prompt_id": parent,
                "sweep_axis": axis,
                "sweep_value": str(value),
            }
            prompt_id = str(queue(cell, meta))
            prompt_ids.append(prompt_id)
            if parent is None:
                parent = prompt_id
            # Submission only acknowledges a queued job. Keep the lease until
            # execution finishes before checking pressure or submitting another.
            if not wait_for_completion(prompt_id):
                stopped = "execution"
                break
    finally:
        holder.release(lease_owner)
    return SweepResult(tuple(prompt_ids), parent, stopped)
