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
from .record import SCHEMA as RECORD_SCHEMA
from .record import SCHEMA_VERSION as RECORD_SCHEMA_VERSION
from .record import Record, records_to_dicts
from .session import (
    TELEMETRY_DIR,
    Session,
    discover_sessions,
    list_sessions,
    open_session,
    session_path_for_pid,
)
from .span import Span
from .telemetry_record_adapter import records_from_session

__all__ = [
    "RECORD_SCHEMA",
    "RECORD_SCHEMA_VERSION",
    "TELEMETRY_DIR",
    "CrashBundle",
    "Event",
    "Investigation",
    "ProcessTree",
    "Record",
    "Session",
    "Span",
    "discover_sessions",
    "list_sessions",
    "open_session",
    "records_from_session",
    "records_to_dicts",
    "session_path_for_pid",
]
