"""Claim the GUI instance or focus the one that already holds it (#873 / #877).

The Qt and Tauri shells both call ``claim_or_focus``. A second instance
must invoke ``GuiInstance.request_focus`` rather than starting another
window. Closing the UI does not stop the supervisor's siblings.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from middleware.src.supervisor.gui_gate import GuiInstance

ACQUIRED = "ACQUIRED"
FOCUSED_OTHER = "FOCUSED_OTHER"
FOCUS = "FOCUS"


SIDE_BY_SIDE_ENV = "IMAGE_TOOLKIT_SIDE_BY_SIDE"


def qt_gate_dir(data_dir: Path, environ: dict[str, str] | None = None) -> Path:
    """Directory the Qt shell claims its single-instance gate in.

    By default Qt and Tauri share ``data_dir``, so whichever starts second
    focuses the first and exits. With ``IMAGE_TOOLKIT_SIDE_BY_SIDE=1`` Qt
    claims ``data_dir/gate/qt`` instead, so both can run at once during the
    migration. Tauri's gate stays in ``data_dir``, and a second Qt window
    still focuses the first Qt window.
    """
    env = os.environ if environ is None else environ
    if env.get(SIDE_BY_SIDE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return data_dir / "gate" / "qt"
    return data_dir


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
