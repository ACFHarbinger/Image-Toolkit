"""tool queries: cross-session diff, RSS trajectory."""

from __future__ import annotations

from .diff import diff_sessions, format_diff
from .hypothesis import generate_hypothesis
from .perf import format_profile_report, profile_session, render_profile_panel
from .rss import rss_peak, rss_trajectory
from .search import SearchResult, format_search_results, search_workspace

__all__ = [
    "SearchResult",
    "diff_sessions",
    "format_diff",
    "format_profile_report",
    "format_search_results",
    "generate_hypothesis",
    "profile_session",
    "render_profile_panel",
    "rss_peak",
    "rss_trajectory",
    "search_workspace",
]
