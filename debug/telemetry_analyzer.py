#!/usr/bin/env python3
"""Deprecation shim for the original telemetry analyzer.

The analysis logic has moved into the debugtool package (see
docs/moon/roadmaps/debug_workbench.md, Phase 1). This script is kept so
any existing invocation/scripts keep working, but it now delegates to
`debugtool analyze`.

    python debug/telemetry_analyzer.py [args...]  # same arguments as before

New code should call `python -m debugtool analyze` directly.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from debugtool.cli.main import main  # noqa: E402


def _deprecation_notice() -> str:
    return (
        "note: telemetry_analyzer.py is a compatibility shim; "
        "prefer `python -m debugtool analyze` (see debug_workbench.md)"
    )


if __name__ == "__main__":
    warnings.warn(_deprecation_notice(), DeprecationWarning, stacklevel=2)
    sys.exit(main())
