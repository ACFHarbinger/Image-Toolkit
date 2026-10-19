"""One-factor training experiments with immutable inputs and sequential children."""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from middleware.src.core.training_curve import loss_series
from middleware.src.core.training_runs import (
    finish_run,
    iter_events,
    new_run_id,
    read_run_record,
    start_run,
    write_run_record,
)

FIELDS = {"learning_rate": (float, 1e-8, 1.0), "rank": (int, 1, 256),
          "batch_size": (int, 1, 32), "epochs": (int, 1, 100)}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def parse_values(field: str, text: str) -> list[int | float]:
    if field not in FIELDS:
        raise ValueError("Choose a supported training field")
    cast, low, high = FIELDS[field]
    try:
        values = [cast(part.strip()) for part in text.split(",")]
    except ValueError as exc:
        raise ValueError("Enter comma-separated numeric values") from exc
    if not 2 <= len(values) <= 6 or len(set(values)) != len(values):
        raise ValueError("Choose 2–6 distinct values")
    if any(not math.isfinite(v) or not low <= v <= high for v in values):
        raise ValueError(f"Values must be between {low:g} and {high:g}")
    return values


def source_details(run_dir: str | Path) -> dict:
    record = read_run_record(run_dir)
    if not record or record.get("status") != "success":
        raise ValueError("Choose a completed successful training run")
    if record.get("engine", "standard") != "standard" or record.get("model_id") == "animegan_v2":
        raise ValueError("Experiments currently support standard diffusion LoRA runs")
    data = str(record.get("config", {}).get("data_dir") or "")
    if not data or not Path(data).is_dir():
        raise ValueError("The source dataset is unavailable. Restore it before creating an experiment.")
    paths = sorted(p for p in Path(data).rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        raise ValueError("The source dataset contains no supported images")
    return {"record": record, "paths": paths,
            "bytes": sum(p.stat().st_size + (p.with_suffix('.txt').stat().st_size if p.with_suffix('.txt').is_file() else 0) for p in paths)}


def estimate(details: dict, field: str, values: list) -> str:
    cfg = details["record"]["config"]
    count = len(details["paths"])
    steps = sum(math.ceil(count / (v if field == "batch_size" else int(cfg.get("batch_size", 1)))) *
                (v if field == "epochs" else int(cfg.get("epochs", 5))) for v in values)
    return (f"{len(values)} sequential runs · {count} training images · approximately {steps} optimizer steps. "
            f"Dataset copy: {details['bytes'] / 2**20:.1f} MiB, plus {len(values)} adapter outputs. "
            "One base-model load per run; GPU memory depends on model, rank and batch size. "
            "Final preview sampling adds 30 denoising steps per prompt per run. "
            "Wall time is unknown. Training loss is not a held-out quality score.")


def _write(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_experiment(source: str, field: str, values: list, seed: int, root: Path,
                       cancelled=lambda: False) -> Path:
    values = parse_values(field, ",".join(map(str, values)))
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be in [0, 4294967295]")
    details = source_details(source)
    record = details["record"]
    experiment_id = new_run_id("experiment")
    folder = root / experiment_id
    folder.mkdir(parents=True, exist_ok=False)
    dataset = folder / "dataset"
    dataset.mkdir()
    files = []
    source_root = Path(record["config"]["data_dir"])
    try:
        for image in details["paths"]:
            for path in (image, image.with_suffix(".txt")):
                if not path.is_file():
                    continue
                if cancelled():
                    raise InterruptedError("Experiment cancelled while copying inputs")
                relative = path.relative_to(source_root)
                destination = dataset / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                files.append({"name": str(relative), "sha256": _digest(destination)})
        config = dict(record["config"])
        config["data_dir"] = str(dataset)
        manifest = {
            "version": 1, "experiment_id": experiment_id, "source_run": str(Path(source).resolve()),
            "field": field, "values": values, "seed": seed, "status": "prepared", "runs": [],
            "model_id": record["model_id"], "model_revision": record.get("model_revision"),
            "instance_prompt": record.get("instance_prompt", ""),
            "prompt_suite": record.get("prompt_suite", [record.get("instance_prompt", "")]),
            "trigger_word": record.get("trigger_word", ""), "config": config,
            "dataset": files, "split": {"train": [str(p.relative_to(source_root)) for p in details["paths"]], "validation": []},
            "estimate": estimate(details, field, values),
        }
        _write(folder / "experiment.json", manifest)
    except BaseException:
        shutil.rmtree(folder)
        raise
    return folder


def read_experiment(folder: Path) -> dict:
    return json.loads((folder / "experiment.json").read_text(encoding="utf-8"))


def curves(folder: Path) -> list[dict]:
    manifest = read_experiment(folder)
    return [{"value": r["value"], "status": (read_run_record(r["run_dir"]) or {}).get("status", "pending"),
             "points": loss_series(iter_events(r["run_dir"]))} for r in manifest["runs"]]


def _freeze_model(manifest, resolve_revision):
    model = Path(manifest["model_id"]).expanduser()
    if model.is_dir():
        manifest["model_id"] = str(model.resolve())
        manifest["model_files"] = {str(p.relative_to(model)): _digest(p) for p in sorted(model.rglob('*')) if p.is_file()}
    elif not manifest["model_revision"]:
        if resolve_revision is None:
            from huggingface_hub import HfApi
            def resolve_revision(name):
                return HfApi().model_info(name).sha
        manifest["model_revision"] = resolve_revision(manifest["model_id"])
        if not manifest["model_revision"]:
            raise ValueError("Cannot freeze the base-model revision")


def run_experiment(folder: Path, cancelled: threading.Event, progress=lambda value: None,
                   popen=subprocess.Popen, resolve_revision=None) -> dict:
    """Caller holds the app GPU lease. No child survives cancellation or an error."""
    manifest = read_experiment(folder)
    if manifest["status"] != "prepared":
        raise ValueError("This experiment has already started; create a new experiment to rerun it")
    manifest["status"] = "running"
    path = folder / "experiment.json"
    _write(path, manifest)
    try:
        _freeze_model(manifest, resolve_revision)
        _write(path, manifest)
        for index, value in enumerate(manifest["values"]):
            if cancelled.is_set():
                break
            config = dict(manifest["config"])
            config[manifest["field"]] = value
            config["output_name"] = str(folder / f"output-{index + 1}")
            run_dir = start_run(runs_root=folder / "runs", run_id=f"run-{index + 1}",
                                output_name=config["output_name"], engine="standard", model_id=manifest["model_id"],
                                instance_prompt=manifest["instance_prompt"], trigger_word=manifest["trigger_word"], config=config)
            record = read_run_record(run_dir)
            record.update(parent_experiment_id=manifest["experiment_id"], seed=manifest["seed"],
                          model_revision=manifest["model_revision"], prompt_suite=manifest["prompt_suite"],
                          varied_field=manifest["field"], varied_value=value)
            write_run_record(run_dir, record)
            manifest["runs"].append({"value": value, "run_dir": str(run_dir)})
            _write(path, manifest)
            progress(str(folder))
            process = None
            try:
                with (run_dir / "process.log").open("w") as log:
                    process = popen([sys.executable, "-m", __name__, str(folder), str(run_dir)],
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                    cwd=str(Path(__file__).resolve().parents[3]))
                    ticks = 0
                    while process.poll() is None:
                        ticks += 1
                        if ticks % 8 == 0:
                            progress(str(folder))
                        if cancelled.wait(0.25):
                            _stop(process)
                            break
                status = "cancel" if cancelled.is_set() else ("success" if process.returncode == 0 else "error")
                finish_run(run_dir, status, lora_path=config["output_name"],
                           error="Child process failed; see process.log" if status == "error" else None)
                progress(str(folder))
                if status != "success":
                    manifest["status"] = status
                    break
            except BaseException:
                if process is not None and process.poll() is None:
                    _stop(process)
                finish_run(run_dir, "error", error="Experiment runner failed")
                raise
        else:
            manifest["status"] = "success"
        if cancelled.is_set():
            manifest["status"] = "cancel"
    except Exception as exc:
        manifest["status"] = "error"
        manifest["error"] = str(exc)
        raise
    finally:
        _write(path, manifest)
    return manifest


def _stop(process) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def train_child(folder: Path, run_dir: Path) -> None:
    manifest = read_experiment(folder)
    record = read_run_record(run_dir)
    config = record["config"]
    for item in manifest["dataset"]:
        if _digest(Path(config["data_dir"]) / item["name"]) != item["sha256"]:
            raise ValueError("Frozen dataset changed")
    for name, digest in manifest.get("model_files", {}).items():
        if _digest(Path(manifest["model_id"]) / name) != digest:
            raise ValueError("Frozen base model changed")
    from accelerate.utils import set_seed

    from middleware.src.models.hooks.training_hooks import DiagnosticsLogger
    from middleware.src.models.tuning.lo_ra_tuner import LoRATuner
    set_seed(manifest["seed"])
    tuner = LoRATuner(model_id=manifest["model_id"], model_revision=manifest["model_revision"],
                      output_dir=config["output_name"])
    tuner.configure_lora(rank=int(config["rank"]))
    diagnostics = DiagnosticsLogger(run_name=run_dir.name, use_tensorboard=False, use_wandb=False,
                                    jsonl_path=str(run_dir / "events.jsonl"))
    try:
        tuner.train(data_dir=config["data_dir"], instance_prompt=manifest["instance_prompt"],
                    epochs=int(config["epochs"]), batch_size=int(config["batch_size"]),
                    learning_rate=float(config["learning_rate"]), diagnostics=diagnostics,
                    sample_prompts=manifest["prompt_suite"], sample_seed=manifest["seed"])
    finally:
        diagnostics.close()


if __name__ == "__main__":
    train_child(Path(sys.argv[1]), Path(sys.argv[2]))
