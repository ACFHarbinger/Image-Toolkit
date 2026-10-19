"""#747: both LoRA trainers emit fixed-prompt/seed sample grids at their
checkpoint points — the wiring Codex's Gate D review flagged as missing."""
from types import SimpleNamespace

import pytest
import torch

from middleware.src.models.tuning.lo_ra_tuner_v2 import LoRATunerV2


class _FakeDiagnostics:
    """Records log_sample_grid calls; can simulate a sampling failure."""

    def __init__(self, fail: bool = False):
        self._jsonl = object()  # pretends a run dir sink is attached
        self.calls: list = []
        self.fail = fail

    def log_sample_grid(self, pipe, prompts, **kwargs):
        if self.fail:
            raise RuntimeError("cuda exploded")
        self.calls.append((list(prompts), kwargs))


class _FakePipe:
    def set_progress_bar_config(self, **kwargs):
        self.progress_cfg = kwargs


def _fake_v2(**cfg_over):
    values = dict(
        sample_grids=True,
        validation_prompts=[],
        validation_seed=7,
        prediction_type="epsilon",
    )
    values.update(cfg_over)
    cfg = SimpleNamespace(**values)
    return SimpleNamespace(
        cfg=cfg,
        accelerator=SimpleNamespace(unwrap_model=lambda m: m),
        unet=torch.nn.Linear(2, 2),
        vae=object(),
        text_encoder_one=object(),
        text_encoder_two=None,
        tokenizer_one=object(),
        tokenizer_two=None,
        is_sdxl=False,
        noise_scheduler=SimpleNamespace(config={}),
    )


def _fake_v1(**over):
    base = dict(
        unet=torch.nn.Linear(2, 2).eval(),
        vae=object(),
        text_encoder_one=object(),
        tokenizer_one=object(),
        is_sdxl=False,
        noise_scheduler=SimpleNamespace(config={}),
    )
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def v2_pipe(monkeypatch):
    pipe = _FakePipe()
    monkeypatch.setattr(
        "middleware.src.models.tuning.lo_ra_tuner_v2._build_sampling_pipe",
        lambda **kwargs: pipe,
    )
    return pipe


@pytest.fixture
def v1_pipe(monkeypatch):
    pipe = _FakePipe()
    monkeypatch.setattr(
        "middleware.src.models.tuning.lo_ra_tuner._build_sampling_pipe",
        lambda **kwargs: pipe,
    )
    return pipe


# ---------------------------------------------------------------------------
# V2 — per-checkpoint grids
# ---------------------------------------------------------------------------

def test_v2_samples_with_validation_prompts_and_fixed_seed(v2_pipe):
    tuner = _fake_v2(validation_prompts=["fixed prompt one", "fixed prompt two"])
    diag = _FakeDiagnostics()
    LoRATunerV2._maybe_sample_grid(tuner, diag, step=12, epoch=3)
    assert diag.calls == [(["fixed prompt one", "fixed prompt two"], {"step": 12, "seed": 7, "epoch": 3})]
    assert v2_pipe.progress_cfg == {"disable": True}


def test_v2_falls_back_to_default_prompts(v2_pipe):
    diag = _FakeDiagnostics()
    LoRATunerV2._maybe_sample_grid(_fake_v2(), diag, step=1, epoch=0)
    prompts, _ = diag.calls[0]
    assert len(prompts) == 4
    assert all("anime style" in p for p in prompts)


def test_v2_sample_grids_opt_out(v2_pipe):
    diag = _FakeDiagnostics()
    LoRATunerV2._maybe_sample_grid(_fake_v2(sample_grids=False), diag, step=1, epoch=0)
    assert diag.calls == []


def test_v2_without_diagnostics_skips(v2_pipe):
    LoRATunerV2._maybe_sample_grid(_fake_v2(), None, step=1, epoch=0)  # no raise


def test_v2_without_run_dir_skips(v2_pipe):
    diag = _FakeDiagnostics()
    diag._jsonl = None
    LoRATunerV2._maybe_sample_grid(_fake_v2(), diag, step=1, epoch=0)
    assert diag.calls == []


def test_v2_sampling_failure_never_raises(v2_pipe):
    diag = _FakeDiagnostics(fail=True)
    tuner = _fake_v2()
    LoRATunerV2._maybe_sample_grid(tuner, diag, step=1, epoch=0)
    assert tuner.unet.training


# ---------------------------------------------------------------------------
# V1 — one final grid (no per-epoch checkpoints exist to sample)
# ---------------------------------------------------------------------------

