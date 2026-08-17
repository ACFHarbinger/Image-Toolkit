"""Debug & Development Workbench TUI (Phase A3).

Visual terminal user interface for trace timelines, crash forensics, concurrency analysis,
memory profiling, pipeline flamegraphs, and btop-style live watching.
"""

from __future__ import annotations

from .app import render_session_view, run_tui

__all__ = [
    "render_session_view",
    "run_tui",
]
