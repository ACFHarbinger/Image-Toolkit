"""Tests for #409's ``list_records`` sidecar method: the sidecar adapts every
telemetry session in the workspace into ``devtool.record`` dicts (lock 9).

Kept separate from test_sidecar.py (#408, opencode's file) to avoid stepping
on that ownership; this only exercises the new method.
"""

from __future__ import annotations

import json

from tool import WorkspaceStore
from tool.sidecar import SidecarServer


def _write_session(tmp_path, pid=222):
    path = tmp_path / f"telemetry-{pid}.jsonl"
    lines = [
        {"t": 1.0, "wall": 1.0, "pid": pid, "tid": 1, "category": "app", "event": "boot.start"},
        {"t": 1.2, "wall": 1.2, "pid": pid, "tid": 1, "category": "app", "event": "boot.end"},
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def test_list_records_adapts_telemetry(tmp_path):
    _write_session(tmp_path)
    store = WorkspaceStore(root=tmp_path, telemetry_dir=tmp_path)
    server = SidecarServer(store)
    resp = json.loads(server.handle('{"jsonrpc":"2.0","id":1,"method":"list_records"}'))
    records = resp["result"]["records"]
    assert len(records) == 1
    record = records[0]
    assert record["schema"] == "devtool.record"
    assert record["kind"] == "span"
    assert record["start_ms"] == 1000.0
    assert record["end_ms"] == 1200.0
    assert record["workspace"] == str(tmp_path)


def test_list_records_empty_workspace(tmp_path):
    store = WorkspaceStore(root=tmp_path, telemetry_dir=tmp_path)
    server = SidecarServer(store)
    resp = json.loads(server.handle('{"jsonrpc":"2.0","id":2,"method":"list_records"}'))
    assert resp["result"]["records"] == []
