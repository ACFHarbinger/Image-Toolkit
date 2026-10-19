"""#747: fixed sample prompts + sampling-pipe composition for checkpoint grids."""
from types import SimpleNamespace

import diffusers

from middleware.src.models.tuning import sample_grids


class _FakeScheduler:
    @classmethod
    def from_config(cls, config, **kwargs):
        return ("scheduler", config)


class _FakePipeline:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_default_prompts_substitute_trigger():
    prompts = sample_grids.default_sample_prompts("zxc")
    assert len(prompts) == 4
    assert all("zxc" in p for p in prompts)
    assert len(set(prompts)) == 4


def test_default_prompts_fallback_when_trigger_blank():
    for blank in ("", "   "):
        prompts = sample_grids.default_sample_prompts(blank)
        assert all("anime style" in p for p in prompts)


def test_build_pipe_routes_sdxl_components(monkeypatch):
    monkeypatch.setattr(diffusers, "StableDiffusionXLPipeline", _FakePipeline)
    monkeypatch.setattr(diffusers, "DPMSolverMultistepScheduler", _FakeScheduler)
    ns = SimpleNamespace(config={"prediction_type": "v_prediction"})
    pipe = sample_grids.build_sampling_pipe(
        is_sdxl=True,
        vae="vae",
        text_encoder_one="te1",
        text_encoder_two="te2",
        tokenizer_one="tok1",
        tokenizer_two="tok2",
        unet="unet",
        noise_scheduler=ns,
        prediction_type="v_prediction",
    )
    assert pipe.kwargs["text_encoder_2"] == "te2"
    assert pipe.kwargs["tokenizer_2"] == "tok2"
    assert pipe.kwargs["unet"] == "unet"
    assert pipe.kwargs["scheduler"] == ("scheduler", ns.config)


def test_build_pipe_sd15_uses_ddpm_and_no_second_encoder(monkeypatch):
    monkeypatch.setattr(diffusers, "StableDiffusionPipeline", _FakePipeline)
    monkeypatch.setattr(diffusers, "DDPMScheduler", _FakeScheduler)
    ns = SimpleNamespace(config={})
    pipe = sample_grids.build_sampling_pipe(
        is_sdxl=False,
        vae="vae",
        text_encoder_one="te1",
        text_encoder_two=None,
        tokenizer_one="tok1",
        tokenizer_two=None,
        unet="unet",
        noise_scheduler=ns,
        prediction_type="epsilon",
    )
    assert pipe.kwargs["safety_checker"] is None
    assert pipe.kwargs["feature_extractor"] is None
    assert "text_encoder_2" not in pipe.kwargs
    assert pipe.kwargs["scheduler"] == ("scheduler", ns.config)


def test_sdxl_arguments_match_installed_diffusers_signature(monkeypatch):
    import inspect
    signature = inspect.signature(diffusers.StableDiffusionXLPipeline.__init__)
    class StrictPipeline(_FakePipeline):
        def __init__(self, **kwargs):
            signature.bind(None, **kwargs)
            super().__init__(**kwargs)
    monkeypatch.setattr(diffusers, "StableDiffusionXLPipeline", StrictPipeline)
    monkeypatch.setattr(diffusers, "DDPMScheduler", _FakeScheduler)
    sample_grids.build_sampling_pipe(
        is_sdxl=True, vae="vae", text_encoder_one="te1", text_encoder_two="te2",
        tokenizer_one="tok1", tokenizer_two="tok2", unet="unet",
        noise_scheduler=SimpleNamespace(config={}),
    )


def test_sampling_restores_nested_modes_dtypes_and_rng_after_failure():
    import random

    import numpy as np
    import pytest
    import torch
    module = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.Dropout())
    module[1].eval()
    original = module[0].weight.detach().clone()
    rng = torch.get_rng_state()
    python_rng = random.getstate()
    numpy_rng = np.random.get_state()
    with pytest.raises(RuntimeError), sample_grids.sampling_state(module):
        assert not module.training and not module[0].training
        module.double()
        torch.rand(3)
        random.random()
        np.random.random()
        raise RuntimeError("sample failed")
    assert module.training and module[0].training and not module[1].training
    assert module[0].weight.dtype == original.dtype
    assert torch.equal(module[0].weight, original)
    assert torch.equal(torch.get_rng_state(), rng)
    assert random.getstate() == python_rng
    assert np.array_equal(np.random.get_state()[1], numpy_rng[1])
