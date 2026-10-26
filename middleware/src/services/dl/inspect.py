"""Read a caller training-run directory (#912).

Uses ``read_run_record`` and ``iter_events`` only. This module does not
start a run, write the directory, import torch, or open library.db.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_EVENT_CAP = 1000
_HELPERS: tuple[Any, Any] | None = None


def _training_runs() -> tuple[Any, Any]:
    """Load ``read_run_record`` and ``iter_events`` without the core package.

    ``middleware.src.core``'s package init imports image and video code,
    which pulls torch and cv2 into the sidecar. The file itself does not.
    """
    global _HELPERS
    if _HELPERS is not None:
        return _HELPERS
    path = Path(__file__).resolve().parents[2] / "core" / "training_runs.py"
    name = "middleware.src.services.dl._training_runs_file"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _HELPERS = (module.read_run_record, module.iter_events)
    return _HELPERS


def inspect_run(run_dir: str) -> dict[str, Any]:
    read_run_record, _iter_events = _training_runs()
    path = Path(run_dir)
    if not path.is_dir():
        return _absent(run_dir, "run directory is missing")
    record = read_run_record(path)
    if record is None:
        return _absent(run_dir, "record.json is missing")
    return {
        "found": True,
        "run_dir": run_dir,
        "run_id": _text(record.get("run_id")),
        "status": _text(record.get("status")),
        "engine": _text(record.get("engine")),
        "model_id": _text(record.get("model_id")),
        "event_count": _event_count(_iter_events, path),
        "started": False,
        "reason": "training is not started",
    }


def _absent(run_dir: str, reason: str) -> dict[str, Any]:
    return {
        "found": False,
        "run_dir": run_dir,
        "run_id": "",
        "status": "",
        "engine": "",
        "model_id": "",
        "event_count": 0,
        "started": False,
        "reason": reason,
    }


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _event_count(iter_events: Any, run_dir: Path) -> int:
    """Count events.jsonl rows, stopping at the cap. A missing file is 0."""
    events = iter_events(run_dir)
    count = 0
    try:
        for _event in events:
            count += 1
            if count >= _EVENT_CAP:
                break
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            close()
    return count
