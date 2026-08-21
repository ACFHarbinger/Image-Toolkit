"""Tests for D1 runner integration (build/test/app verbs open an
attributable Session: command, cwd, env snapshot, exit status)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tool.host.runner import RunRecord, env_snapshot, run_workflow


class TestEnvSnapshot:
    def test_allowlist_only(self):
        snap = env_snapshot({"HOME": "/home/x", "SECRET_TOKEN": "hunter2", "PATH": "/usr/bin"})
        assert "HOME" in snap
        assert "PATH" in snap
        assert "SECRET_TOKEN" not in snap


class TestRunWorkflow:
    def test_success_records_attribution(self, tmp_path):
        record = run_workflow(
            "test",
            [sys.executable, "-c", "print('ok')"],
            cwd=tmp_path,
        )
        assert isinstance(record, RunRecord)
        assert record.verb == "test"
        assert record.command == [sys.executable, "-c", "print('ok')"]
        assert record.cwd == str(tmp_path)
        assert record.exit_code == 0
        assert "ok" in record.stdout
        assert "git" in record.to_dict()

    def test_failure_captures_exit_code(self, tmp_path):
        record = run_workflow(
            "build",
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            cwd=tmp_path,
        )
        assert record.exit_code == 3

    def test_telemetry_producing_run_writes_manifest(self, tmp_path):
        tel = tmp_path / "telemetry"
        tel.mkdir()
        target = tel / "telemetry-999.jsonl"
        line = json.dumps({"t": 0.0, "category": "a", "event": "e", "tid": 1})
        code = f"import pathlib; pathlib.Path({str(target)!r}).write_text({line!r})"
        record = run_workflow(
            "app",
            [sys.executable, "-c", code],
            cwd=tmp_path,
            telemetry_dir=tel,
        )
        assert record.exit_code == 0
        assert record.session_path is not None
        assert record.manifest_path is not None
        manifest = json.loads(Path(record.manifest_path).read_text())
        assert manifest["run"]["verb"] == "app"
        assert manifest["run"]["command"] == [sys.executable, "-c", code]
