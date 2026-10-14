"""In-process GPU admission shared by model jobs and Comfy (#772)."""
from types import MethodType
from unittest.mock import MagicMock

import pytest
from backend.src.comfy_matrix import gpu_lease

pytestmark = pytest.mark.gui


def test_lora_training_holds_and_releases_admission(monkeypatch):
    from gui.src.tabs.models.delta import lora_train_tab as mod

    class _Gan:
        is_cancelled = False

        def train(self, **_kwargs):
            assert gpu_lease.owner == "lora-train"
            assert gpu_lease.try_acquire("matrix") is False

        def unload(self):
            pass

    monkeypatch.setattr(mod, "GanWrapper", _Gan)
    gpu_lease.release("lora-train")
    tab = MagicMock()
    tab._run_training_admitted = MethodType(mod.LoRATrainTab._run_training_admitted, tab)
    mod.LoRATrainTab.run_training(
        tab,
        params={"epochs": 1, "learning_rate": 1e-4, "batch_size": 1},
        data_dir="data",
        model_id="animegan_v2",
        rank=4,
        prompt="p",
        output_name="out",
    )
    assert gpu_lease.owner is None
    assert gpu_lease.try_acquire("after-train")
    gpu_lease.release("after-train")


def test_lora_training_supplies_a_vram_estimate(monkeypatch):
    from gui.src.tabs.models.delta import lora_train_tab as mod

    seen = {}

    def _admit(owner, lease=None, *, estimated_gb=None, kind=None):
        seen["owner"] = owner
        seen["estimated_gb"] = estimated_gb
        return None

    monkeypatch.setattr(mod, "try_admit", _admit)
    monkeypatch.setattr(mod.LoRATrainTab, "_run_training_admitted", lambda *a, **k: None)
    tab = MagicMock()
    mod.LoRATrainTab.run_training(
        tab,
        params={"epochs": 1, "learning_rate": 1e-4, "batch_size": 2},
        data_dir="data",
        model_id="stabilityai/stable-diffusion-xl-base-1.0",
        rank=16,
        prompt="p",
        output_name="out",
    )
    assert seen["owner"] == "lora-train"
    assert seen["estimated_gb"] is not None
    assert seen["estimated_gb"] > 8.0


def test_lora_training_refuses_when_admission_is_held():
    from gui.src.tabs.models.delta import lora_train_tab as mod

    tab = MagicMock()
    assert gpu_lease.try_acquire("matrix")
    try:
        mod.LoRATrainTab.run_training(
            tab,
            params={},
            data_dir="data",
            model_id="animegan_v2",
            rank=4,
            prompt="p",
            output_name="out",
        )
    finally:
        gpu_lease.release("matrix")
    status, message, run_dir = tab.training_finished_signal.emit.call_args[0]
    assert run_dir == ""
    assert status == "error"
    assert "matrix" in message
    assert gpu_lease.owner is None


def test_lora_generate_holds_admission(monkeypatch):
    from gui.src.tabs.models.gen import lora_generate_tab as mod

    def _generate(**_kwargs):
        assert gpu_lease.owner == "lora-generate"

    monkeypatch.setattr(mod.LoRATuner, "generate_anime_image", _generate)
    monkeypatch.setattr(mod.LoRATuner, "is_cancelled", False)
    monkeypatch.setattr(mod.GanWrapper, "is_cancelled", False)
    tab = MagicMock()
    mod.LoRAGenerateTab.run_generation(
        tab, "model", "out.png", 1, "p", "n", "lora", 5, 7.0, "",
    )
    assert gpu_lease.owner is None


def test_cbir_training_holds_admission_for_the_tuner(monkeypatch):
    from gui.src.tabs.models.delta.cbir_train_tab import _training_worker as mod

    class _Tuner:
        is_cancelled = False

        def __init__(self, **_kwargs):
            pass

        def train(self):
            assert gpu_lease.owner == "cbir-train"

    monkeypatch.setattr(mod, "_TRAINER_OK", True)
    monkeypatch.setattr(mod, "CBIRTuner", _Tuner)
    worker = MagicMock()
    worker._img_dir.text.return_value = "/tmp/images"
    worker.collect.return_value = {"output_dir": "/tmp/out"}
    worker._epochs.value.return_value = 1
    mod.CBIRTrainWorkerController._start_training(worker)
    worker._train_thread.join(2)
    assert gpu_lease.owner is None
    worker.sig_done.emit.assert_called()


def test_guided_comfy_holds_admission_until_execution_finishes():
    from gui.src.tabs.models.gen.comfy_generate_tab import _queue_workflow

    manager = MagicMock()
    manager.queue_workflow.return_value = "running"

    def wait(prompt_id, **kwargs):
        assert prompt_id == "running"
        assert gpu_lease.owner == "guided"
        assert not gpu_lease.try_acquire("lora-train")
        return True

    manager.wait_for_run.side_effect = wait
    _queue_workflow(manager, MagicMock(), "lora", "", "base", "lora", "p", "n")
    manager.wait_for_run.assert_called_once()
    assert gpu_lease.owner is None


def test_generation_cleanup_failure_still_releases_admission(monkeypatch, tmp_path):
    from gui.src.tabs.models.gen import lora_generate_tab as mod

    source = tmp_path / "input.png"
    source.write_bytes(b"fixture")
    gan = MagicMock()
    gan.unload.side_effect = RuntimeError("cleanup failed")
    monkeypatch.setattr(mod, "GanWrapper", MagicMock(return_value=gan))
    with pytest.raises(RuntimeError, match="cleanup failed"):
        mod.LoRAGenerateTab.run_generation(
            MagicMock(), "animegan_v2", "out.png", 1, "p", "n", "lora", 5, 7.0, str(source),
        )
    assert gpu_lease.owner is None
