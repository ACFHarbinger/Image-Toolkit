"""tool data model.

Typed, queryable views over telemetry and the durable Investigation /
CrashBundle / ProcessTree models. Session/Span (originally the debugtool
Phase 1 engine, folded in here 2026-08-17) live in .session/.span.
"""

from __future__ import annotations

from .crash_bundle import CrashBundle
from .event import Event
from .investigation import Investigation
from .process_tree import ProcessTree
from .session import (
    TELEMETRY_DIR,
    Session,
    discover_sessions,
    list_sessions,
    open_session,
    session_path_for_pid,
)
from .span import Span

__all__ = [
    "TELEMETRY_DIR",
    "CrashBundle",
    "Event",
    "Investigation",
    "ProcessTree",
    "Session",
    "Span",
    "discover_sessions",
    "list_sessions",
    "open_session",
    "session_path_for_pid",
]
