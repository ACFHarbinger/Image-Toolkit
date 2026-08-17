"""Session / Span re-export.

Until Track C2 migrates debug/debugtool under dev/, the host imports the
Phase 1 data engine from the existing package. This module is the single
point the rest of devtool uses, so the C2 move is a one-line change here.
"""

from __future__ import annotations

from debugtool import (
    TELEMETRY_DIR,
    Session,
    Span,
    discover_sessions,
    session_path_for_pid,
)

__all__ = [
    "TELEMETRY_DIR",
    "Session",
    "Span",
    "discover_sessions",
    "session_path_for_pid",
]
