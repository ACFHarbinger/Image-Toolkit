"""CLI tests: list / analyze subcommands against a temp telemetry dir."""

from __future__ import annotations

from conftest import event, write_session
from tool.devtool import main


def _run_main(capsys, argv):
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out


def test_list_prints_sessions(capsys, telemetry_dir, monkeypatch):
    write_session(telemetry_dir, 301, [event(0.0, "cat", "a")])

    from tool.debug import discover_sessions

    def fake_list_sessions():
        return discover_sessions(telemetry_dir)

    monkeypatch.setattr("tool.cli.parser.list_sessions", fake_list_sessions)
    code, out = _run_main(capsys, ["list"])
    assert code == 0
    assert "telemetry-301.jsonl" in out


def test_analyze_path_prints_report(capsys, telemetry_dir):
    path = write_session(telemetry_dir, 302, [event(0.0, "cat", "only")])
    code, out = _run_main(capsys, ["analyze", str(path)])
    assert code == 0
    assert "=== telemetry-302.jsonl (1 events) ===" in out
    assert "cat/only" in out


def test_analyze_tail_prints_last_events(capsys, telemetry_dir):
    path = write_session(
        telemetry_dir, 303, [event(0.0, "cat", "one"), event(0.1, "cat", "two")]
    )
    code, out = _run_main(capsys, ["analyze", str(path), "--tail", "1"])
    assert code == 0
    assert "cat/two" in out
    assert "cat/one" not in out
