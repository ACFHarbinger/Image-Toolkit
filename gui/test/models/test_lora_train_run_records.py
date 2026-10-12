"""#741: training run records + JSONL sink wired into both GUI launch paths.

LoRATuner, DiagnosticsLogger, and the LyCORIS subprocess are stubbed — no
model loads, no GPU, no real subprocess. The runs root is monkeypatched to
tmp_path. The real JSONL sink behavior is covered in the backend suite
(backend/test/models/test_diagnostics_jsonl.py); here we assert the GUI
hands the right path to the logger and the logger reaches tuner.train().
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from backend.src.core.training_runs import (
    EVENTS_FILE_NAME,
    RECORD_FILE_NAME,
    read_run_record,
)

from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab

pytestmark = pytest.mark.gui

MODULE = "gui.src.tabs.models.delta.lora_train_tab"


class _FakeDiagnostics:
    """Stands in for the mocked-away real DiagnosticsLogger in GUI tests."""

    def __init__(self, run_name="", use_tensorboard=False, use_wandb=False, jsonl_path=None):
        self.run_name = run_name
        self.jsonl_path = jsonl_path
        self.closed = False

    def log_step(self, step, epoch=None, **metrics):
        event = {"step": step}
        if epoch is not None:
            event["epoch"] = epoch
        event.update(metrics)
        with open(self.jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _runs_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ITK_TRAINING_RUNS_ROOT", str(tmp_path / "runs"))
    return tmp_path / "runs"


@pytest.fixture(autouse=True)
def _no_modal_dialogs():
    with patch(f"{MODULE}.QMessageBox"):
        yield


@pytest.fixture
def tab():
    return LoRATrainTab()


def _fake_lora_tuner():
    tuner_cls = MagicMock(name="LoRATuner")
    tuner_cls.is_cancelled = False
    tuner_cls.return_value.train.return_value = None
    return tuner_cls


def test_standard_path_creates_run_record_and_jsonl_sink(tab, _runs_root):
    captured = {}

    def fake_train(*args, **kwargs):
        captured["diagnostics"] = kwargs.get("diagnostics")
        if captured["diagnostics"] is not None:
            captured["diagnostics"].log_step(1, epoch=0, loss=0.5)

    tuner_cls = _fake_lora_tuner()
    tuner_cls.return_value.train.side_effect = fake_train
    with patch(f"{MODULE}.LoRATuner", tuner_cls), \
         patch(f"{MODULE}.DiagnosticsLogger", _FakeDiagnostics):
        tab.run_training(
            params={"epochs": 5, "batch_size": 1, "learning_rate": 1e-4},
            data_dir="/tmp/data", model_id="some/model", rank=8,
            prompt="a character", output_name="my_lora", engine="standard",
            trigger="mychar_xyz",
        )

    run_dirs = list(_runs_root.iterdir())
    assert len(run_dirs) == 1
    record = read_run_record(run_dirs[0])
    # Kimi's #733 contract keys are first-class.
    assert record["trigger_word"] == "mychar_xyz"
    assert record["negative_prompt"] == ""
    assert record["lora_path"]
    assert record["status"] == "success"
    assert record["engine"] == "standard"
    assert record["model_id"] == "some/model"
    assert record["config"]["rank"] == 8
    assert record["finished_at"]

    # The JSONL sink the trainer received is the run's events file.
    diag = captured["diagnostics"]
    assert isinstance(diag, _FakeDiagnostics)
    events_file = run_dirs[0] / EVENTS_FILE_NAME
    assert Path(diag.jsonl_path) == events_file
    assert diag.closed

    lines = [json.loads(line) for line in events_file.read_text().splitlines()]
    assert lines[0]["step"] == 1
    assert lines[0]["epoch"] == 0
    assert lines[0]["loss"] == 0.5


def test_lycoris_path_forwards_run_dir_and_finishes_record(tab, _runs_root, tmp_path):
    fake_proc = MagicMock()
    fake_proc.stdout = iter(["[LoRATunerV2] Training: 1 epochs\n"])
    fake_proc.wait.return_value = 0
    output_name = str(tmp_path / "lyco_out")
    (tmp_path / "lyco_out").mkdir()
    (tmp_path / "lyco_out" / "lora_weights.safetensors").write_bytes(b"")
    with patch(f"{MODULE}.subprocess.Popen", return_value=fake_proc) as mock_popen:
        tab.run_training(
            params={"epochs": 2, "batch_size": 1, "learning_rate": 1e-4},
            data_dir="/data", model_id="some/model", rank=4,
            prompt="mychar", output_name=output_name, engine="locon",
        )
    cmd = mock_popen.call_args.args[0]
    run_dirs = list(_runs_root.iterdir())
    assert len(run_dirs) == 1
    assert f"logging.run_dir={run_dirs[0]}" in cmd
    record = read_run_record(run_dirs[0])
    assert record["status"] == "success"
    assert record["engine"] == "locon"
    assert record["lora_path"] == str(tmp_path / "lyco_out" / "lora_weights.safetensors")


def test_lycoris_failure_records_error(tab, _runs_root):
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = 3
    with patch(f"{MODULE}.subprocess.Popen", return_value=fake_proc):
        tab.run_training(
            params={}, data_dir="/data", model_id="m", rank=4,
            prompt="p", output_name="bad", engine="loha",
        )
    run_dir = next(iter(_runs_root.iterdir()))
    record = read_run_record(run_dir)
    assert record["status"] == "error"
    assert "exited with code 3" in record["error"]


def test_record_failure_never_blocks_training(tab, _runs_root):
    tuner_cls = _fake_lora_tuner()
    with patch(f"{MODULE}.LoRATuner", tuner_cls), \
         patch(f"{MODULE}.DiagnosticsLogger", _FakeDiagnostics), \
         patch(f"{MODULE}.start_run", side_effect=OSError("disk full")):
        tab.run_training(
            params={}, data_dir="/tmp/data", model_id="some/model", rank=4,
            prompt="p", output_name="out", engine="standard",
        )
    tuner_cls.return_value.train.assert_called_once()
    assert tuner_cls.return_value.train.call_args.kwargs["diagnostics"] is None
    assert not _runs_root.exists() or not any(_runs_root.iterdir())


def test_run_record_json_is_valid_and_atomic(tab, _runs_root):
    import json

    tuner_cls = _fake_lora_tuner()
    with patch(f"{MODULE}.LoRATuner", tuner_cls):
        tab.run_training(
            params={}, data_dir="/d", model_id="m", rank=4,
            prompt="p", output_name="atomic", engine="standard",
        )
    run_dir = next(iter(_runs_root.iterdir()))
    record = json.loads((run_dir / RECORD_FILE_NAME).read_text())
    assert record["status"] == "success"
    assert not (run_dir / (RECORD_FILE_NAME + ".tmp")).exists()


def test_finish_record_failure_does_not_hide_training_success(tab):
    tuner_cls = _fake_lora_tuner()
    results = []
    tab.training_finished_signal.connect(lambda *args: results.append(args))
    with patch(f"{MODULE}.LoRATuner", tuner_cls), \
         patch(f"{MODULE}.DiagnosticsLogger", _FakeDiagnostics), \
         patch(f"{MODULE}.finish_run", side_effect=OSError("disk full")):
        tab.run_training(params={}, data_dir="data", model_id="model", rank=4,
                         prompt="p", output_name="output", engine="standard")
    assert results and results[-1][0] == "success"
