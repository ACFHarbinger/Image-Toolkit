"""GUI single-instance gate on the data directory (#877 / Kimi Q2)."""

from __future__ import annotations

from middleware.src.supervisor.gui_gate import GuiInstance


def test_second_gui_requests_focus(tmp_path) -> None:
    focused = []
    first = GuiInstance(tmp_path)
    assert first.acquire(on_focus=lambda: focused.append("ok")) is True
    try:
        second = GuiInstance(tmp_path)
        assert second.acquire() is False
        assert second.request_focus() is True
        assert focused == ["ok"]
    finally:
        first.release()


def test_lock_released_allows_new_owner(tmp_path) -> None:
    first = GuiInstance(tmp_path)
    assert first.acquire() is True
    first.release()
    second = GuiInstance(tmp_path)
    assert second.acquire() is True
    second.release()
