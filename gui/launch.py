#!/usr/bin/env python3
"""Launch the standalone Qt demonstration application.

Installed packages need no path setup. The two source roots are added only
when this file is run directly from a repository checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for source_root in (_REPO_ROOT / "logic" / "src", _REPO_ROOT / "gui" / "src"):
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)


def main() -> int:
    from cel_shaded_generator_gui.app import main as run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
