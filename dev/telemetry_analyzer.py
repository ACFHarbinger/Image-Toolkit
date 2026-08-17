#!/usr/bin/env python3
"""Deprecation shim for the original telemetry analyzer.

The analysis logic lives in ``tool.debug.analyzer`` (see
docs/moon/roadmaps/development_tool.md Track A1). This script is kept so
any existing invocation/scripts keep working, but it now delegates to
`tool analyze`.

    python dev/telemetry_analyzer.py [args...]  # same arguments as before

New code should call `python dev/ analyze` directly.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tool.devtool import main  # noqa: E402


def _deprecation_notice() -> str:
    return (
        "note: telemetry_analyzer.py is a compatibility shim; "
        "prefer `python dev/ analyze` (see development_tool.md Track A)"
    )


if __name__ == "__main__":
    warnings.warn(_deprecation_notice(), DeprecationWarning, stacklevel=2)
    sys.exit(main())
