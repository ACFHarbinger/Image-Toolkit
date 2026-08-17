import json
from pathlib import Path

from debugtool import Session
from devtool.cli.main import main as cli_main
from devtool.host.scenarios import get_scenario, list_scenarios
from devtool.queries.hypothesis import generate_hypothesis


def _ev(t, category, event, tid=1, tname="MainThread", **fields):
    base = {"t": t, "wall": 1786567965.0 + t, "pid": 999, "tid": tid, "tname": tname, "category": category, "event": event}
    base.update(fields)
    return base


def _write_session(path: Path, events: list) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return path


def test_hypothesis_clean_run():
    hypo = generate_hypothesis(session=None, exit_code=0)
    assert "Clean execution" in hypo


def test_hypothesis_signal_and_orphans(tmp_path):
    events = [
        _ev(0.1, "downloader", "download_batch.start", tid=1),
        _ev(0.2, "scanner", "scan_dir.start", tid=2),
    ]
    path = _write_session(tmp_path / "telemetry-555.jsonl", events)
    session = Session.open(path)
    session.truncated_final_line = True

    hypo = generate_hypothesis(
        session=session,
        exit_code=134,
        gdb_trace="Thread 1 (Thread 0x7f): #0 0x1e74d5 in QObjectPrivate::ConnectionData::deleteOrphaned",
    )
    assert "SIGABRT" in hypo
    assert "died mid-telemetry write" in hypo
    assert "downloader" in hypo or "scanner" in hypo
    assert "deleteOrphaned" in hypo


def test_hypothesis_overlaps_and_socket_notifier(tmp_path):
    events = [
        _ev(0.1, "scanner", "scan_dir.start", img_thread=101),
        _ev(0.15, "scanner", "scan_dir.start", img_thread=102),
        _ev(0.2, "scanner", "scan_dir.end", img_thread=101),
        _ev(0.25, "scanner", "scan_dir.end", img_thread=102),
    ]
    path = _write_session(tmp_path / "telemetry-777.jsonl", events)
    session = Session.open(path)

    hypo = generate_hypothesis(
        session=session,
        exit_code=139,
        gdb_trace="QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread",
    )
    assert "SIGSEGV" in hypo
    assert "Thread collision detected" in hypo
    assert "socket notifier" in hypo.lower()


def test_scenario_catalog():
    scenarios = list_scenarios()
    assert len(scenarios) >= 4
    names = [s.name for s in scenarios]
    assert "media-loader-stress" in names
    assert "telemetry-span-test" in names

    sc = get_scenario("media-loader-stress")
    assert sc is not None
    assert "downloader" in sc.tags
    assert len(sc.command) > 0


def test_cli_repro_list_scenarios(capsys):
    ret = cli_main(["repro", "--list-scenarios"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert "Available Reproduction Scenarios:" in out
    assert "media-loader-stress" in out
    assert "telemetry-span-test" in out
