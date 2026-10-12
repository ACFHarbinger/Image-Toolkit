"""Training run records + JSONL event sink layout (#741).

Run layout (the Gate D contract, also read by Kimi's ``RunRecordStore``
in ``gui/src/components/prompt_vocabulary.py``):

    <IMAGE_TOOLKIT_DIR>/training_runs/<YYYYMMDD-HHMMSS-<output_name>>/
        record.json     identity + effective config + status
        events.jsonl    one line per training step, appended by
                        ``DiagnosticsLogger`` and flushed per step

Training *outputs* keep going wherever their ``output_dir`` points;
``record.json`` only records the path via ``lora_path``. Nothing here
imports torch — the writer is pure so GUI tests can use it freely.

``negative_prompt`` is written as ``""`` for training runs: training has
no negative prompt; the key exists because the PromptEdit vocabulary's
generation-time negative default grows into it.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

from backend.src.constants import paths as _paths

RUNS_ROOT_ENV = "ITK_TRAINING_RUNS_ROOT"
RUNS_DIR_NAME = "training_runs"
EVENTS_FILE_NAME = "events.jsonl"
RECORD_FILE_NAME = "record.json"

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_CANCEL = "cancel"
STATUS_ERROR = "error"


def default_runs_root() -> Path:
    """Runs root: env override first (portable installs, tests), then the
    app config root. Read at call time so tests that monkeypatch
    ``paths.IMAGE_TOOLKIT_DIR`` stay isolated from the real home."""
    env = os.environ.get(RUNS_ROOT_ENV, "")
    if env:
        return Path(env)
    return Path(_paths.IMAGE_TOOLKIT_DIR) / RUNS_DIR_NAME


def new_run_id(output_name: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", (output_name or "").strip()).strip("-")
    return f"{now:%Y%m%d-%H%M%S}-{safe or 'lora'}-{uuid.uuid4().hex[:8]}"


def create_run_dir(runs_root: Path, run_id: str) -> Path:
    run_dir = Path(runs_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def events_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / EVENTS_FILE_NAME


def start_run(
    *,
    runs_root: Path | str,
    run_id: str,
    output_name: str,
    engine: str,
    model_id: str,
    trigger_word: str = "",
    negative_prompt: str = "",
    instance_prompt: str = "",
    lora_path: str = "",
    config: dict | None = None,
    now: float | None = None,
) -> Path:
    """Create the run dir and write its record with status running.

    Kimi's ``record.json`` keys (trigger_word / negative_prompt /
    lora_path) are first-class; the rest is the effective config the
    analysis tools (#742-#747) read back.
    """
    run_dir = create_run_dir(runs_root, run_id)
    record = {
        "run_id": run_id,
        "trigger_word": trigger_word,
        "negative_prompt": negative_prompt,
        "lora_path": lora_path,
        "engine": engine,
        "model_id": model_id,
        "instance_prompt": instance_prompt,
        "config": config or {},
        "output_name": output_name,
        "events_file": EVENTS_FILE_NAME,
        "status": STATUS_RUNNING,
        "started_at": _timestamp(now),
        "finished_at": None,
        "error": None,
    }
    write_run_record(run_dir, record)
    return run_dir


def finish_run(
    run_dir: Path | str,
    status: str,
    *,
    lora_path: str | None = None,
    error: str | None = None,
    now: float | None = None,
) -> dict:
    """Move a run record to a terminal status (idempotent on already
    terminal records — the first terminal state wins)."""
    record = read_run_record(run_dir)
    if record is None:
        return {}
    if record.get("status") not in (None, STATUS_RUNNING):
        return record
    record["status"] = status
    if lora_path:
        record["lora_path"] = lora_path
    if error:
        record["error"] = str(error)[:500]
    record["finished_at"] = _timestamp(now)
    write_run_record(run_dir, record)
    return record


def read_run_record(run_dir: Path | str) -> dict | None:
    path = Path(run_dir) / RECORD_FILE_NAME
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def iter_events(run_dir: Path | str):
    """Yield parsed event dicts from a run's events.jsonl (missing file,
    torn tail lines, and non-dict entries are skipped, never raised)."""
    path = events_path(run_dir)
    if not path.is_file():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn tail line from a live append
            if isinstance(event, dict):
                yield event


def write_run_record(run_dir: Path | str, record: dict) -> None:
    """Atomic write: tmp file + replace, so readers never see a torn JSON."""
    run_dir = Path(run_dir)
    path = run_dir / RECORD_FILE_NAME
    tmp = run_dir / f"{RECORD_FILE_NAME}.tmp"
    tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _timestamp(now: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if now is None else now).isoformat(timespec="seconds")


__all__ = [
    "EVENTS_FILE_NAME",
    "RECORD_FILE_NAME",
    "RUNS_DIR_NAME",
    "RUNS_ROOT_ENV",
    "STATUS_CANCEL",
    "STATUS_ERROR",
    "STATUS_RUNNING",
    "STATUS_SUCCESS",
    "create_run_dir",
    "default_runs_root",
    "events_path",
    "finish_run",
    "iter_events",
    "new_run_id",
    "read_run_record",
    "start_run",
    "write_run_record",
]
