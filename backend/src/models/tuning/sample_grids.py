"""#747: fixed-prompt/seed sample-grid production for checkpoint comparison.

Both LoRA trainers call into this at their checkpoint-save points so
ordinary training emits ``samples/step-NNNNNN.png`` grids (via
``DiagnosticsLogger.save_sample``) that the blind tournament (#747) and
the live panel (#742) consume. Prompts and seed are fixed per run — grids
are only comparable across checkpoints when every grid used the same
prompts and the same noise.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager

log = logging.getLogger(__name__)

# Generic anime fallbacks when a run provides neither validation prompts
# nor a trigger word; phrased for the Illustrious/NoobAI model family.
_DEFAULT_TEMPLATES = (
    "masterpiece, best quality, {trigger}",
    "{trigger}, detailed anime illustration, clean lineart",
    "1girl, {trigger}, upper body, looking at viewer",
    "{trigger}, wide shot, scenery, atmospheric lighting",
)


def default_sample_prompts(trigger: str = "") -> list[str]:
    """The fixed prompt set for one grid. A non-empty trigger wins;
    otherwise fall back to a generic stand-in so grids stay fixed."""
    t = (trigger or "").strip() or "anime style"
    return [tpl.format(trigger=t) for tpl in _DEFAULT_TEMPLATES]


def build_sampling_pipe(
    *,
    is_sdxl: bool,
    vae,
    text_encoder_one,
    text_encoder_two,
    tokenizer_one,
    tokenizer_two,
    unet,
    noise_scheduler,
    prediction_type: str = "epsilon",
):
    """Compose a diffusers pipeline from components the trainer already
    holds — no base-model reload. Verified by py_compile/stub only: the
    resource rule forbids the GPU run a real construction needs."""
    from diffusers import (
        DDPMScheduler,
        DPMSolverMultistepScheduler,
        StableDiffusionPipeline,
        StableDiffusionXLPipeline,
    )

    if prediction_type == "v_prediction":
        scheduler = DPMSolverMultistepScheduler.from_config(noise_scheduler.config, prediction_type=prediction_type)
    else:
        scheduler = DDPMScheduler.from_config(noise_scheduler.config, prediction_type=prediction_type)

    if is_sdxl:
        return StableDiffusionXLPipeline(
            vae=vae,
            text_encoder=text_encoder_one,
            text_encoder_2=text_encoder_two,
            tokenizer=tokenizer_one,
            tokenizer_2=tokenizer_two,
            unet=unet,
            scheduler=scheduler,
        )
    return StableDiffusionPipeline(
        vae=vae,
        text_encoder=text_encoder_one,
        tokenizer=tokenizer_one,
        unet=unet,
        scheduler=scheduler,
        safety_checker=None,
        feature_extractor=None,
        requires_safety_checker=False,
    )


@contextmanager
def sampling_state(*components):
    """Sampling shares training modules; restore modes, dtypes and RNG on failure too."""
    import random

    import numpy as np
    import torch

    modules = {module for component in components if isinstance(component, torch.nn.Module)
               for module in component.modules()}
    modes = [(module, module.training) for module in modules]
    tensors = {tensor for module in modules
               for tensor in (*module.parameters(recurse=False), *module.buffers(recurse=False))}
    dtypes = [(tensor, tensor.dtype) for tensor in tensors]
    devices = sorted({tensor.device.index for tensor in tensors if tensor.is_cuda})
    python_state, numpy_state = random.getstate(), np.random.get_state()
    try:
        with torch.random.fork_rng(devices=devices):
            for module, _ in modes:
                module.training = False
            yield
    finally:
        for tensor, dtype in dtypes:
            if tensor.dtype != dtype:
                tensor.data = tensor.data.to(dtype=dtype)
        for module, training in modes:
            module.training = training
        random.setstate(python_state)
        np.random.set_state(numpy_state)
