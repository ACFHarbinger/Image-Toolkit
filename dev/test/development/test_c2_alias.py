"""C2/debug-fold: tool is canonical; tool.debug keeps the debugtool API surface.

Historical note: before the 2026-08-17 debug/dev fold, C2 made ``tool``
canonical while ``python -m debugtool`` re-exported the same CLI as a
separate top-level package. That CLI-level alias is retired now that
``debug/`` no longer exists as its own directory — the CLI is exclusively
``python dev/`` (see dev/__main__.py). What survives is the import-level
compatibility surface: ``tool.debug`` still re-exports the original
``debugtool`` public API (``open_session``, ``list_sessions``,
``render_session_view``, ``run_tui``), so old import statements only need
``debugtool`` -> ``tool.debug``, not a full rewrite.
"""

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


def test_tool_exports_open_session():
    import tool

    assert callable(tool.open_session)
    assert callable(tool.list_sessions)
    assert tool.open_session is not None


def test_open_session_reads_file(tmp_path):
    from tool import open_session

    path = tmp_path / "telemetry-9.jsonl"
    path.write_text(
        '{"t": 0.0, "tid": 1, "tname": "Main", "category": "c", "event": "e"}\n'
    )
    session = open_session(path=path)
    assert session is not None
    assert len(session.events) == 1
    assert session.events[0]["event"] == "e"


def test_tool_debug_open_session_matches_tool_open_session(tmp_path):
    """tool.debug's re-exported open_session is the same Session model tool uses."""
    from tool import open_session as tool_open_session
    from tool.debug import open_session as debug_open_session

    path = tmp_path / "telemetry-401.jsonl"
    _write_session(path.parent, 401, [_event(0.0, "cat", "a")])
    path = path.parent / "telemetry-401.jsonl"

    session_a = tool_open_session(path=path)
    session_b = debug_open_session(path=path)
    assert session_a is not None and session_b is not None
    assert session_a.events == session_b.events
    assert type(session_a) is type(session_b)


def test_tool_devtool_main_analyze(tmp_path, capsys):
    from tool.devtool import main

    telemetry_dir = tmp_path / "tel"
    telemetry_dir.mkdir()
    path = _write_session(telemetry_dir, 402, [_event(0.0, "cat", "only")])
    assert main(["analyze", str(path)]) == 0
    out = capsys.readouterr().out
    assert "=== telemetry-402.jsonl" in out
    assert "cat/only" in out
