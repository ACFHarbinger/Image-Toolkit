"""Regression test for ui-arch-48 / #570 (R3.3).

Verifies that zero live processEvents() calls exist in production code under
gui/src. Replaces them with single-shot timers, progress facts, or native Qt
event loop integration.
"""

from __future__ import annotations

from pathlib import Path

from tools.dev.gui_audit.check_no_process_events import find_process_events_calls


def test_no_live_process_events_in_gui_src():
    root = Path(__file__).resolve().parent.parent / "src"
    assert root.is_dir(), f"Expected gui/src directory at {root}"

    violations = find_process_events_calls(root)
    assert not violations, (
        f"Found {len(violations)} live processEvents() call(s) in gui/src:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
