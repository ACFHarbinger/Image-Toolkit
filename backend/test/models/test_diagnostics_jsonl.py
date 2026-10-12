"""#741: DiagnosticsLogger's JSONL sink — the training-event contract.

No TensorBoard/W&B needed: the JSONL mirror is the analysis contract
(#742/#743/#745 consume it); TB/W&B stay optional sinks.
"""
import json

import pytest

from backend.src.models.hooks import DiagnosticsLogger


def write_events(tmp_path, **kwargs):
    logger = DiagnosticsLogger(
        run_name="test-run",
        use_tensorboard=False,
        use_wandb=False,
        jsonl_path=str(tmp_path / "events.jsonl"),
        **kwargs,
    )
    return logger


def test_log_step_appends_jsonl_with_epoch_and_ts(tmp_path):
    logger = write_events(tmp_path)
    logger.log_step(1, epoch=0, loss=0.5)
    logger.log_step(2, epoch=0, loss=0.4)
    logger.log_step(3, epoch=1, loss=0.3, **{"grad/total": 1.25})
    logger.close()

    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events[0] == {"step": 1, "ts": events[0]["ts"], "epoch": 0, "loss": 0.5}
    assert events[1]["step"] == 2
    assert events[2]["grad/total"] == 1.25
    assert all(isinstance(e["ts"], float) for e in events)


def test_epoch_absent_when_not_given(tmp_path):
    logger = write_events(tmp_path)
    logger.log_step(7, loss=0.2)  # full_fine_tuner-style call, no epoch
    logger.close()
    event = json.loads((tmp_path / "events.jsonl").read_text())
    assert event["step"] == 7
    assert "epoch" not in event


def test_flush_is_immediate_for_live_tailing(tmp_path):
    logger = write_events(tmp_path)
    logger.log_step(1, epoch=0, loss=0.5)
    # Readable before close(): the per-step flush is what makes the
    # QFileSystemWatcher tail see events live.
    event = json.loads((tmp_path / "events.jsonl").read_text())
    assert event["loss"] == 0.5
    logger.close()


def test_non_float_metrics_are_coerced_not_fatal(tmp_path):
    logger = write_events(tmp_path)
    import numpy as np

    logger.log_step(1, epoch=0, loss=np.float32(0.25))
    logger.close()
    event = json.loads((tmp_path / "events.jsonl").read_text())
    assert event["loss"] == pytest.approx(0.25)


def test_no_jsonl_path_keeps_legacy_behavior(tmp_path):
    logger = DiagnosticsLogger(run_name="legacy", use_tensorboard=False, use_wandb=False)
    logger.log_step(1, epoch=0, loss=0.5)
    logger.close()
    assert not (tmp_path / "events.jsonl").exists()


def test_grad_norm_reaches_jsonl(tmp_path):
    import torch

    logger = write_events(tmp_path, log_grad_every=1)
    model = torch.nn.Linear(2, 2)
    loss = model(torch.randn(1, 2)).sum()
    loss.backward()
    total = logger.log_grad_norm(model, step=1)
    logger.close()
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events
    assert events[-1]["step"] == 1
    assert events[-1]["grad/total"] == pytest.approx(total)
    assert total > 0


def test_unwritable_sink_does_not_prevent_training(tmp_path):
    parent = tmp_path / "not-a-directory"
    parent.write_text("keep")
    logger = DiagnosticsLogger(run_name="test", use_tensorboard=False, use_wandb=False,
                               jsonl_path=str(parent / "events.jsonl"))
    logger.log_step(1, loss=0.5)
    logger.close()
    assert parent.read_text() == "keep"


# ---------------------------------------------------------------------------
# #747: sample-grid persistence (the material checkpoint tournaments pair up)
# ---------------------------------------------------------------------------

def test_save_sample_writes_grid_and_event(tmp_path):
    from PIL import Image

    logger = write_events(tmp_path)
    rel = logger.save_sample(Image.new("RGB", (8, 8), "red"), step=5, epoch=2)
    logger.close()
    assert rel == "samples/step-000005.png"
    assert (tmp_path / "samples" / "step-000005.png").exists()
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events[-1]["step"] == 5
    assert events[-1]["sample"] == rel
    assert events[-1]["epoch"] == 2


def test_save_sample_epoch_absent_when_not_given(tmp_path):
    from PIL import Image

    logger = write_events(tmp_path)
    logger.save_sample(Image.new("RGB", (8, 8)), step=1)
    logger.close()
    event = json.loads((tmp_path / "events.jsonl").read_text().splitlines()[-1])
    assert "epoch" not in event


def test_save_sample_without_jsonl_is_noop(tmp_path):
    from PIL import Image

    logger = DiagnosticsLogger(run_name="legacy", use_tensorboard=False, use_wandb=False)
    assert logger.save_sample(Image.new("RGB", (8, 8)), step=1, epoch=0) is None
    logger.close()
    assert not (tmp_path / "samples").exists()


def test_save_sample_disk_error_never_raises(tmp_path, monkeypatch):
    from PIL import Image

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", boom)
    logger = write_events(tmp_path)
    assert logger.save_sample(Image.new("RGB", (8, 8)), step=1) is None
    logger.log_step(2, loss=0.1)  # the training loop keeps going
    logger.close()
    assert json.loads((tmp_path / "events.jsonl").read_text())["step"] == 2


def test_log_sample_grid_persists_fixed_prompt_grid(tmp_path):
    import torch
    from PIL import Image

    calls = {}

    class FakePipe:
        def __call__(self, **kwargs):
            calls.update(kwargs)
            return type("Out", (), {"images": [Image.new("RGB", (8, 8)) for _ in kwargs["prompt"]]})()

        def set_progress_bar_config(self, **kwargs):
            pass

    logger = write_events(tmp_path)
    gen = torch.Generator().manual_seed(1)  # injected CPU generator — no CUDA in tests
    logger.log_sample_grid(FakePipe(), ["a cat", "a dog"], 9, seed=42, epoch=1, generator=gen)
    logger.close()
    assert (tmp_path / "samples" / "step-000009.png").exists()
    assert calls["prompt"] == ["a cat", "a dog"]
    assert calls["num_inference_steps"] == 30
    assert calls["guidance_scale"] == 6.0
    assert calls["generator"] is gen  # fixed-seed determinism is the whole point
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events[-1]["sample"] == "samples/step-000009.png"
    assert events[-1]["epoch"] == 1


def test_log_sample_grid_without_run_dir_does_not_write_disk(tmp_path):
    import torch
    from PIL import Image

    class FakePipe:
        def __call__(self, **kwargs):
            return type("Out", (), {"images": [Image.new("RGB", (8, 8))]})()

    logger = DiagnosticsLogger(run_name="legacy", use_tensorboard=False, use_wandb=False)
    logger.log_sample_grid(FakePipe(), ["a cat"], 3, generator=torch.Generator().manual_seed(1))
    logger.close()
    assert not (tmp_path / "samples").exists()
