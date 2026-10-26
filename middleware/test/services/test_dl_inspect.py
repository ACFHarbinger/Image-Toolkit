"""dl.inspect reads a caller run directory and does not write it (#912)."""

from __future__ import annotations

import json
from pathlib import Path

from middleware.src.services.dl.inspect import inspect_run


def _snapshot(path: Path) -> dict[str, bytes]:
    return {child.name: child.read_bytes() for child in path.iterdir()}


def test_missing_directory_is_not_created(tmp_path: Path) -> None:
    target = tmp_path / "absent"
    result = inspect_run(str(target))
    assert result == {
        "found": False,
        "run_dir": str(target),
        "run_id": "",
        "status": "",
        "engine": "",
        "model_id": "",
        "event_count": 0,
        "started": False,
        "reason": "run directory is missing",
    }
    assert not target.exists()


def test_missing_or_invalid_record(tmp_path: Path) -> None:
    missing = tmp_path / "no-record"
    missing.mkdir()
    before = _snapshot(missing)
    result = inspect_run(str(missing))
    assert result["found"] is False
    assert result["reason"] == "record.json is missing"
    assert result["started"] is False
    assert result["event_count"] == 0
    assert _snapshot(missing) == before

    invalid = tmp_path / "bad-record"
    invalid.mkdir()
    (invalid / "record.json").write_text("{not json", encoding="utf-8")
    before = _snapshot(invalid)
    result = inspect_run(str(invalid))
    assert result["found"] is False
    assert result["reason"] == "record.json is missing"
    assert result["started"] is False
    assert _snapshot(invalid) == before


def test_record_counts_events_and_skips_a_torn_line(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    run.mkdir()
    (run / "record.json").write_text(
        json.dumps({"run_id": "run-1", "status": "running", "engine": "lora", "model_id": "sdxl"}),
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text('{"step": 1}\n{"step": 2}\n{"step":\n', encoding="utf-8")
    before = _snapshot(run)
    result = inspect_run(str(run))
    assert result == {
        "found": True,
        "run_dir": str(run),
        "run_id": "run-1",
        "status": "running",
        "engine": "lora",
        "model_id": "sdxl",
        "event_count": 2,
        "started": False,
        "reason": "training is not started",
    }
    assert _snapshot(run) == before


def test_missing_events_file_counts_zero(tmp_path: Path) -> None:
    run = tmp_path / "quiet"
    run.mkdir()
    (run / "record.json").write_text(json.dumps({"run_id": "quiet"}), encoding="utf-8")
    before = _snapshot(run)
    result = inspect_run(str(run))
    assert result["found"] is True
    assert result["event_count"] == 0
    assert result["status"] == ""
    assert result["engine"] == ""
    assert result["model_id"] == ""
    assert result["started"] is False
    assert _snapshot(run) == before


def test_event_count_stops_at_one_thousand(tmp_path: Path) -> None:
    run = tmp_path / "long"
    run.mkdir()
    (run / "record.json").write_text(json.dumps({"run_id": "long", "status": "running"}), encoding="utf-8")
    lines = ['{"step": %d}\n' % index for index in range(1001)]
    (run / "events.jsonl").write_text("".join(lines), encoding="utf-8")
    before = _snapshot(run)
    result = inspect_run(str(run))
    assert result["event_count"] == 1000
    assert result["started"] is False
    assert _snapshot(run) == before