def test_v1_samples_final_grid_with_trigger(v1_pipe):
    from middleware.src.models.tuning.lo_ra_tuner import LoRATuner

    diag = _FakeDiagnostics()
    LoRATuner._maybe_sample_grid(_fake_v1(), "zxc", diag, step=30, epoch=4)
    prompts, kwargs = diag.calls[0]
    assert all("zxc" in p for p in prompts)
    assert kwargs == {"step": 30, "seed": 42, "epoch": 4}
    assert v1_pipe.progress_cfg == {"disable": True}


def test_v1_without_run_dir_skips():
    from middleware.src.models.tuning.lo_ra_tuner import LoRATuner

    diag = _FakeDiagnostics()
    diag._jsonl = None
    LoRATuner._maybe_sample_grid(_fake_v1(), "t", diag, step=1, epoch=0)
    assert diag.calls == []


def test_v1_failure_never_raises(v1_pipe):
    from middleware.src.models.tuning.lo_ra_tuner import LoRATuner

    diag = _FakeDiagnostics(fail=True)
    LoRATuner._maybe_sample_grid(_fake_v1(), "t", diag, step=1, epoch=0)  # no raise


def test_pipeline_builds_tuner_config_without_dead_logging_kwargs(monkeypatch, tmp_path):
    """Regression: anime_training_pipeline passed use_wandb/wandb_project/
    use_tensorboard into LoRATunerConfig after #741 deleted those fields —
    a constructor TypeError that killed every ordinary pipeline run."""
    from omegaconf import OmegaConf

    from middleware.src.models.tuning.lo_ra_tuner_config import LoRATunerConfig
    from middleware.src.pipeline import anime_training_pipeline as pipeline

    captured = {}

    class FakeV2:
        def __init__(self, cfg):
            captured["cfg"] = cfg

    monkeypatch.setattr(pipeline, "LoRATunerV2", FakeV2)
    cfg = OmegaConf.create(
        {
            "model": {"model_id": "fake/model"},
            "training": {"stage": "lora", "save_every_n_epochs": 2},
            "optimizer": {"unet_lr": 2e-4},
            "output_dir": str(tmp_path),
            "validation_prompts": ["fixed prompt"],
            "logging": {"use_wandb": True, "wandb_project": "x", "use_tensorboard": True},
        }
    )
    pipeline._build_tuner(cfg)
    built = captured["cfg"]
    assert isinstance(built, LoRATunerConfig)
    assert built.save_every_n_epochs == 2
    assert built.validation_prompts == ["fixed prompt"]
    assert built.sample_grids is True
    assert built.unet_lr == pytest.approx(2e-4)


def test_v2_does_not_resample_final_at_same_checkpoint_step(v2_pipe):
    tuner, diag = _fake_v2(), _FakeDiagnostics()
    LoRATunerV2._maybe_sample_grid(tuner, diag, step=12, epoch=2)
    LoRATunerV2._maybe_sample_grid(tuner, diag, step=12, epoch=2)
    assert len(diag.calls) == 1


def test_v2_non_main_rank_does_not_write_samples(v2_pipe):
    tuner, diag = _fake_v2(), _FakeDiagnostics()
    tuner.accelerator.is_main_process = False
    LoRATunerV2._maybe_sample_grid(tuner, diag, step=12, epoch=2)
    assert diag.calls == []


def test_v1_uses_experiment_prompt_suite_and_seed(v1_pipe):
    from middleware.src.models.tuning.lo_ra_tuner import LoRATuner
    diag = _FakeDiagnostics()
    LoRATuner._maybe_sample_grid(_fake_v1(), "unused", diag, step=3, epoch=0,
                                prompts=["frozen prompt"], seed=123)
    assert diag.calls == [(["frozen prompt"], {"step": 3, "seed": 123, "epoch": 0})]


def test_hydra_sample_opt_out_and_seed_reach_tuner_config(monkeypatch):
    from pathlib import Path

    from hydra import compose, initialize_config_dir

    from middleware.src.pipeline import anime_training_pipeline as pipeline
    config_dir = Path(pipeline.__file__).resolve().parents[2] / "config"
    with initialize_config_dir(config_dir=str(config_dir), version_base=None):
        cfg = compose(config_name="base", overrides=["training.sample_grids=false", "seed=123"])
    monkeypatch.setattr(pipeline, "LoRATunerV2", lambda config: config)
    built = pipeline._build_tuner(cfg)
    assert built.sample_grids is False
    assert built.validation_seed == 123
