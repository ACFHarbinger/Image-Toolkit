"""tool.debug: the original ``debugtool`` telemetry-workbench identity.

Preserved as its own subpackage rather than merged flat into ``tool``
when ``debug/debugtool`` folded in here (2026-08-17) — the host's own
``model``/``queries``/``ui`` are the current implementation; this module
is ``debugtool``'s original small public surface, now at ``tool.debug``:

    from tool.debug import open_session, list_sessions
    session = open_session(pid=1234)
    session.orphaned_spans()       # what was in flight at a crash
    session.in_flight_at(t)        # spans active at a moment
    session.overlapping_windows()  # generalized worker-window overlaps

See docs/moon/roadmaps/development_tool.md (Track A) for the full roadmap.
"""

from __future__ import annotations

from ..model.session import (
    TELEMETRY_DIR,
    Session,
    Span,
    discover_sessions,
    list_sessions,
    open_session,
    session_path_for_pid,
)


def render_session_view(session, view_name="timeline", **kwargs):
    """Render a visual TUI view for the given session."""
    from ..ui.app import render_session_view as _render

    return _render(session, view_name=view_name, **kwargs)


def run_tui(session_or_path, initial_view="timeline", live=False, console=None):
    """Run the TUI application."""
    from ..ui.app import run_tui as _run

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
