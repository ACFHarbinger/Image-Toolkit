"""C2: devtool is canonical; debugtool re-exports the same CLI and API."""

from __future__ import annotations

import json
from pathlib import Path


def _event(t, category, name, tid=1, tname="MainThread"):
    return {
        "t": t,
        "wall": 1786567965.0 + t,
        "pid": 999,
        "tid": tid,
        "tname": tname,
        "category": category,
        "event": name,
    }


def _write_session(root: Path, pid: int, events: list) -> Path:
    path = root / f"telemetry-{pid}.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return path


def test_devtool_exports_open_session():
    import devtool

    assert callable(devtool.open_session)
    assert callable(devtool.list_sessions)
    assert devtool.open_session is not None


def test_open_session_reads_file(tmp_path):
    from devtool import open_session

    path = tmp_path / "telemetry-9.jsonl"
    path.write_text(
        '{"t": 0.0, "tid": 1, "tname": "Main", "category": "c", "event": "e"}\n'
    )
    session = open_session(path=path)
    assert session is not None
    assert len(session.events) == 1
    assert session.events[0]["event"] == "e"


def test_debugtool_main_is_devtool_main(tmp_path, capsys, monkeypatch):
    telemetry_dir = tmp_path / "tel"
    telemetry_dir.mkdir()
    _write_session(telemetry_dir, 401, [_event(0.0, "cat", "a")])

    import debugtool
    from debugtool.cli.main import main as dbg_main
    from devtool.cli.main import main as dev_main

    def fake_list_sessions(directory=None):
        return debugtool.discover_sessions(telemetry_dir)

    monkeypatch.setattr("debugtool.cli.main.list_sessions", fake_list_sessions)

    code_dev = dev_main(["list"])
    out_dev = capsys.readouterr().out
    code_dbg = dbg_main(["list"])
    out_dbg = capsys.readouterr().out
    assert code_dev == 0
    assert code_dbg == 0
    assert "telemetry-401.jsonl" in out_dev
    assert "telemetry-401.jsonl" in out_dbg


def test_devtool_analyze_matches_debugtool(tmp_path, capsys):
    from debugtool.cli.main import main as dbg_main
    from devtool.cli.main import main as dev_main

    telemetry_dir = tmp_path / "tel"
    telemetry_dir.mkdir()
    path = _write_session(telemetry_dir, 402, [_event(0.0, "cat", "only")])
    assert dev_main(["analyze", str(path)]) == 0
    out_dev = capsys.readouterr().out
    assert dbg_main(["analyze", str(path)]) == 0
    out_dbg = capsys.readouterr().out
    assert "=== telemetry-402.jsonl" in out_dev
    assert out_dev == out_dbg
