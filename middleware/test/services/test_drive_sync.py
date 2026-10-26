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
