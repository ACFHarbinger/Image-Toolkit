import json
import threading
from pathlib import Path

import pytest

from middleware.src.core import training_experiments as ex
from middleware.src.core.training_runs import finish_run, read_run_record, start_run


@pytest.fixture
def source(tmp_path):
    data = tmp_path / "source"
    data.mkdir()
    (data / "one.png").write_bytes(b"image")
    (data / "one.txt").write_text("caption")
    run = start_run(runs_root=tmp_path / "runs", run_id="source", output_name="out",
                    engine="standard", model_id="test/model", instance_prompt="fixed prompt",
                    config={"data_dir": str(data), "rank": 4, "epochs": 2,
                            "batch_size": 1, "learning_rate": 1e-4})
    finish_run(run, "success")
    return run


def prepare(source, tmp_path):
    return ex.prepare_experiment(str(source), "learning_rate", [1e-4, 5e-5], 42, tmp_path / "experiments")


def test_snapshot_copies_captions_and_preserves_one_factor(source, tmp_path):
    folder = prepare(source, tmp_path)
    manifest = ex.read_experiment(folder)
    original = Path(read_run_record(source)["config"]["data_dir"])
    (original / "one.txt").write_text("changed")
    assert (folder / "dataset/one.txt").read_text() == "caption"
    assert manifest["split"] == {"train": ["one.png"], "validation": []}
    assert manifest["seed"] == 42
    assert manifest["prompt_suite"] == ["fixed prompt"]
    assert len(manifest["dataset"]) == 2


@pytest.mark.parametrize("field,text", [("rank", "1.2,2"), ("epochs", "0,1"),
                                        ("learning_rate", "nan,1"), ("rank", "4,4"),
                                        ("rank", "1"), ("unknown", "1,2")])
def test_rejects_bad_values(field, text):
    with pytest.raises(ValueError):
        ex.parse_values(field, text)


def test_sequential_children_share_revision_and_parent(source, tmp_path):
    folder = prepare(source, tmp_path)
    seen = []
    class Process:
        returncode = 0
        def poll(self):
            return 0
    def launch(command, **kwargs):
        assert command[1:3] == ["-m", "middleware.src.core.training_experiments"]
        record = read_run_record(command[-1])
        seen.append(record)
        return Process()
    result = ex.run_experiment(folder, threading.Event(), popen=launch, resolve_revision=lambda _: "fixed-sha")
    assert result["status"] == "success"
    assert len(seen) == 2
    assert {r["model_revision"] for r in seen} == {"fixed-sha"}
    assert len({r["parent_experiment_id"] for r in seen}) == 1
    assert len({r["config"]["output_name"] for r in seen}) == 2
    assert [r["config"]["learning_rate"] for r in seen] == [1e-4, 5e-5]
    assert all(r["config"]["rank"] == 4 for r in seen)
    with pytest.raises(ValueError, match="already started"):
        ex.run_experiment(folder, threading.Event(), popen=launch)


def test_child_failure_stops_queue(source, tmp_path):
    folder = prepare(source, tmp_path)
    class Failed:
        returncode = 2
        def poll(self):
            return 2
    result = ex.run_experiment(folder, threading.Event(), popen=lambda *a, **k: Failed(), resolve_revision=lambda _: "sha")
    assert result["status"] == "error"
    assert len(result["runs"]) == 1
    assert read_run_record(result["runs"][0]["run_dir"])["status"] == "error"


def test_cancel_waits_for_child_before_stopping_queue(source, tmp_path, monkeypatch):
    folder = prepare(source, tmp_path)
    cancelled = threading.Event()
    stopped = []
    class Active:
        returncode = None
        def poll(self):
            return self.returncode
    active = Active()
    def launch(*args, **kwargs):
        cancelled.set()
        return active
    def stop(process):
        stopped.append(process)
        process.returncode = -15
    monkeypatch.setattr(ex, "_stop", stop)
    result = ex.run_experiment(folder, cancelled, popen=launch, resolve_revision=lambda _: "sha")
    assert stopped == [active]
    assert result["status"] == "cancel"
    assert len(result["runs"]) == 1


def test_curves_align_steps_not_timestamps(source, tmp_path):
    folder = prepare(source, tmp_path)
    run = folder / "runs/a"
    run.mkdir(parents=True)
    (run / "events.jsonl").write_text('\n'.join(json.dumps(v) for v in [
        {"step": 2, "loss": 4, "ts": 1}, {"step": 1, "loss": 3, "ts": 500}]))
    manifest = ex.read_experiment(folder)
    manifest["runs"] = [{"value": 1e-4, "run_dir": str(run)}]
    ex._write(folder / "experiment.json", manifest)
    assert ex.curves(folder)[0]["points"] == [(1, 3.0), (2, 4.0)]


def test_cancelled_copy_cleans_partial_snapshot(source, tmp_path):
    root = tmp_path / "experiments"
    with pytest.raises(InterruptedError):
        ex.prepare_experiment(str(source), "rank", [2, 4], 42, root, lambda: True)
    assert list(root.iterdir()) == []


def test_snapshot_preserves_nested_images_with_same_name(source, tmp_path):
    data = Path(read_run_record(source)["config"]["data_dir"])
    (data / "nested").mkdir()
    (data / "nested/one.png").write_bytes(b"other image")
    (data / "nested/one.txt").write_text("other caption")
    folder = prepare(source, tmp_path)
    assert (folder / "dataset/nested/one.txt").read_text() == "other caption"
    assert set(ex.read_experiment(folder)["split"]["train"]) == {"one.png", "nested/one.png"}
