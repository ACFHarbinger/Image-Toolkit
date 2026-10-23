"""Claim the GUI instance or focus the one that already holds it (#873 / #877).

The Qt and Tauri shells both call ``claim_or_focus``. A second instance
must invoke ``GuiInstance.request_focus`` rather than starting another
window. Closing the UI does not stop the supervisor's siblings.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from middleware.src.supervisor.gui_gate import GuiInstance

ACQUIRED = "ACQUIRED"
FOCUSED_OTHER = "FOCUSED_OTHER"
FOCUS = "FOCUS"


def claim_or_focus(
    data_dir: Path,
    on_focus: Callable[[], None] | None = None,
) -> GuiInstance | None:
    """Return the held instance, or focus the existing owner and return None."""
    instance = GuiInstance(data_dir)
    if instance.acquire(on_focus=on_focus):
        return instance
    instance.request_focus()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="image-toolkit-gui-shell")
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)

    def on_focus() -> None:
        sys.stdout.write(f"{FOCUS}\n")
        sys.stdout.flush()

    held = claim_or_focus(data_dir, on_focus=on_focus)
    if held is None:
        sys.stdout.write(f"{FOCUSED_OTHER}\n")
        sys.stdout.flush()
        return 0
    sys.stdout.write(f"{ACQUIRED}\n")
    sys.stdout.flush()
    try:
        for line in sys.stdin:
            if line.strip() == "QUIT":
                break
    finally:
        held.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
