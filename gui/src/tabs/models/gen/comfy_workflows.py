"""ComfyUI workflow modes, template building and queuing (split from comfy_generate_tab)."""
import copy
import json
from pathlib import Path

from backend.src.comfy_matrix import apply_node_overrides, gpu_lease, merge_sampler_overrides, try_admit
from backend.src.core.gpu_vram_estimate import estimate_job_gb

from gui.src.helpers.base import BaseQThreadWorker


class ImageUploadWorker(BaseQThreadWorker):
    """Off-thread worker to upload a local image to ComfyUI server (#755)."""

    def __init__(self, manager, local_path: str, node_id: str, request: int) -> None:
        super().__init__()
        self._manager = manager
        self._local_path = local_path
        self._node_id = node_id
        self._request = request

    def _execute(self) -> tuple[int, str, str, str]:
        # Returns (node_id, local_path, server_token)
        server_token = self._manager.upload_image(self._local_path)
        return (self._request, self._node_id, self._local_path, server_token)

# Content Gen §1.4 (issue #35) — ControlNet + IP-Adapter workflow modes.
#
# Each mode maps to a curated workflow JSON template under
# configs/comfy_workflows/ plus the node ids that need overriding: the base
# checkpoint, positive/negative prompt text, the extra conditioning image
# (control image for ControlNet, reference image for IP-Adapter), and the
# extra model checkpoint (ControlNet or IP-Adapter weights). The three
# ControlNet sub-modes share one template and differ only in which
# preprocessor's control image / ControlNet checkpoint the user supplies.
WORKFLOW_MODES = {
    "controlnet_pose": {
        "label": "ControlNet — Pose (OpenPose)",
        "template": "controlnet_generate.json",
        "checkpoint_node": "1",
        "positive_node": "2",
        "negative_node": "3",
        "image_node": "9",
        "extra_node": "8",
        "extra_key": "control_net_name",
        "extra_default": "control_v11p_sd15_openpose.pth",
        "extra_label": "ControlNet Checkpoint:",
        "image_label": "Pose Control Image:",
    },
    "controlnet_depth": {
        "label": "ControlNet — Depth",
        "template": "controlnet_generate.json",
        "checkpoint_node": "1",
        "positive_node": "2",
        "negative_node": "3",
        "image_node": "9",
        "extra_node": "8",
        "extra_key": "control_net_name",
        "extra_default": "control_v11f1p_sd15_depth.pth",
        "extra_label": "ControlNet Checkpoint:",
        "image_label": "Depth Control Image:",
    },
    "controlnet_canny": {
        "label": "ControlNet — Canny",
        "template": "controlnet_generate.json",
        "checkpoint_node": "1",
        "positive_node": "2",
        "negative_node": "3",
        "image_node": "9",
        "extra_node": "8",
        "extra_key": "control_net_name",
        "extra_default": "control_v11p_sd15_canny.pth",
        "extra_label": "ControlNet Checkpoint:",
        "image_label": "Canny Control Image:",
    },
    "ipadapter_reference": {
        "label": "IP-Adapter — Reference Image",
        "template": "ipadapter_generate.json",
        "checkpoint_node": "1",
        "positive_node": "6",
        "negative_node": "7",
        "image_node": "4",
        "extra_node": "3",
        "extra_key": "ipadapter_file",
        "extra_default": "ip-adapter-plus_sdxl_vit-h.safetensors",
        "extra_label": "IP-Adapter Checkpoint:",
        "image_label": "Reference Image:",
    },
    "lora": {
        "label": "LoRA",
        "template": "lora_generate.json",
        "checkpoint_node": "1",
        "positive_node": "3",
        "negative_node": "4",
        "image_node": None,
        "extra_node": "2",
        "extra_key": "lora_name",
        "extra_default": "anime_lora.safetensors",
        "extra_label": "LoRA file:",
        "image_label": "No control image for LoRA.",
    },
}


