from __future__ import annotations

import io

import pytest
from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.drive_sync.plan import plan_sync
from middleware.src.sidecar.server import SidecarServer


def test_plan_is_not_submitted() -> None:
    result = plan_sync("google_drive", ["a.png", " b.png "])
    assert result == {
        "submitted": False,
        "provider": "google_drive",
        "count": 2,
        "reason": "sync is not sent",
    }


def test_plan_rejects_empty_unknown_and_oversized_lists() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        plan_sync("box", ["a.png"])
    with pytest.raises(ValueError, match="1 to 32"):
        plan_sync("dropbox", [])
    with pytest.raises(ValueError, match="empty"):
        plan_sync("onedrive", ["  "])
    with pytest.raises(ValueError, match="1 to 32"):
        plan_sync("onedrive", [str(index) for index in range(33)])


def test_execute_drive_sync_success(tmp_path) -> None:
    from middleware.src.services.drive_sync.sync import execute_drive_sync
    from middleware.src.sidecar.handlers.drive_sync import handle_drive_sync

    file1 = tmp_path / "file1.png"
    file2 = tmp_path / "file2.png"
    file1.write_bytes(b"123")
    file2.write_bytes(b"456")

    class FakeVault:
        def is_unlocked(self) -> bool:
            return True

    result = execute_drive_sync("google_drive", [str(file1), str(file2)], vault_session=FakeVault())
    assert result["success"] is False
    assert result["synced_count"] == 0
    assert "provider upload is unavailable" in result["errors"]

    seen: dict[str, object] = {}

    def syncer(provider: str, paths: list[str], *, remote_folder: str, dry_run: bool) -> int:
        seen["provider"] = provider
        seen["paths"] = paths
        seen["remote_folder"] = remote_folder
        seen["dry_run"] = dry_run
        return len(paths)

    uploaded = execute_drive_sync(
        "google_drive",
        [str(file1), str(file2)],
        remote_folder="Album",
        vault_session=FakeVault(),
        syncer=syncer,
    )
    assert uploaded["success"] is True
    assert uploaded["synced_count"] == 2
    assert seen["remote_folder"] == "Album"

    # Handler test
    handler_result = handle_drive_sync({
        "provider": "dropbox",
        "paths": [str(file1)],
        "dry_run": True,
    })
    assert handler_result["success"] is True
    assert handler_result["synced_count"] == 1
    assert handler_result["provider"] == "dropbox"


def test_sidecar_forwards_the_vault_session(monkeypatch, tmp_path) -> None:
    sentinel = object()
    seen: dict[str, object] = {}

    def fake(params: dict, vault_session=None):
        seen["vault"] = vault_session
        seen["paths"] = params["paths"]
        return {"success": False, "provider": params["provider"], "synced_count": 0, "errors": []}

    monkeypatch.setattr("middleware.src.sidecar.handlers.drive_sync.handle_drive_sync", fake)
    server = SidecarServer(stdout=io.StringIO(), vault_session=sentinel)
    server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "hs",
            "method": "system.handshake",
            "params": {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        }
    )
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    server.handle_frame(
        {
            "jsonrpc": "2.0",
            "id": "sync",
            "method": "drive_sync.sync",
            "params": {"provider": "dropbox", "paths": [str(image)]},
        }
    )
    assert seen["vault"] is sentinel

