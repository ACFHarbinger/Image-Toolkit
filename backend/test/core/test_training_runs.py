"""#741: training run-record layout, statuses, and event reading (pure, no torch)."""
import json
from datetime import datetime
from pathlib import Path

from backend.src.core import training_runs
from backend.src.core.training_runs import (
    EVENTS_FILE_NAME,
    RECORD_FILE_NAME,
    STATUS_CANCEL,
    STATUS_ERROR,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    default_runs_root,
    finish_run,
    iter_events,
    new_run_id,
    read_run_record,
    start_run,
)


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(training_runs.RUNS_ROOT_ENV, str(tmp_path))
    assert default_runs_root() == tmp_path


def test_default_root_reads_image_toolkit_dir_at_call_time(monkeypatch, tmp_path):
    monkeypatch.delenv(training_runs.RUNS_ROOT_ENV, raising=False)
    from backend.src.constants import paths

    monkeypatch.setattr(paths, "IMAGE_TOOLKIT_DIR", tmp_path)
    assert default_runs_root() == tmp_path / training_runs.RUNS_DIR_NAME


def test_new_run_id_sanitizes_and_stamps():
    run_id = new_run_id("My Char/Lora! v2", now=datetime(2026, 10, 12, 13, 14, 15))
    assert run_id.startswith("20261012-131415-My-Char-Lora-v2-")
    assert new_run_id("", now=datetime(2026, 10, 12)).startswith("20261012-000000-lora-")


def test_start_run_writes_kimi_contract_keys(tmp_path):
    run_dir = start_run(
        runs_root=tmp_path,
        run_id="20261012-131415-my_lora",
        output_name="my_lora",
        engine="locon",
        model_id="some/model",
        trigger_word="mychar_xyz",
        instance_prompt="mychar_xyz, 1girl",
        config={"rank": 16, "epochs": 15},
    )
    record = read_run_record(run_dir)
    assert record["run_id"] == "20261012-131415-my_lora"
    assert record["trigger_word"] == "mychar_xyz"
    assert record["negative_prompt"] == ""
    assert record["lora_path"] == ""
    assert record["engine"] == "locon"
    assert record["model_id"] == "some/model"
    assert record["config"]["rank"] == 16
    assert record["status"] == STATUS_RUNNING
    assert record["started_at"]
    assert record["finished_at"] is None
    assert record["events_file"] == EVENTS_FILE_NAME
    assert not (run_dir / (RECORD_FILE_NAME + ".tmp")).exists()


def test_finish_run_is_first_terminal_wins(tmp_path):
    run_dir = start_run(
        runs_root=tmp_path, run_id="r1", output_name="out",
        engine="standard", model_id="m",
    )
    record = finish_run(run_dir, STATUS_SUCCESS, lora_path="/x/lora_weights.safetensors")
    assert record["status"] == STATUS_SUCCESS
    assert record["lora_path"] == "/x/lora_weights.safetensors"
    assert record["finished_at"]
    # A late cancel after success must not rewrite history.
    again = finish_run(run_dir, STATUS_CANCEL)
    assert again["status"] == STATUS_SUCCESS


def test_finish_run_error_truncates_message(tmp_path):
    run_dir = start_run(
        runs_root=tmp_path, run_id="r2", output_name="out",
        engine="standard", model_id="m",
    )
    record = finish_run(run_dir, STATUS_ERROR, error="x" * 2000)
    assert record["status"] == STATUS_ERROR
    assert len(record["error"]) == 500


def test_read_run_record_tolerates_garbage(tmp_path):
    assert read_run_record(tmp_path) is None
    (tmp_path / RECORD_FILE_NAME).write_text("{not json")
    assert read_run_record(tmp_path) is None
    (tmp_path / RECORD_FILE_NAME).write_text("[1, 2]")
    assert read_run_record(tmp_path) is None


def test_iter_events_skips_torn_lines_and_missing_file(tmp_path):
    assert list(iter_events(tmp_path)) == []
    events_file = tmp_path / EVENTS_FILE_NAME
    events_file.write_text(
        json.dumps({"step": 1, "loss": 0.5}) + "\n"
        '{"step": 2, "loss": 0.4}\n'  # still valid without ts
        '{"step": 3, "loss": 0.'  # torn tail from a live append
    )
    events = list(iter_events(tmp_path))
    assert [e["step"] for e in events] == [1, 2]
    assert isinstance(events[0], dict)


def test_record_and_events_layout_matches_promptedit_contract(tmp_path):
    """Kimi's RunRecordStore globs <base>/*/record.json; the layout must fit."""
    run_dir = start_run(
        runs_root=tmp_path, run_id="20261012-131415-x", output_name="x",
        engine="standard", model_id="m", trigger_word="tok",
    )
    (run_dir / EVENTS_FILE_NAME).write_text('{"step": 1, "loss": 0.1}\n')
    found = list(Path(tmp_path).glob("*/record.json"))
    assert len(found) == 1
    record = json.loads(found[0].read_text())
    assert record["trigger_word"] == "tok"


def test_repeated_runs_have_distinct_ids_and_cannot_overwrite(tmp_path):
    import pytest

    now = datetime(2026, 10, 12)
    assert new_run_id("same", now) != new_run_id("same", now)
    args = dict(runs_root=tmp_path, run_id="same", output_name="x", engine="standard", model_id="m")
    run = start_run(**args)
    finish_run(run, STATUS_SUCCESS)
    with pytest.raises(FileExistsError):
        start_run(**args)
    assert read_run_record(run)["status"] == STATUS_SUCCESS


def test_hydra_accepts_gui_run_directory_override(tmp_path):
    from hydra import compose, initialize_config_dir

    config_dir = str(Path(__file__).resolve().parents[2] / "config")
    with initialize_config_dir(config_dir=config_dir, version_base="1.3"):
        config = compose(config_name="base", overrides=[f"logging.run_dir={tmp_path}"])
    assert config.logging.run_dir == str(tmp_path)
