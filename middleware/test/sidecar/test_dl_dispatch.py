"""dl.inspect reaches the read-only service through the sidecar dispatcher."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready() -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "dl" in handshake["result"]["capabilities"]
    return server


def test_inspect_dispatch_counts_events_without_writing(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "record.json").write_text(
        json.dumps({"run_id": "r1", "status": "running", "engine": "lora", "model_id": "sdxl"}),
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text('{"step": 1}\n{"step": 2}\n{"step":\n', encoding="utf-8")
    before = sorted((child.name, child.read_bytes()) for child in run.iterdir())
    response = _request(_ready(), "dl.inspect", {"run_dir": str(run)}, "inspect")
    result = response["result"]
    assert result["found"] is True
    assert result["run_id"] == "r1"
    assert result["event_count"] == 2
    assert result["started"] is False
    assert result["reason"] == "training is not started"
    assert sorted((child.name, child.read_bytes()) for child in run.iterdir()) == before


def test_missing_directory_is_a_validated_inspect_result(tmp_path: Path) -> None:
    target = tmp_path / "absent"
    response = _request(_ready(), "dl.inspect", {"run_dir": str(target)}, "inspect")
    result = response["result"]
    assert result["found"] is False
    assert result["reason"] == "run directory is missing"
    assert result["started"] is False
    assert result["event_count"] == 0
    assert not target.exists()
