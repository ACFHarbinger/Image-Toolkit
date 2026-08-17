"""TUI Application Engine & View Router.

Routes between the 5 Perfetto static views and the btop live watch face:
1. Timeline & Waterfall (timeline)
2. Crash Forensics Splicer (crash)
3. Concurrency & Overlap Inspector (concurrency)
4. Memory & RSS Profiler (memory)
5. Pipeline Flamegraph Breakdown (flame)
6. btop Live Watch (live)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from .views.concurrency import render_concurrency
from .views.crash import render_crash
from .views.flame import render_flame
from .views.live_tail import render_live_view, tail_session_live
from .views.memory import render_memory
from .views.timeline import render_timeline

if TYPE_CHECKING:
    from ..model.session import Session

VIEW_NAMES = ("timeline", "crash", "concurrency", "memory", "flame", "live")


def _render_hotkey_bar(active_view: str) -> RenderableType:
    """Render the global navigation hotkey bar."""
    bar = Text()
    items = [
        ("1", "Timeline", "timeline"),
        ("2", "Crash", "crash"),
        ("3", "Concurrency", "concurrency"),
        ("4", "Memory", "memory"),
        ("5", "Flame", "flame"),
        ("6", "Live Watch", "live"),
    ]
    for key, label, name in items:
        if name == active_view:
            bar.append(f" [{key}] {label} ", style="bold black on bright_cyan")
        else:
            bar.append(f" [{key}] {label} ", style="bold white on grey23")
        bar.append(" ")
    bar.append(" | [q] Quit  [z/x] Zoom  [/] Search", style="dim")
    return Panel(bar, style="grey23")


def render_session_view(
    session: "Session",
    view_name: str = "timeline",
    gdb_trace: Optional[str] = None,
    hs_err_path: Optional[str] = None,
) -> RenderableType:
    """Render a named view for the given session with global navigation bar."""
    name = view_name.lower().strip()
    if name in ("1", "timeline"):
        view_renderable = render_timeline(session)
        current = "timeline"
    elif name in ("2", "crash"):
        view_renderable = render_crash(session, gdb_trace=gdb_trace, hs_err_path=hs_err_path)
        current = "crash"
    elif name in ("3", "concurrency", "overlap"):
        view_renderable = render_concurrency(session)
        current = "concurrency"
    elif name in ("4", "memory", "rss"):
        view_renderable = render_memory(session)
        current = "memory"
    elif name in ("5", "flame", "flamegraph"):
        view_renderable = render_flame(session)
        current = "flame"
    elif name in ("6", "live", "watch"):
        view_renderable = render_live_view(session)
        current = "live"
    else:
        view_renderable = render_timeline(session)
        current = "timeline"

    hotkey_bar = _render_hotkey_bar(current)
    return Group(view_renderable, hotkey_bar)


def run_tui(
    session_or_path: Union["Session", Path, str],
    initial_view: str = "timeline",
    live: bool = False,
    console: Optional[Console] = None,
) -> int:
    """Run the TUI application.

    If live is True, streams updates continuously.
    Otherwise renders the requested view to console.
    """
    from ..model.session import Session

    c = console or Console()

    if isinstance(session_or_path, (str, Path)):
        path = Path(session_or_path)
        if live or initial_view == "live":
            tail_session_live(path)
            return 0
        session = Session.open(path)
    else:
        session = session_or_path

    view_renderable = render_session_view(session, view_name=initial_view)
    c.print(view_renderable)
    return 0
