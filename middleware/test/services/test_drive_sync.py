from __future__ import annotations

import pytest
from middleware.src.services.drive_sync.plan import plan_sync


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
    assert result["success"] is True
    assert result["synced_count"] == 2
    assert result["provider"] == "google_drive"

    # Handler test
    handler_result = handle_drive_sync({
        "provider": "dropbox",
        "paths": [str(file1)],
        "dry_run": True,
    })
    assert handler_result["success"] is True
    assert handler_result["synced_count"] == 1
    assert handler_result["provider"] == "dropbox"