# Template loading/override-merging is duplicated here (a thin ~10-line
# mirror of ComfyUIManager.load_workflow()/apply_overrides()) rather than
# imported from backend.src.models.core.comfy_manager, because
# gui/test/conftest.py blanket-mocks that module for every GUI test (its
# "block heavy imports" convention, predating this change, applies to the
# whole models/core package). Keeping the pure template logic self-contained
# here means build_workflow() stays unit-testable without fighting that
# mock; the network calls (upload_image/queue_workflow) still go through
# self._manager, which individual tests mock per-instance as needed.
_WORKFLOWS_DIR = Path(__file__).resolve().parents[5] / "configs" / "comfy_workflows"


def _load_workflow_template(name: str) -> dict:
    with open(_WORKFLOWS_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def plan_guided_workflow(
    mode: str,
    *,
    base_checkpoint: str,
    extra_checkpoint: str,
    positive_prompt: str,
    negative_prompt: str,
    image_filename: str,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
) -> tuple[dict, dict]:
    """Return ``(workflow, overrides)`` for one guided submission.

    The override map is what ``apply_node_overrides`` merged. Unknown node
    ids raise ``UnknownWorkflowNodeError`` instead of being dropped.
    """
    cfg = WORKFLOW_MODES[mode]
    template = copy.deepcopy(_load_workflow_template(cfg["template"]))
    overrides = {
        cfg["checkpoint_node"]: {"ckpt_name": base_checkpoint},
        cfg["positive_node"]: {"text": positive_prompt},
        cfg["negative_node"]: {"text": negative_prompt},
    }
    if cfg.get("image_node"):
        overrides[cfg["image_node"]] = {"image": image_filename}
    if cfg.get("extra_node"):
        overrides[cfg["extra_node"]] = {cfg["extra_key"]: extra_checkpoint}
    overrides = merge_sampler_overrides(
        template, overrides, seed=seed, width=width, height=height,
    )
    return apply_node_overrides(template, overrides), overrides


def build_workflow(
    mode: str,
    *,
    base_checkpoint: str,
    extra_checkpoint: str,
    positive_prompt: str,
    negative_prompt: str,
    image_filename: str,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """Load the curated template for *mode* and apply the GUI's parameter
    overrides (base checkpoint, prompts, extra ControlNet/IP-Adapter
    checkpoint, and the uploaded extra-image filename).

    Pure function (no Qt / no network) so it can be exercised directly in
    tests without a running ComfyUI server or QApplication.
    """
    workflow, _overrides = plan_guided_workflow(
        mode,
        base_checkpoint=base_checkpoint,
        extra_checkpoint=extra_checkpoint,
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        image_filename=image_filename,
        seed=seed,
        width=width,
        height=height,
    )
    return workflow


def _queue_workflow(
    manager, log, mode, image_path, base_checkpoint, extra_checkpoint,
    positive_prompt, negative_prompt, *, seed=None, width=None, height=None,
    run_meta=None, cancel=None, uploaded_image=None,
) -> None:
    refusal = try_admit(
        "guided",
        estimated_gb=estimate_job_gb(
            "guided",
            width=width,
            height=height,
            checkpoint=base_checkpoint,
        ),
    )
    if refusal:
        log(f"[workflow] {refusal}\n")
        return
    try:
        cfg = WORKFLOW_MODES[mode]
        uploaded_name = uploaded_image or image_path
        if cfg.get("image_node") and not uploaded_image:
            log(f"[workflow] Uploading {image_path}…\n")
            uploaded_name = manager.upload_image(image_path)

        workflow, overrides = plan_guided_workflow(
            mode,
            base_checkpoint=base_checkpoint,
            extra_checkpoint=extra_checkpoint,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            image_filename=uploaded_name,
            seed=seed,
            width=width,
            height=height,
        )
        meta = {
            "surface_mode": "guided",
            "template_name": WORKFLOW_MODES[mode]["template"],
            "applied_overrides": overrides,
        }
        if run_meta:
            meta.update(run_meta)

        log(f"[workflow] Queuing {WORKFLOW_MODES[mode]['label']}…\n")
        prompt_id = manager.queue_workflow(workflow, run_meta=meta)
        log(f"[workflow] Queued — prompt_id={prompt_id}\n")
        manager.wait_for_run(prompt_id, cancel=cancel)
    except Exception as exc:
        log(f"[workflow] Error: {exc}\n")
    finally:
        gpu_lease.release("guided")
