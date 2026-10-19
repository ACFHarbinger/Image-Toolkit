"""full_bf16 / seed reach the tuner, and adamw8bit degrades without bitsandbytes."""
from types import SimpleNamespace

import pytest
import torch
from omegaconf import OmegaConf

from middleware.src.models.tuning import lo_ra_tuner_v2
from middleware.src.models.tuning.lo_ra_tuner_v2 import LoRATunerV2
from middleware.src.pipeline import anime_training_pipeline as pipeline


def _built(monkeypatch, tmp_path, training, **top):
    captured = {}
    monkeypatch.setattr(pipeline, "LoRATunerV2", lambda cfg: captured.setdefault("cfg", cfg))
    cfg = OmegaConf.create({"model": {"model_id": "fake/model"},
                            "training": {"stage": "lora", **training},
                            "output_dir": str(tmp_path), **top})
    pipeline._build_tuner(cfg)
    return captured["cfg"]


def test_full_bf16_and_seed_are_forwarded(monkeypatch, tmp_path):
    built = _built(monkeypatch, tmp_path, {"full_bf16": True}, seed=7)
    assert built.full_bf16 is True and built.seed == 7


def test_defaults_keep_fp32_and_unseeded(monkeypatch, tmp_path):
    built = _built(monkeypatch, tmp_path, {})
    assert built.full_bf16 is False and built.seed is None


def test_adamw8bit_falls_back_without_bitsandbytes(monkeypatch, caplog):
    monkeypatch.setattr(lo_ra_tuner_v2, "_BNB_OK", False)
    tuner = SimpleNamespace(
        _param_groups=[{"params": [torch.nn.Parameter(torch.zeros(2))], "lr": 1e-4}],
        cfg=SimpleNamespace(optimizer_type="adamw8bit", weight_decay=0.01),
    )
    optimizer = LoRATunerV2.build_optimizer(tuner)
    assert type(optimizer) is torch.optim.AdamW
    assert "falls back to torch AdamW" in caplog.text


def test_lion_still_requires_bitsandbytes(monkeypatch):
    monkeypatch.setattr(lo_ra_tuner_v2, "_BNB_OK", False)
    tuner = SimpleNamespace(_param_groups=[], cfg=SimpleNamespace(optimizer_type="lion", weight_decay=0.0))
    with pytest.raises(ImportError):
        LoRATunerV2.build_optimizer(tuner)
