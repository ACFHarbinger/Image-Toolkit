"""#747: fixed sample prompts + sampling-pipe composition for checkpoint grids."""
from types import SimpleNamespace

import diffusers

from backend.src.models.tuning import sample_grids


class _FakeScheduler:
    @classmethod
    def from_config(cls, config):
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
