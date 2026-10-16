"""Job-parameter VRAM estimates for GpuLeaseArbiter admission (#758).

Parametric heuristics, then a per-owner scale from measured peaks
(``gpu_vram_calibration``). Not a memory-fit guarantee: custom nodes,
ControlNet, and Comfy HTTP occupancy are still out of band. After a local
run the arbiter records measured peak and can only raise that scale.
"""
from __future__ import annotations

from typing import Any

# fp16 parameter memory, rounded from public checkpoints.
WEIGHT_GB = {
    "sd15": 2.0,
    "sdxl": 6.6,
    "animegan": 0.4,
    "esrgan": 0.07,
    "clip": 0.6,
    "gan": 0.15,
    "vlm": 4.5,
}

# Activation GB at 512², batch 1. SDXL is heavier per pixel than SD1.5.
ACT_GB_512 = {
    "sd15": 2.0,
    "sdxl": 1.5,
}

REF_PIXELS = 512 * 512
DEFAULT_TILE = 400


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if number > 0 else default


def _finite_gb(value: float) -> float:
    return round(max(float(value), 0.1), 2)


def model_family(model_id: str | None) -> str:
    text = (model_id or "").lower()
    if "animegan" in text:
        return "animegan"
    if any(token in text for token in ("esrgan", "realesrgan", "upscal")):
        return "esrgan"
    if any(token in text for token in ("sdxl", "sd_xl", "xl-", "-xl", "_xl_", "illustrious", "pony", "noobai", "lumina")):
        return "sdxl"
    if any(token in text for token in ("sd3", "stable-diffusion-3", "flux")):
        return "sdxl"
    return "sd15"


def workflow_latent_size(workflow: dict | None) -> tuple[int, int]:
    for node in (workflow or {}).values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") not in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            continue
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        return (
            _positive_int(inputs.get("width"), 512),
            _positive_int(inputs.get("height"), 512),
        )
    return (512, 512)


def workflow_batch_size(workflow: dict | None) -> int:
    batches = [
        _positive_int(node.get("inputs", {}).get("batch_size"), 1)
        for node in (workflow or {}).values()
        if isinstance(node, dict)
        and node.get("class_type") in {"EmptyLatentImage", "EmptySD3LatentImage"}
        and isinstance(node.get("inputs"), dict)
    ]
    return max(batches, default=1)


def workflow_family(workflow: dict | None, checkpoint: str | None = None) -> str:
    names = [checkpoint or ""]
    for node in (workflow or {}).values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        for key in ("ckpt_name", "checkpoint", "unet_name", "model"):
            value = inputs.get(key)
            if isinstance(value, str):
                names.append(value)
        class_type = str(node.get("class_type") or "")
        if "SDXL" in class_type or "SD3" in class_type:
            return "sdxl"
    return model_family(" ".join(names))


def diffusion_gb(
    *,
    family: str = "sd15",
    width: Any = 512,
    height: Any = 512,
    batch: Any = 1,
    extra_gb: float = 0.0,
) -> float:
    if family == "animegan":
        return _finite_gb(1.5 + 0.2 * max(_positive_int(batch, 1) - 1, 0))
    scale = (
        _positive_int(width, 512)
        * _positive_int(height, 512)
        / REF_PIXELS
        * _positive_int(batch, 1)
    )
    weights = WEIGHT_GB.get(family, WEIGHT_GB["sd15"])
    activations = ACT_GB_512.get(family, ACT_GB_512["sd15"]) * scale
    return _finite_gb(weights + activations + extra_gb)


def image_size(path: str | None) -> tuple[int, int] | None:
    if not path:
        return None
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        with Image.open(path) as image:
            return (int(image.width), int(image.height))
    except Exception:
        return None


def estimate_job_gb(owner: str, **job: Any) -> float:
    """Positive VRAM estimate for a production lease owner."""
    from backend.src.core.gpu_vram_calibration import apply_scale

    return apply_scale(owner, _formula_job_gb(owner, **job))


def _formula_job_gb(owner: str, **job: Any) -> float:
    family = model_family(job.get("model_id") or job.get("checkpoint"))
    if owner in {"guided", "graph", "promoted", "matrix", "guidance"}:
        width = job.get("width")
        height = job.get("height")
        if width is None or height is None:
            width, height = workflow_latent_size(job.get("workflow"))
        family = workflow_family(job.get("workflow"), job.get("checkpoint") or job.get("model_id"))
        return diffusion_gb(family=family, width=width, height=height, batch=job.get("batch", workflow_batch_size(job.get("workflow"))))
    if owner == "lora-generate":
        return diffusion_gb(
            family=family,
            width=job.get("width", 512),
            height=job.get("height", 512),
            batch=job.get("batch_size", 1),
        )
    if owner in {"lora-train", "training-experiment"}:
        rank = _positive_int(job.get("rank"), 4)
        batch = _positive_int(job.get("batch_size"), 1)
        extra = 2.4 + rank / 16 * 0.5 + max(batch - 1, 0) * 0.8
        return diffusion_gb(family=family, width=512, height=512, batch=1, extra_gb=extra)
    if owner == "upscale":
        tile = _positive_int(job.get("tile_size"), DEFAULT_TILE)
        # ESRGANWrapper keeps the entire fp32 RGB input on the device while tiling.
        input_gb = _positive_int(job.get("width"), tile) * _positive_int(job.get("height"), tile) * 12 / 1024**3
        return _finite_gb(WEIGHT_GB["esrgan"] + (tile * tile) / REF_PIXELS * 1.6 + input_gb)
    if owner == "gan-train":
        return _finite_gb(WEIGHT_GB["gan"] + 0.7 + _positive_int(job.get("batch_size"), 1) * 0.08)
    if owner == "cbir-train":
        return _finite_gb(WEIGHT_GB["clip"] + 1.4 + _positive_int(job.get("batch_size"), 64) / 64 * 1.6)
    if owner == "dataset-advisor":
        return _finite_gb(WEIGHT_GB["clip"] + 1.2)
    if owner == "vlm-advise":
        return _finite_gb(WEIGHT_GB["vlm"])
    if owner == "loss-slice":
        return diffusion_gb(family=family, width=512, height=512, extra_gb=1.8)
    if "train" in owner:
        return diffusion_gb(family=family, extra_gb=2.4)
    return diffusion_gb(family=family, width=job.get("width", 512), height=job.get("height", 512))


formula_job_gb = _formula_job_gb

__all__ = [
    "DEFAULT_TILE",
    "WEIGHT_GB",
    "diffusion_gb",
    "estimate_job_gb",
    "formula_job_gb",
    "image_size",
    "model_family",
    "workflow_family",
    "workflow_latent_size",
]
