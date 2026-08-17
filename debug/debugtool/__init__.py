"""debugtool: a session-oriented telemetry workbench for Image-Toolkit.

Public API (stable, importable by agents and other tools):

    from debugtool import open_session, list_sessions
    session = open_session(pid=1234)
    session.orphaned_spans()       # what was in flight at a crash
    session.in_flight_at(t)        # spans active at a moment
    session.overlapping_windows()  # generalized worker-window overlaps

Headless by design: the CLI (debugtool analyze / list / ...) is a thin
wrapper over this API, and Gemini's visual UI consumes the same model.

See docs/moon/roadmaps/development_tool.md (Track A) for the full roadmap.
"""

from __future__ import annotations

from .model.session import (
    TELEMETRY_DIR,
    Session,
    Span,
    discover_sessions,
    session_path_for_pid,
)


def list_sessions(directory=None):
    """Return available telemetry files, oldest first (see discover_sessions)."""
    return discover_sessions(directory)


def open_session(path=None, pid=None, directory=None):
    """Open a telemetry session by file path or pid.

    Exactly one of path or pid must be given. Returns a Session, or None if
    the pid has no telemetry file.
    """
    if path is not None:
        return Session.open(path)
    if pid is not None:
        return Session.open_pid(pid, directory)
    raise ValueError("provide either path= or pid=")


def render_session_view(session, view_name="timeline", **kwargs):
    """Render a visual TUI view for the given session."""
    from .ui.app import render_session_view as _render

    return _render(session, view_name=view_name, **kwargs)


def run_tui(session_or_path, initial_view="timeline", live=False, console=None):
    """Run the TUI application."""
    from .ui.app import run_tui as _run

    return _run(session_or_path, initial_view=initial_view, live=live, console=console)


__all__ = [
    "TELEMETRY_DIR",
    "Session",
    "Span",
    "discover_sessions",
    "session_path_for_pid",
    "list_sessions",
    "open_session",
    "render_session_view",
    "run_tui",
]
