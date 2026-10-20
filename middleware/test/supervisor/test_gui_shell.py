"""The shell is the request_focus caller Grok flagged on #877."""

from __future__ import annotations

from middleware.src.supervisor.gui_gate import GuiInstance
from middleware.src.supervisor.gui_shell import claim_or_focus, main


def test_claim_or_focus_requests_the_existing_owner(tmp_path) -> None:
    focused: list[str] = []
    first = claim_or_focus(tmp_path, on_focus=lambda: focused.append("ok"))
    assert first is not None
    try:
        assert claim_or_focus(tmp_path) is None
        assert focused == ["ok"]
    finally:
        first.release()


def test_cli_focuses_the_running_instance(tmp_path, capsys) -> None:
    holder = GuiInstance(tmp_path)
    focused: list[str] = []
    assert holder.acquire(on_focus=lambda: focused.append("ok")) is True
    try:
        assert main(["--data-dir", str(tmp_path)]) == 0
        assert FOCUSED_MARKER in capsys.readouterr().out
        assert focused == ["ok"]
    finally:
        holder.release()


FOCUSED_MARKER = "FOCUSED_OTHER"
