"""Guided/Graph override checks and Generate matrix sweeps (#739, #740).

Lives outside ``backend.src.models`` so GUI tests can import it. That
suite replaces ``backend.src.models`` with an empty package stub.
"""
from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass

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
    if value != value:  # NaN
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
    stopped: str | None = None  # "cap" | "lease" | "stop" | "pressure"


class GpuLease:
    """One holder at a time. A matrix sweep keeps it across every cell."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.owner: str | None = None

    def try_acquire(self, owner: str) -> bool:
        if not self._lock.acquire(blocking=False):
            return False
        self.owner = owner
        return True

    def release(self, owner: str) -> None:
        if self.owner != owner:
            return
        self.owner = None
        self._lock.release()


gpu_lease = GpuLease()


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
        if isinstance(node_overrides, dict):
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
        f"{count} cells{steps_bit}. One GPU lease for the whole sweep. "
        f"Cell cap {CELL_CAP}. Cells queue at {PREVIEW_EDGE}px. "
        "Promote restores the guided width and height. "
        "Stops between cells if VRAM is tight."
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
    overrides: dict = {node_id: {spec.input_name: value}}
    if preview_edge is not None:
        latent = find_node_id(workflow, LATENT_TYPES)
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


def run_matrix_sweep(
    *,
    workflow: dict,
    axis: str,
    values: list,
    queue: Callable[[dict, dict], str],
    template_name: str | None = None,
    base_overrides: dict | None = None,
    preview_edge: int | None = PREVIEW_EDGE,
    parent_prompt_id: str | None = None,
    stop_check: Callable[[], bool] | None = None,
    pressure_check: Callable[[], bool] | None = None,
    lease: GpuLease | None = None,
    lease_owner: str = "matrix",
) -> SweepResult:
    """Queue one ``queue_workflow`` per value. No new execution engine."""
    if len(values) > CELL_CAP:
        return SweepResult((), parent_prompt_id, "cap")
    holder = lease or gpu_lease
    if not holder.try_acquire(lease_owner):
        return SweepResult((), parent_prompt_id, "lease")
    prompt_ids: list[str] = []
    parent = parent_prompt_id
    stopped: str | None = None
    try:
        for index, value in enumerate(values):
            if index and stop_check is not None and stop_check():
                stopped = "stop"
                break
            if index and _under_pressure(pressure_check):
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
    finally:
        holder.release(lease_owner)
    return SweepResult(tuple(prompt_ids), parent, stopped)
