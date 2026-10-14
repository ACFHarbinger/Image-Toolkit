"""#756: run_checkpoint_gauge orchestration on a stub tuner (CPU, no diffusers)."""
import contextlib
from types import SimpleNamespace

import pytest
import torch
import torch.nn as nn

from backend.src.models.hooks.hessian_trace import run_checkpoint_gauge


class _TinyUNet(nn.Module):
    def __init__(self, fail=False):
        super().__init__()
        self.proj = nn.Linear(4, 4)
        self.frozen = nn.Linear(4, 4)
        self.frozen.requires_grad_(False)
        self.fail = fail

    def forward(self, noisy, timesteps, encoder_hidden_states, added_cond_kwargs=None):
        if self.fail:
            raise RuntimeError("CUDA out of memory (simulated)")
        out = torch.tanh(self.proj(self.frozen(noisy))) + 0 * encoder_hidden_states.sum()
        return SimpleNamespace(sample=out)


class _Diagnostics:
    def __init__(self):
        self.steps = []

    def log_step(self, step, **fields):
        self.steps.append((step, fields))


def _tuner(hessian_vectors=3, fail=False):
    unet = _TinyUNet(fail=fail)
    return SimpleNamespace(
        cfg=SimpleNamespace(hessian_vectors=hessian_vectors, validation_seed=7, prediction_type="epsilon"),
        accelerator=SimpleNamespace(
            device="cpu", is_main_process=True,
            unwrap_model=lambda m: m, autocast=contextlib.nullcontext,
        ),
        noise_scheduler=SimpleNamespace(
            config=SimpleNamespace(num_train_timesteps=1000),
            add_noise=lambda x, n, t: x + 0.1 * n,
        ),
        unet=unet,
        compute_loss=lambda pred, target, t: ((pred - target) ** 2).mean(),
        _frozen_eval=None,
    )


def _batch():
    torch.manual_seed(0)
    return torch.randn(2, 4), torch.randn(2, 4)


def test_gauge_logs_trace_and_freezes_batch_once():
    tuner, diag = _tuner(), _Diagnostics()
    latents, ehs = _batch()
    run_checkpoint_gauge(tuner, diag, 6, 0, latents, ehs, None)
    frozen = tuner._frozen_eval
    run_checkpoint_gauge(tuner, diag, 12, 1, latents + 1.0, ehs, None)
    assert tuner._frozen_eval is frozen  # later checkpoints reuse the first batch
    assert [s for s, _ in diag.steps] == [6, 12]
    step, fields = diag.steps[0]
    assert fields["epoch"] == 0
    assert torch.isfinite(torch.tensor(fields["hessian/trace"]))
    trainable = sum(p.numel() for p in tuner.unet.parameters() if p.requires_grad)
    assert fields["hessian/trace"] / fields["hessian/param"] == pytest.approx(trainable)
    assert diag.steps[0][1]["hessian/trace"] == pytest.approx(diag.steps[1][1]["hessian/trace"])
    assert all(p.grad is None for p in tuner.unet.parameters())


@pytest.mark.parametrize("hessian_vectors, diagnostics, latents", [
    (0, _Diagnostics(), torch.zeros(1, 4)),
    (3, None, torch.zeros(1, 4)),
    (3, _Diagnostics(), None),
])
def test_gauge_is_off_without_vectors_diagnostics_or_batch(hessian_vectors, diagnostics, latents):
    tuner = _tuner(hessian_vectors)
    run_checkpoint_gauge(tuner, diagnostics, 1, 0, latents, torch.zeros(1, 4), None)
    assert tuner._frozen_eval is None
    assert diagnostics is None or diagnostics.steps == []


def test_gauge_failure_is_soft(caplog):
    tuner, diag = _tuner(fail=True), _Diagnostics()
    latents, ehs = _batch()
    run_checkpoint_gauge(tuner, diag, 3, 0, latents, ehs, None)
    assert diag.steps == []
    assert "Hessian trace failed at step 3" in caplog.text
